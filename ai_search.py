"""Account-authenticated AI search, isolated from ordinary catalog searches."""
import html
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QPlainTextEdit, QTextBrowser)
from dark_combo import DarkComboBox
from discord_access import load_config
from discord_session import SessionStore
from server_registry import SERVER_NAMES


class AiError(Exception):
    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload or {}


class AiClient:
    def __init__(self, root=None):
        root = Path(root or Path(__file__).parent)
        self.config = load_config(root)
        self.store = SessionStore(root, self.config.get('service_url', ''))

    def post(self, route, data=None):
        saved = self.store.load()
        if not self.config.get('enabled') or not saved:
            raise AiError('Для ИИ-поиска войдите в аккаунт хелпера.')
        body = {key: saved[key] for key in ('install_id', 'release_id')}
        body.update(data or {})
        try:
            response = requests.post(self.config['service_url'] + '/v1/ai/' + route, json=body,
                headers={'Authorization': 'Bearer ' + saved['session_key']}, timeout=(5, 65), allow_redirects=False)
            if len(response.content) > 65536:
                raise ValueError()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
        except (requests.RequestException, ValueError):
            raise AiError('Не удалось связаться с ИИ-поиском. Проверьте интернет и повторите запрос.') from None
        if response.status_code != 200:
            raise AiError(result.get('error', 'ИИ-поиск недоступен.'), result)
        return result


class AiSearchPanel(QWidget):
    completed = Signal(object)

    def __init__(self, parent=None, client=None, view=None):
        super().__init__(parent)
        self.client = client or AiClient()
        self.server = None
        self.generation = 0
        self.busy = self.stopped = False
        self.pending = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        row = QHBoxLayout()
        self.scope = DarkComboBox()
        for label, value in [('Законы и правила', 'all'), ('Только законы', 'laws'), ('Только правила', 'rules')]:
            self.scope.addItem(label, value)
        self.scope.setCurrentIndex(max(0, self.scope.findData((view or {}).get('scope', 'all'))))
        row.addWidget(self.scope)
        row.addStretch()
        self.quota_label = QLabel('5 новых запросов в сутки на аккаунт')
        self.quota_label.setObjectName('aiQuota')
        row.addWidget(self.quota_label)
        layout.addLayout(row)
        self.question = QPlainTextEdit()
        self.question.setObjectName('aiQuestion')
        self.question.setPlaceholderText('Опишите ситуацию своими словами. Например: игрок угнал чужую машину и скрылся. Какие статьи могут подходить?')
        self.question.setMaximumHeight(110)
        self.question.setPlainText((view or {}).get('query', ''))
        layout.addWidget(self.question)
        actions = QHBoxLayout()
        hint = QLabel('Ответы на повторные вопросы сохраняются для вашего аккаунта и не тратят лимит.')
        hint.setObjectName('pageSubtitle')
        hint.setWordWrap(True)
        actions.addWidget(hint, 1)
        self.submit = QPushButton('Найти с ИИ')
        self.submit.setObjectName('primaryAction')
        self.submit.clicked.connect(self.search)
        actions.addWidget(self.submit)
        layout.addLayout(actions)
        self.status = QLabel('Выберите сервер в боковой панели и опишите ситуацию. Отправляется только ваш вопрос; заметки и финансы не передаются.')
        self.status.setObjectName('aiStatus')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.answer = QTextBrowser()
        self.answer.setObjectName('aiAnswer')
        self.answer.setOpenExternalLinks(False)
        self.answer.setHtml('<p style="color:#85858d;">Здесь появится объяснение и ссылки на подходящие статьи выбранного сервера.</p>')
        layout.addWidget(self.answer, 1)
        self.poll_timer = QTimer(self)
        self.poll_timer.setSingleShot(True)
        self.poll_timer.timeout.connect(self.poll)
        self.completed.connect(self.finish)

    def export_view(self):
        return {'query': self.question.toPlainText(), 'scope': self.scope.currentData()}

    def set_server(self, server):
        if server == self.server:
            return
        self.server = server
        self.generation += 1
        self.pending = None
        self.poll_timer.stop()
        self.busy = False
        self.submit.setEnabled(True)
        self.scope.setEnabled(True)
        self.answer.clear()
        self.status.setText('База сервера ' + SERVER_NAMES.get(server, server) + '. Опишите ситуацию, чтобы найти подходящие статьи.')
        self.work('quota', lambda: self.client.post('quota'))

    def work(self, phase, action):
        if self.stopped or self.busy:
            return
        self.busy = True
        self.submit.setEnabled(False)
        self.scope.setEnabled(False)
        generation = self.generation
        def run():
            try:
                result = {'value': action()}
            except AiError as error:
                result = {'error': str(error), 'payload': error.payload}
            except Exception:
                result = {'error': 'Не удалось обработать ответ ИИ. Повторите попытку.'}
            try:
                if not self.stopped:
                    self.completed.emit({**result, 'generation': generation, 'phase': phase})
            except RuntimeError:
                pass
        threading.Thread(target=run, daemon=True, name='HelperAiSearch').start()

    def search(self):
        if self.busy or self.pending:
            return
        query = self.question.toPlainText().strip()
        if not 8 <= len(query) <= 800:
            self.status.setText('Опишите ситуацию: от 8 до 800 символов.')
            return
        self.pending = {'query': query, 'server': self.server, 'scope': self.scope.currentData()}
        self.status.setText('Подбираем статьи и готовим объяснение…')
        self.poll()

    def poll(self):
        if self.pending:
            data = self.pending.copy()
            self.work('search', lambda: self.client.post('search', data))

    def show_quota(self, value):
        if not isinstance(value, dict):
            return
        remaining, limit = value.get('remaining', 0), value.get('limit', 5)
        self.quota_label.setText(f'Осталось {remaining} из {limit} на сегодня')
        if value.get('reset_at'):
            reset = datetime.fromtimestamp(value['reset_at']).astimezone().strftime('%d.%m в %H:%M')
            self.quota_label.setToolTip('Лимит привязан к аккаунту. Обновление: ' + reset)

    def finish(self, result):
        if self.stopped or result['generation'] != self.generation:
            return
        self.busy = False
        self.submit.setEnabled(True)
        self.scope.setEnabled(True)
        if 'error' in result:
            self.pending = None
            self.status.setText(result['error'])
            self.show_quota(result.get('payload', {}).get('quota'))
            return
        value = result['value']
        self.show_quota(value.get('quota'))
        if result['phase'] == 'quota':
            return
        if value.get('status') == 'pending':
            self.status.setText('Этот вопрос уже обрабатывается. Ожидаем сохранённый ответ…')
            self.submit.setEnabled(False)
            self.poll_timer.start(3000)
            return
        self.pending = None
        answer = value.get('answer', '')
        if value.get('status') != 'ready' or not isinstance(answer, str):
            self.status.setText('Некорректный ответ сервиса ИИ.')
            return
        rendered = '<div style="font-size:14px;line-height:1.5;color:#dedee3;">' + html.escape(answer).replace('\n', '<br>') + '</div>'
        for source in value.get('sources', []):
            url = urlparse(source.get('url', ''))
            if url.scheme == 'https' and url.hostname == 'forum.gta5rp.com' and not url.username and not url.password:
                rendered += '<p><a style="color:#e5c779;" href="' + html.escape(source['url'], quote=True) + '">[' + str(source.get('ref', '')) + '] ' + html.escape(source.get('title', 'Источник')) + '</a></p>'
        self.answer.setHtml(rendered)
        self.answer.anchorClicked.connect(self.open_source) if not getattr(self, '_links_connected', False) else None
        self._links_connected = True
        self.status.setText('Сохранённый ответ · лимит не расходуется' if value.get('cached') else ('Ответ готов · использован 1 запрос' if value.get('charged') else 'Подходящие статьи не найдены · запрос не списан'))

    def open_source(self, url):
        if url.scheme() == 'https' and url.host() == 'forum.gta5rp.com':
            QDesktopServices.openUrl(url)

    def stop(self):
        self.stopped = True
        self.generation += 1
        self.poll_timer.stop()
