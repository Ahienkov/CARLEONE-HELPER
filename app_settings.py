"""Per-user preferences, kept outside release packages and forum data."""
from PySide6.QtCore import QSettings, Qt, QEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)
from hotkey_config import parse_hotkey, event_hotkey, display_hotkey
from i18n import LANGUAGES, tr
from dark_combo import DarkComboBox


DEFAULTS = {'hotkey': 'F4', 'background_opacity': 95, 'always_on_top': True, 'check_on_startup': True, 'language': 'ru'}


def validate_preferences(values):
    result = {**DEFAULTS, **values}
    result['hotkey'] = parse_hotkey(result['hotkey'])[0]
    if result['language'] not in LANGUAGES:
        raise ValueError(tr('Некорректное значение настройки.'))
    if type(result['background_opacity']) is not int or not 60 <= result['background_opacity'] <= 100:
        raise ValueError(tr('Непрозрачность должна быть от 60 до 100%.'))
    for name in ('always_on_top', 'check_on_startup'):
        if type(result[name]) is not bool:
            raise ValueError(tr('Некорректное значение настройки.'))
    return {name: result[name] for name in DEFAULTS}


class SettingsStore:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings('CARLEONE', 'HELPER')

    def load(self):
        try:
            values = {name: self.settings.value(name, default, type=type(default)) for name, default in DEFAULTS.items()}
            return validate_preferences(values)
        except (TypeError, ValueError):
            return dict(DEFAULTS)

    def save(self, values):
        values = validate_preferences(values)
        for name, value in values.items():
            self.settings.setValue(name, value)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError(tr('Не удалось сохранить настройки на этом компьютере.'))


class HotkeyCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.key_name = None
        self.suspended_manager = None
        self.setWindowTitle(tr('Выберите клавишу или сочетание'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(440)
        self.setStyleSheet('QDialog { background-color: #161b20; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        self.prompt = QLabel(tr('Нажмите клавишу или сочетание клавиш'))
        self.prompt.setWordWrap(True)
        self.prompt.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(self.prompt)
        note = QLabel(tr('Например: H, F4, Ctrl+H или Ctrl+Shift+H.\nНажатая комбинация будет записана автоматически.'))
        note.setObjectName('status')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Отмена'))
        buttons.rejected.connect(self.reject)
        disable = buttons.addButton(tr('Отключить'), QDialogButtonBox.ButtonRole.ResetRole)
        disable.clicked.connect(self.disable_hotkey)
        layout.addWidget(buttons)
        self.finished.connect(self.cleanup)

    def showEvent(self, event):
        super().showEvent(event)
        from window_hotkey import application_hotkey
        manager = application_hotkey()
        self.suspended_manager = manager
        manager.stop()
        QApplication.instance().installEventFilter(self)

    def cleanup(self, _result):
        QApplication.instance().removeEventFilter(self)
        manager = self.suspended_manager
        self.suspended_manager = None
        if manager is not None:
            window = manager.target() if manager.target else None
            if window is not None:
                from shiboken6 import isValid
                if isValid(window):
                    manager.attach(window)

    def disable_hotkey(self):
        self.key_name = 'disabled'
        self.accept()

    def eventFilter(self, watched, event):
        if self.isVisible() and isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            if event.type() == QEvent.Type.ShortcutOverride:
                event.accept()
                return True
            if event.type() == QEvent.Type.KeyPress:
                if not event.isAutoRepeat():
                    try:
                        key = event_hotkey(event)
                        if key:
                            self.key_name = key
                            self.accept()
                    except ValueError as error:
                        self.prompt.setText(str(error))
                return True
        return super().eventFilter(watched, event)


class HotkeyButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.key_name = 'F4'
        self.setAccessibleName(tr('Выбрать клавишу или сочетание'))
        self.setToolTip(tr('Нажмите, затем нажмите нужную клавишу или сочетание'))
        self.clicked.connect(self.choose)

    def set_hotkey(self, key_name):
        self.key_name = parse_hotkey(key_name)[0]
        self.setText(display_hotkey(self.key_name))

    def choose(self):
        dialog = HotkeyCaptureDialog(self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.key_name is not None:
            self.set_hotkey(dialog.key_name)


class SettingsDialog(QDialog):
    def __init__(self, values, on_save, parent=None):
        super().__init__(parent)
        self.on_save = on_save
        self.setWindowTitle(tr('Настройки GTA 5 RP HELPER'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(470)
        self.setStyleSheet('QDialog { background-color: #161b20; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        title = QLabel(tr('Настройки'))
        title.setStyleSheet('font-size: 22px; font-weight: bold;')
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(16)
        self.language = DarkComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        form.addRow(tr('Язык интерфейса'), self.language)
        self.hotkey = HotkeyButton()
        form.addRow(tr('Показать / скрыть окно'), self.hotkey)
        self.opacity_label = QLabel()
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(60, 100)
        self.opacity.setAccessibleName(tr('Непрозрачность фона'))
        self.opacity.valueChanged.connect(lambda value: self.opacity_label.setText(tr('Непрозрачность фона: {value}%', value=value)))
        form.addRow(self.opacity_label, self.opacity)
        self.always_on_top = QCheckBox(tr('Поверх других окон'))
        self.check_on_startup = QCheckBox(tr('Проверять обновления при запуске'))
        form.addRow(self.always_on_top)
        form.addRow(self.check_on_startup)
        layout.addLayout(form)
        note = QLabel(tr('Карточки законов и правил остаются непрозрачными.\nКнопка ↻ проверяет обновления независимо от настройки запуска.') + '\n' + tr('Тексты законов и правил отображаются в оригинале с форума.'))
        note.setWordWrap(True)
        note.setObjectName('status')
        layout.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.RestoreDefaults)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Сохранить'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Отмена'))
        self.buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(tr('Сбросить'))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(lambda: self.fill(DEFAULTS))
        layout.addWidget(self.buttons)
        self.fill(values)

    def fill(self, values):
        self.language.setCurrentIndex(self.language.findData(values.get('language', 'ru')))
        self.hotkey.set_hotkey(values['hotkey'])
        self.opacity.setValue(values['background_opacity'])
        self.opacity_label.setText(tr('Непрозрачность фона: {value}%', value=values['background_opacity']))
        self.always_on_top.setChecked(values['always_on_top'])
        self.check_on_startup.setChecked(values['check_on_startup'])

    def values(self):
        return validate_preferences({'language': self.language.currentData(), 'hotkey': self.hotkey.key_name, 'background_opacity': self.opacity.value(),
                                     'always_on_top': self.always_on_top.isChecked(), 'check_on_startup': self.check_on_startup.isChecked()})

    def accept(self):
        try:
            self.on_save(self.values())
        except Exception as error:
            QMessageBox.warning(self, tr('Настройки не применены'), str(error))
            return
        super().accept()
