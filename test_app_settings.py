import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog

from app_settings import DEFAULTS, SettingsDialog, SettingsStore
from main import CarleoneWindow
from window_hotkey import WindowHotkey


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.store = SettingsStore(QSettings(str(Path(self.directory.name) / 'preferences.ini'), QSettings.Format.IniFormat))

    def tearDown(self):
        self.directory.cleanup()

    def test_store_remembers_valid_preferences(self):
        self.assertEqual(self.store.load(), DEFAULTS)
        values = {**DEFAULTS, 'background_opacity': 88, 'hotkey': 'F6', 'check_on_startup': False}
        self.store.save(values)
        self.assertEqual(self.store.load(), values)
        with self.assertRaises(ValueError):
            self.store.save({**values, 'background_opacity': 150})
        self.assertEqual(self.store.load(), values)

    def test_cancel_does_not_apply_and_save_applies(self):
        save = Mock()
        dialog = SettingsDialog(DEFAULTS, save)
        dialog.opacity.setValue(85)
        dialog.reject()
        save.assert_not_called()
        dialog = SettingsDialog(DEFAULTS, save)
        dialog.opacity.setValue(90)
        dialog.hotkey.set_hotkey('F6')
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(save.call_args.args[0]['hotkey'], 'F6')
        self.assertEqual(save.call_args.args[0]['background_opacity'], 90)

    def test_preferences_change_window_without_fading_cards(self):
        window = CarleoneWindow()
        window.settings_store = self.store
        try:
            window.apply_preferences({**DEFAULTS, 'background_opacity': 80, 'always_on_top': False, 'hotkey': 'disabled'})
            self.assertIn('rgba(18, 22, 25, 204)', window.styleSheet())
            self.assertIn('background-color: #1b2229', window.styleSheet())
            self.assertFalse(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            self.assertIn('отключена', window.hotkey_hint.text())
            self.assertEqual(self.store.load()['background_opacity'], 80)
        finally:
            window.close()
            window.deleteLater()

    def test_busy_new_key_restores_previous_key(self):
        api = Mock()
        api.RegisterHotKey.side_effect = lambda hwnd, identifier, modifiers, key: key != 0x75
        manager = WindowHotkey(self.app, api=api)
        window = CarleoneWindow()
        try:
            self.assertTrue(manager.attach(window, 'F4'))
            self.assertFalse(manager.try_change(window, 'F6'))
            self.assertEqual(manager.key_name, 'F4')
            self.assertTrue(manager.registered)
            self.assertTrue(manager.try_change(window, 'disabled'))
            self.assertFalse(manager.registered)
        finally:
            manager.stop()
            self.app.removeNativeEventFilter(manager)
            self.app.aboutToQuit.disconnect(manager.stop)
            window.close()
            window.deleteLater()


if __name__ == '__main__':
    unittest.main()
