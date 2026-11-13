"""Helper accounts with persistent device sessions and silent Discord role checks."""
import json
import threading
import weakref
from pathlib import Path
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QObject, QTimer, Signal, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QApplication, QLineEdit, QTabWidget, QWidget, QFrame, QFormLayout, QHBoxLayout
from shiboken6 import isValid

from community import DISCORD_INVITE_URL
from discord_session import SessionStore
from dialog_chrome import ChromeDialog

GUILD_ID = '1569352173043589263'
ROLE_ID = '1569352648308686888'


class LoginError(Exception):
    def __init__(self, message, status=0):
        self.status = status
        super().__init__(message)


def load_config(root):
    path = Path(root) / 'discord_access.json'
    if not path.exists():
        return {'enabled': False}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if type(data.get('enabled')) is not bool:
        raise ValueError('Некорректная настройка доступа Discord.')
    if not data['enabled']:
        return data
    url = urlparse(data.get('service_url', ''))
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ('', '/')):
        raise ValueError('Для аккаунтов требуется HTTPS-адрес сервера авторизации.')
    if data.get('guild_id') != GUILD_ID or data.get('role_id') != ROLE_ID:
        raise ValueError('Неверный сервер или роль Discord в настройках доступа.')
    return {**data, 'service_url': data['service_url'].rstrip('/')}


class Client:
    def __init__(self, config):
        self.url = config['service_url']

    def post(self, path, data, key=''):
        try:
            response = requests.post(self.url + path, json=data,
                                     headers={'Authorization': 'Bearer ' + key} if key else {},
                                     timeout=(5, 15), allow_redirects=False)
            if len(response.content) > 32768:
                raise LoginError('Некорректный ответ сервера аккаунтов.')
            value = response.json()
        except (requests.RequestException, ValueError):
            raise LoginError('Не удалось проверить аккаунт. Проверьте интернет и нажмите «Повторить».') from None
        if not isinstance(value, dict):
            raise LoginError('Некорректный ответ сервера аккаунтов.')
        if response.status_code != 200:
            raise LoginError(str(value.get('error', 'Проверка аккаунта не выполнена.')), response.status_code)
        if value.get('status') == 'authorized':
            if value.get('guild_id') != GUILD_ID or value.get('role_id') != ROLE_ID:
                raise LoginError('Сервер подтвердил другую роль Discord.')
            if not isinstance(value.get('account'), dict) or not value['account'].get('id'):
                raise LoginError('Сервер не вернул аккаунт хелпера.')
        return value


class LoginDialog(ChromeDialog):
    def __init__(self, manager):
        super().__init__(title='Аккаунт · CARLEONE HELPER', minimize=True)
        self.manager = manager
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(480)
        layout = self.content_layout
        self.heading = title = QLabel('С возвращением')
        title.setObjectName('dialogHeading')
        layout.addWidget(title)
        self.status = QLabel('Проверяем сохранённый вход…')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName('accountStatus')
        self.detail = QLabel('Создайте логин и пароль хелпера, затем подтвердите свой Discord и роль «Участник». Вход на этом устройстве сохраняется автоматически.')
        self.detail.setObjectName('dialogHint')
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.fields = {}
        for mode, caption in (('login', 'Вход'), ('register', 'Регистрация'), ('recover', 'Забыли пароль?')):
            panel = QWidget()
            form = QFormLayout(panel)
            form.setContentsMargins(0, 18, 0, 4)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setVerticalSpacing(8)
            name, password = QLineEdit(), QLineEdit()
            name.setPlaceholderText('Логин хелпера')
            name.setMaxLength(32)
            password.setPlaceholderText('От 12 символов')
            password.setMaxLength(256)
            password.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow('Логин', name)
            form.addRow('Новый пароль' if mode == 'recover' else 'Пароль', password)
            repeat = None
            if mode != 'login':
                repeat = QLineEdit()
                repeat.setEchoMode(QLineEdit.EchoMode.Password)
                repeat.setMaxLength(256)
                form.addRow('Повторите пароль', repeat)
                repeat.returnPressed.connect(manager.submit_credentials)
            else:
                password.returnPressed.connect(manager.submit_credentials)
            self.fields[mode] = (name, password, repeat)
            self.tabs.addTab(panel, caption)
        layout.addWidget(self.tabs)
        layout.addWidget(self.status)
        self.login = QPushButton('Войти')
        self.login.setObjectName('primaryAction')
        self.login.clicked.connect(manager.submit_credentials)
        self.tabs.currentChanged.connect(self.update_action)
        layout.addWidget(self.login)
        self.retry = QPushButton('Повторить проверку')
        self.retry.clicked.connect(manager.retry)
        self.retry.setObjectName('quietAction')
        footer = QHBoxLayout()
        footer.addWidget(self.retry)
        footer.addStretch()
        join = QPushButton('Наш Discord ↗')
        join.setObjectName('quietAction')
        join.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_INVITE_URL)))
        footer.addWidget(join)
        layout.addLayout(footer)
        self.update_action()

    def update_action(self):
        index = self.tabs.currentIndex()
        self.login.setText(('Войти в хелпер', 'Создать аккаунт', 'Восстановить через Discord')[index])
        self.heading.setText(('С возвращением', 'Создать аккаунт', 'Восстановить доступ')[index])
        self.detail.setText(('Введите логин и пароль. Вход на этом устройстве сохранится автоматически.', 'Придумайте логин и пароль. На следующем шаге подтвердите Discord и роль «Участник».', 'Укажите логин и новый пароль. Подтвердите Discord, привязанный к аккаунту.')[index])

    def select_mode(self, mode, setup=False):
        self.tabs.setCurrentIndex({'login': 0, 'register': 1, 'recover': 2}[mode])
        self.tabs.setTabEnabled(0, not setup)
        self.tabs.setTabEnabled(2, not setup)
        self.update_action()

    def clear_passwords(self):
        for _, password, repeat in self.fields.values():
            password.clear()
            if repeat is not None:
                repeat.clear()

    def closeEvent(self, event):
        event.accept() if self.manager.shutdown() else event.ignore()

    def reject(self):
        self.close()


class AccountManager(QObject):
    completed = Signal(object)

    def __init__(self, app, config, root, factory, client=None, store=None):
        super().__init__(app)
        self.app, self.factory = app, factory
        self.client = client or Client(config)
        self.store = store or SessionStore(root, config['service_url'])
        self.saved = self.store.load()
        self.identity = ({k: self.saved[k] for k in ('install_id', 'release_id')} if self.saved else self.store.new_identity())
        self.target = self.account = self.pending = None
        self.authorized = self.busy = self.stopped = self.setup_required = False
        self.generation = 0
        self.dialog = LoginDialog(self)
        self.timer = QTimer(self)
        self.timer.setInterval(300000)
        self.timer.timeout.connect(self.retry)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(3000)
        self.poll_timer.timeout.connect(self.poll)
        self.completed.connect(self.finish)
        app.aboutToQuit.connect(self.stop)

    def window(self):
        window = self.target() if self.target else None
        return window if window is not None and isValid(window) else None

    def attach(self, window):
        self.target = weakref.ref(window)
        window.setEnabled(self.authorized)
        if not self.authorized:
            QTimer.singleShot(0, self.dialog.show)

    def start(self):
        self.app.setQuitOnLastWindowClosed(False)
        self.dialog.show()
        if self.saved:
            self.retry()
        else:
            self.dialog.status.setText('Войдите по логину и паролю или создайте аккаунт.')

    def work(self, phase, action):
        if self.busy or self.stopped:
            return
        self.busy = True
        self.dialog.login.setEnabled(False)
        self.dialog.tabs.setEnabled(False)
        self.dialog.retry.setEnabled(False)
        generation = self.generation
        def run():
            try:
                result = {'value': action()}
            except LoginError as error:
                result = {'error': str(error), 'status': error.status}
            except Exception:
                result = {'error': 'Не удалось обработать вход. Повторите попытку.'}
            if not self.stopped:
                try:
                    self.completed.emit({**result, 'phase': phase, 'generation': generation})
                except RuntimeError:
                    pass
        threading.Thread(target=run, daemon=True, name='HelperAccount').start()

    def submit_credentials(self):
        if self.busy or self.pending:
            return
        mode = ('login', 'register', 'recover')[self.dialog.tabs.currentIndex()]
        name_field, password_field, repeat = self.dialog.fields[mode]
        name, password = name_field.text(), password_field.text()
        import re
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]{2,31}', name):
            self.dialog.status.setText('Логин: 3–32 латинских символа, первая буква; разрешены цифры, точка, _ и -.')
            return
        if not 12 <= len(password) <= 128:
            self.dialog.status.setText('Пароль должен содержать от 12 до 128 символов.')
            return
        if repeat is not None and repeat.text() != password:
            self.dialog.status.setText('Пароли не совпадают.')
            return
        self.generation += 1
        data = {**self.identity, 'username': name, 'password': password}
        self.dialog.clear_passwords()
        if self.setup_required and self.saved:
            key = self.saved['session_key']
            self.work('setup', lambda: self.client.post('/v2/account/setup', data, key))
        elif mode == 'login':
            self.dialog.status.setText('Проверяем логин, пароль и доступ…')
            self.work('signin', lambda: self.client.post('/v2/login', data))
        else:
            self.dialog.status.setText('Открываем подтверждение Discord в браузере…')
            self.work('begin', lambda: self.client.post('/v2/' + mode, data))

    def poll(self):
        if self.pending:
            login = self.pending.copy()
            self.work('poll', lambda: self.client.post('/v2/registration/' + login['login_id'], self.identity, login['polling_secret']))

    def retry(self):
        if self.busy:
            return
        if self.saved:
            saved = self.saved.copy()
            self.work('check', lambda: self.client.post('/v1/session/check', self.identity, saved['session_key']))
        elif self.pending:
            self.poll()
        else:
            self.dialog.status.setText('Введите логин и пароль или откройте вкладку «Регистрация».')

    def lock(self, message):
        self.authorized = False
        self.app.setQuitOnLastWindowClosed(False)
        self.timer.stop()
        window = self.window()
        if window is not None:
            window.setEnabled(False)
            window.hide()
            from window_hotkey import application_hotkey
            application_hotkey().detach(window)
        self.dialog.status.setText(message)
        self.dialog.show()
        self.dialog.raise_()

    def finish(self, result):
        self.busy = False
        self.dialog.login.setEnabled(True)
        self.dialog.tabs.setEnabled(True)
        self.dialog.retry.setEnabled(True)
        if self.stopped or result['generation'] != self.generation:
            return
        phase = result['phase']
        if 'error' in result:
            if phase in ('begin', 'poll'):
                self.poll_timer.stop()
                self.pending = None
            if result.get('status') in (401, 403):
                self.saved = None
                self.setup_required = False
                self.dialog.select_mode('login')
                try:
                    self.store.clear()
                except OSError:
                    pass
            self.lock(result['error'])
            return
        value = result['value']
        if phase == 'begin':
            url = urlparse(value.get('browser_url', ''))
            if url.scheme != 'https' or url.hostname != 'discord.com' or url.path != '/oauth2/authorize':
                self.lock('Сервер вернул некорректный адрес подтверждения Discord.')
                return
            self.pending = value
            if not QDesktopServices.openUrl(QUrl(value['browser_url'])):
                self.pending = None
                self.lock('Не удалось открыть браузер. Повторите вход.')
                return
            self.dialog.status.setText('Подтвердите Discord в браузере. Аккаунт будет готов после проверки роли «Участник».')
            self.poll_timer.start()
        elif value.get('status') == 'setup_required':
            self.setup_required = True
            self.dialog.select_mode('register', setup=True)
            self.lock('Discord уже подтверждён. Завершите создание аккаунта: придумайте логин и пароль хелпера.')
        elif value.get('status') == 'authorized':
            if phase in ('poll', 'signin', 'setup'):
                saved = {**self.identity, 'session_key': value.get('session_key') or self.saved['session_key'], 'account': value['account']}
                try:
                    self.store.save(saved)
                except OSError:
                    self.lock('Windows не смогла сохранить вход. Проверьте доступ к папке хелпера и войдите повторно.')
                    return
                self.saved = saved
            self.poll_timer.stop()
            self.pending = None
            self.setup_required = False
            self.dialog.select_mode('login')
            self.dialog.clear_passwords()
            self.account = value['account']
            self.authorized = True
            self.dialog.hide()
            window = self.window()
            if window is None:
                window = self.factory()
                self.app.account_window = window
                self.attach(window)
            if hasattr(window, 'account_button'):
                window.account_button.setText('Мой аккаунт')
                window.account_button.setToolTip('Аккаунт: ' + self.account.get('username', self.account['display_name']))
            window.setEnabled(True)
            window.show()
            self.app.setQuitOnLastWindowClosed(True)
            self.timer.start()
        elif phase == 'logout':
            pass
        elif value.get('status') != 'pending':
            self.lock('Сервер не подтвердил доступ к хелперу.')

    def create_account_dialog(self):
        dialog = ChromeDialog(self.window(), title='Мой аккаунт')
        dialog.setMinimumWidth(460)
        layout = dialog.content_layout
        heading = QLabel('Ваш аккаунт')
        heading.setObjectName('dialogHeading')
        layout.addWidget(heading)
        subtitle = QLabel('Ваше личное пространство в CARLEONE HELPER.')
        subtitle.setObjectName('dialogHint')
        layout.addWidget(subtitle)
        profile = QFrame()
        profile.setObjectName('profileCard')
        row = QHBoxLayout(profile)
        row.setContentsMargins(18, 18, 18, 18)
        row.setSpacing(14)
        username = self.account.get('username', self.account['display_name'])
        avatar = QLabel(username[:1].upper())
        avatar.setObjectName('profileAvatar')
        avatar.setFixedSize(48, 48)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(avatar)
        identity = QVBoxLayout()
        name = QLabel(username)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setObjectName('profileName')
        identity.addWidget(name)
        verified = QLabel('Discord подтверждён · Участник')
        verified.setObjectName('profileVerified')
        identity.addWidget(verified)
        row.addLayout(identity, 1)
        layout.addWidget(profile)
        for caption, value in [('Discord', self.account['display_name']), ('Discord ID', self.account['discord_id']), ('Устройство', 'Вход сохранён')]:
            line = QHBoxLayout()
            label = QLabel(caption)
            label.setObjectName('dialogHint')
            text = QLabel(value)
            text.setTextFormat(Qt.TextFormat.PlainText)
            line.addWidget(label)
            line.addStretch()
            line.addWidget(text)
            layout.addLayout(line)
        change = QPushButton('Изменить пароль через Discord')
        change.clicked.connect(lambda: (dialog.accept(), self.open_recovery()))
        layout.addWidget(change)
        logout = QPushButton('Выйти на этом устройстве')
        logout.setObjectName('quietAction')
        logout.clicked.connect(lambda: (dialog.accept(), self.logout()))
        layout.addWidget(logout)
        return dialog

    def show_account(self):
        if self.account:
            self.create_account_dialog().exec()

    def open_recovery(self):
        if self.busy:
            return
        self.dialog.select_mode('recover')
        self.dialog.fields['recover'][0].setText(self.account.get('username', '') if self.account else '')
        self.lock('Задайте новый пароль и подтвердите привязанный Discord. После смены пароля остальные устройства выйдут из аккаунта.')

    def logout(self):
        if self.busy:
            return
        old = self.saved
        try:
            self.store.clear()
        except OSError:
            self.lock('Не удалось удалить сохранённый вход. Проверьте доступ к папке хелпера.')
            return
        self.saved = self.account = None
        self.setup_required = False
        self.dialog.select_mode('login')
        self.dialog.clear_passwords()
        self.generation += 1
        self.lock('Вы вышли из аккаунта хелпера.')
        if old:
            self.work('logout', lambda: self.client.post('/v1/session/logout', self.identity, old['session_key']))

    def shutdown(self):
        window = self.window()
        if window is not None and not window.close():
            return False
        self.stop()
        self.app.quit()
        return True

    def stop(self):
        self.stopped = True
        self.timer.stop()
        self.poll_timer.stop()
