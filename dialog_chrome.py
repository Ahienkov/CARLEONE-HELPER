"""Shared dark, draggable window chrome for helper dialogs."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                              QMessageBox as QtMessageBox, QPushButton, QVBoxLayout,
                              QWidget, QInputDialog as QtInputDialog)


from app_theme import DIALOG_STYLE


class DialogHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()
        else:
            super().mousePressEvent(event)


def decorate_dialog(dialog, title, minimize=False):
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    dialog.setFont(QFont('Segoe UI', 10))
    dialog.setStyleSheet(DIALOG_STYLE)
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    shell = QFrame()
    shell.setObjectName('dialogShell')
    outer.addWidget(shell)
    surface = QVBoxLayout(shell)
    surface.setContentsMargins(24, 14, 24, 24)
    surface.setSpacing(14)
    header = DialogHeader()
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    brand = QLabel('CARLEONE  /  HELPER')
    brand.setObjectName('dialogBrand')
    brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    row.addWidget(brand)
    row.addStretch()
    if minimize:
        button = QPushButton('−')
        button.setObjectName('chromeMinimize')
        button.setFixedSize(30, 30)
        button.setAccessibleName('Свернуть окно')
        button.clicked.connect(dialog.showMinimized)
        row.addWidget(button)
    close = QPushButton('×')
    close.setObjectName('chromeClose')
    close.setFixedSize(30, 30)
    close.setAccessibleName('Закрыть окно')
    close.clicked.connect(dialog.close)
    row.addWidget(close)
    surface.addWidget(header)
    body = QVBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(16)
    surface.addLayout(body)
    dialog.setWindowTitle(title)
    return body


class ChromeDialog(QDialog):
    def __init__(self, parent=None, title='', minimize=False):
        super().__init__(parent)
        self.content_layout = decorate_dialog(self, title, minimize)


class MessageBox(QtMessageBox):
    """Keep Qt message-box behavior, replacing only the OS window frame."""
    @classmethod
    def _show(cls, parent, title, text, icon, buttons, default):
        box = cls(parent)
        box.setWindowTitle(title)
        box.setIcon(icon)
        box.setText(title)
        box.setInformativeText(text)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setStandardButtons(buttons)
        box.setDefaultButton(default)
        box.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        box.setStyleSheet(DIALOG_STYLE + 'QMessageBox { background: #131313; border: 1px solid #303030; border-radius: 12px; padding: 20px; }')
        return cls.StandardButton(box.exec())

    @classmethod
    def warning(cls, parent, title, text, buttons=QtMessageBox.StandardButton.Ok, defaultButton=QtMessageBox.StandardButton.NoButton):
        return cls._show(parent, title, text, cls.Icon.Warning, buttons, defaultButton)

    @classmethod
    def critical(cls, parent, title, text, buttons=QtMessageBox.StandardButton.Ok, defaultButton=QtMessageBox.StandardButton.NoButton):
        return cls._show(parent, title, text, cls.Icon.Critical, buttons, defaultButton)

    @classmethod
    def question(cls, parent, title, text, buttons=QtMessageBox.StandardButton.Yes | QtMessageBox.StandardButton.No, defaultButton=QtMessageBox.StandardButton.NoButton):
        return cls._show(parent, title, text, cls.Icon.Question, buttons, defaultButton)


class InputDialog(QtInputDialog):
    @classmethod
    def getText(cls, parent, title, label, echo=QLineEdit.EchoMode.Normal, text='', flags=Qt.WindowType.Widget, inputMethodHints=Qt.InputMethodHint.ImhNone):
        box = cls(parent, flags | Qt.WindowType.FramelessWindowHint)
        box.setWindowTitle(title)
        box.setLabelText(label)
        box.setTextEchoMode(echo)
        box.setTextValue(text)
        box.setInputMethodHints(inputMethodHints)
        box.setOkButtonText('Сохранить')
        box.setCancelButtonText('Отмена')
        box.setStyleSheet(DIALOG_STYLE + 'QInputDialog { background: #131313; border: 1px solid #303030; padding: 20px; }')
        accepted = box.exec() == QDialog.DialogCode.Accepted
        return box.textValue(), accepted
