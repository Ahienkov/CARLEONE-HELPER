import os
import unittest
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app_settings import HotkeyCaptureDialog, HotkeyButton, validate_preferences, DEFAULTS
from hotkey_config import event_hotkey, parse_hotkey
from window_hotkey import WindowHotkey, HOTKEY_ID, MOD_NOREPEAT
from main import CarleoneWindow


class HotkeyConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_keyboard_combinations_map_to_windows_values(self):
        examples = {'H': (0, 0x48), 'Ctrl+Shift+H': (6, 0x48), 'Alt+F24': (1, 0x87),
                    'Meta+J': (8, 0x4A), 'Ctrl+Num+1': (2, 0x61), 'Ctrl+,': (2, 0xBC),
                    'Esc': (0, 0x1B), 'Ctrl++': (6, 0xBB), 'Num++': (0, 0x6B)}
        for text, expected in examples.items():
            with self.subTest(text=text):
                canonical, modifiers, key = parse_hotkey(text)
                self.assertEqual((modifiers, key), expected)
                self.assertEqual(parse_hotkey(canonical)[1:], expected)
                self.assertEqual(validate_preferences({**DEFAULTS, 'hotkey': text})['hotkey'], canonical)

    def test_cyrillic_layout_records_the_same_physical_letter(self):
        event = QKeyEvent(QEvent.Type.KeyPress, 0x0424, Qt.KeyboardModifier.ControlModifier, 0, 0x41, 0, 'ф')
        self.assertEqual(event_hotkey(event), 'Ctrl+A')

    def test_capture_records_combination_and_closes(self):
        dialog = HotkeyCaptureDialog()
        dialog.show()
        self.app.processEvents()
        QTest.keyClick(dialog, Qt.Key.Key_H, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.key_name, 'Ctrl+Shift+H')
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_modifier_alone_waits_and_cancel_keeps_previous_assignment(self):
        button = HotkeyButton()
        button.set_hotkey('Ctrl+H')
        dialog = HotkeyCaptureDialog()
        dialog.show()
        self.app.processEvents()
        QTest.keyClick(dialog, Qt.Key.Key_Control)
        self.assertIsNone(dialog.key_name)
        self.assertTrue(dialog.isVisible())
        dialog.reject()
        self.assertEqual(button.key_name, 'Ctrl+H')
        dialog.deleteLater()
        button.deleteLater()

    def test_escape_and_disable_are_explicit_choices(self):
        dialog = HotkeyCaptureDialog()
        dialog.show()
        self.app.processEvents()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertEqual(dialog.key_name, 'Esc')
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.deleteLater()
        dialog = HotkeyCaptureDialog()
        dialog.disable_hotkey()
        self.assertEqual(dialog.key_name, 'disabled')
        dialog.deleteLater()

    def test_invalid_and_multi_step_shortcuts_are_rejected(self):
        for text in ('', 'Ctrl', 'Ctrl+K, Ctrl+C', 'NotAKey'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hotkey(text)

    def test_global_registration_receives_modifiers_and_letter(self):
        api = Mock()
        api.RegisterHotKey.return_value = True
        manager = WindowHotkey(self.app, api=api)
        window = CarleoneWindow()
        try:
            self.assertTrue(manager.attach(window, 'Ctrl+Shift+H'))
            api.RegisterHotKey.assert_called_once_with(None, HOTKEY_ID, MOD_NOREPEAT | 6, 0x48)
        finally:
            manager.stop()
            self.app.removeNativeEventFilter(manager)
            self.app.aboutToQuit.disconnect(manager.stop)
            window.close()
            window.deleteLater()


if __name__ == '__main__':
    unittest.main()
