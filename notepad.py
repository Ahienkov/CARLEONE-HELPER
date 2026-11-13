"""A local tabbed notebook stored outside application release packages."""
import json

from PySide6.QtCore import QSettings, Qt, QSignalBlocker, QSize
from PySide6.QtWidgets import (QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QToolButton, QTabBar, QVBoxLayout, QWidget)

from dialog_chrome import MessageBox as QMessageBox, InputDialog as QInputDialog

from i18n import tr
from ui_icons import line_icon


class NotepadStore:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings('CARLEONE', 'HELPER')

    def load(self):
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError(tr('Не удалось прочитать блокнот.'))
        if not self.settings.contains('notepad/v2/document'):
            return {'active': 0, 'tabs': [{'title': tr('Заметка {number}', number=1),
                                         'text': self.settings.value('notepad/v1/text', '', type=str)}]}
        try:
            document = json.loads(self.settings.value('notepad/v2/document', '', type=str))
            if (not isinstance(document, dict) or not isinstance(document.get('tabs'), list)
                    or not document['tabs'] or type(document.get('active')) is not int
                    or not 0 <= document['active'] < len(document['tabs'])):
                raise ValueError()
            for tab in document['tabs']:
                if (not isinstance(tab, dict) or not isinstance(tab.get('title'), str)
                        or not tab['title'].strip() or not isinstance(tab.get('text'), str)):
                    raise ValueError()
            return document
        except (TypeError, ValueError):
            raise ValueError(tr('Не удалось прочитать блокнот.')) from None

    def save(self, document):
        self.settings.setValue('notepad/v2/document', json.dumps(document, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError(tr('Не удалось сохранить блокнот. Текст остаётся в редакторе.'))


class NoteTabBar(QTabBar):
    """Scroll complete tab labels instead of squeezing every tab to an ellipsis."""
    def tabSizeHint(self, index):
        text_width = self.fontMetrics().horizontalAdvance(self.tabText(index))
        return QSize(max(146, text_width + 64), 42)

    def minimumTabSizeHint(self, index):
        return self.tabSizeHint(index)


class NotepadPanel(QWidget):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.dirty = False
        self.document = {'active': 0, 'tabs': [{'title': '', 'text': ''}]}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.title = QLabel()
        header.addWidget(self.title)
        header.addStretch()
        self.add_button = QPushButton()
        self.add_button.setObjectName('noteAdd')
        self.add_button.clicked.connect(self.add_tab)
        header.addWidget(self.add_button)
        self.save_button = QPushButton()
        self.save_button.setObjectName('noteSave')
        self.save_button.clicked.connect(self.save)
        header.addWidget(self.save_button)
        layout.addLayout(header)
        self.tabs = NoteTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setTabsClosable(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setStyleSheet('''
            QTabBar::tab { background: #1a1a1c; color: #93959d;
                padding: 8px 14px; border: 1px solid #303033; border-radius: 8px;
                margin-right: 8px; font-size: 12px; }
            QTabBar::tab:selected { background: #2b271e; color: #e9cf8e; border-color: #5c4e2e; }
            QTabBar::tab:hover { background: #262628; color: #ededee; }
            QTabBar QToolButton { background: #202022; border: none; border-radius: 5px; padding: 2px; }
            QToolButton#noteTabClose { background: transparent; border: none; padding: 0; }
            QToolButton#noteTabClose:hover { background: transparent; }
        ''')
        layout.addWidget(self.tabs)
        self.editor = QPlainTextEdit()
        self.editor.setTabChangesFocus(True)
        self.editor.setStyleSheet('QPlainTextEdit { background: #131313; color: #f4f4f4; '
                                 'border: 1px solid #303030; border-radius: 10px; padding: 14px; '
                                 'font-size: 14px; selection-background-color: #615125; }')
        layout.addWidget(self.editor, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setStyleSheet('color: #73757d; font-size: 11px;')
        layout.addWidget(self.status)
        self.retranslate_ui()
        try:
            self.document = store.load()
            self.rebuild_tabs()
        except (OSError, TypeError, ValueError) as error:
            self.editor.setReadOnly(True)
            self.save_button.setEnabled(False)
            self.add_button.setEnabled(False)
            self.tabs.setEnabled(False)
            self.status.setText(str(error))
        self.editor.textChanged.connect(self.text_changed)
        self.tabs.currentChanged.connect(self.change_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_tab)
        self.tabs.tabCloseRequested.connect(self.remove_tab)

    def retranslate_ui(self):
        self.title.setText(tr('Блокнот'))
        self.title.hide()
        self.save_button.setText(tr('Сохранить'))
        self.add_button.setText(tr('+ Вкладка'))
        self.tabs.setAccessibleName(tr('Вкладки блокнота'))
        self.tabs.setToolTip(tr('Двойной щелчок по вкладке — переименовать'))
        self.editor.setAccessibleName(tr('Блокнот'))
        self.editor.setPlaceholderText(tr('Записывайте сюда всё, что нужно запомнить…'))
        if not self.dirty and not self.editor.isReadOnly():
            self.status.setText(tr('Автосохранение на этом компьютере. Общие заметки для всех серверов.'))

    def text_changed(self):
        self.document['tabs'][self.document['active']]['text'] = self.editor.toPlainText()
        self.dirty = True
        self.save()

    def rebuild_tabs(self):
        with QSignalBlocker(self.tabs), QSignalBlocker(self.editor):
            while self.tabs.count():
                self.tabs.removeTab(0)
            for tab in self.document['tabs']:
                self.tabs.addTab(tab['title'])
            self.tabs.setCurrentIndex(self.document['active'])
            self.editor.setPlainText(self.document['tabs'][self.document['active']]['text'])
        if len(self.document['tabs']) > 1:
            for index, tab in enumerate(self.document['tabs']):
                close = QToolButton(self.tabs)
                close.setObjectName('noteTabClose')
                close.setAutoRaise(True)
                close.setIcon(line_icon('close', 12))
                close.setFixedSize(20, 20)
                close.setCursor(Qt.CursorShape.PointingHandCursor)
                close.setAccessibleName(tr('Удалить вкладку') + ': ' + tab['title'])
                close.setToolTip(tr('Удалить вкладку'))
                close.clicked.connect(lambda _checked=False, index=index: self.tabs.tabCloseRequested.emit(index))
                self.tabs.setTabButton(index, QTabBar.ButtonPosition.RightSide, close)
        for index, tab in enumerate(self.document['tabs']):
            self.tabs.setTabToolTip(index, tab['title'])

    def add_tab(self):
        titles = {tab['title'] for tab in self.document['tabs']}
        number = 1
        while tr('Заметка {number}', number=number) in titles:
            number += 1
        self.document['tabs'].append({'title': tr('Заметка {number}', number=number), 'text': ''})
        self.document['active'] = len(self.document['tabs']) - 1
        self.rebuild_tabs()
        self.dirty = True
        self.save()
        self.editor.setFocus()

    def change_tab(self, index):
        if not 0 <= index < len(self.document['tabs']):
            return
        self.document['active'] = index
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(self.document['tabs'][index]['text'])
        self.dirty = True
        self.save()

    def rename_tab(self, index):
        if not 0 <= index < len(self.document['tabs']):
            return
        title, accepted = QInputDialog.getText(self, tr('Переименовать вкладку'), tr('Название вкладки'),
                                              text=self.document['tabs'][index]['title'])
        if accepted and title.strip():
            self.document['tabs'][index]['title'] = title.strip()
            self.tabs.setTabText(index, title.strip())
            self.dirty = True
            self.save()

    def remove_tab(self, index):
        if len(self.document['tabs']) <= 1 or not 0 <= index < len(self.document['tabs']):
            return
        answer = QMessageBox.question(self, tr('Удалить вкладку'),
                                      tr('Удалить вкладку «{title}» и её текст?',
                                         title=self.document['tabs'][index]['title']),
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.document['tabs'][index]
        active = self.document['active']
        self.document['active'] = min(active - (index < active), len(self.document['tabs']) - 1)
        self.rebuild_tabs()
        self.dirty = True
        self.save()

    def save(self):
        if self.editor.isReadOnly():
            return True
        try:
            self.store.save(self.document)
        except OSError as error:
            self.status.setText(str(error))
            return False
        self.dirty = False
        self.status.setText(tr('Сохранено на этом компьютере'))
        return True

    def flush(self):
        return not self.dirty or self.save()
