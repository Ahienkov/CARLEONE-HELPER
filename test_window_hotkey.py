import ctypes
import os
import unittest
from ctypes import wintypes
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app_refresh import reload_application
from main import CarleoneWindow
from window_hotkey import HOTKEY_ID, MOD_NOREPEAT, VK_F4, WM_HOTKEY, WindowHotkey


class HotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.previous = getattr(self.app, 'window_hotkey', None)
        self.api = Mock()
        self.api.RegisterHotKey.return_value = True
        self.api.GetForegroundWindow.return_value = 0
        self.manager = WindowHotkey(self.app, api=self.api)
        self.app.window_hotkey = self.manager
        self.window = CarleoneWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.manager.stop()
        self.app.removeNativeEventFilter(self.manager)
        self.app.aboutToQuit.disconnect(self.manager.stop)
        if self.previous is not None:
            self.app.window_hotkey = self.previous
        else:
            del self.app.window_hotkey

    def test_native_f4_message_and_frameless_window(self):
        self.api.RegisterHotKey.assert_called_once_with(None, HOTKEY_ID, MOD_NOREPEAT, VK_F4)
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        message = wintypes.MSG()
        message.message, message.wParam = WM_HOTKEY, HOTKEY_ID
        with patch.object(self.window, 'toggle_from_hotkey') as toggle:
            handled = self.manager.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(message))
            self.assertEqual(handled, (True, 0))
            toggle.assert_called_once()
        self.window.close()
        self.api.UnregisterHotKey.assert_called_once_with(None, HOTKEY_ID)

    def test_hide_and_restore_from_minimized(self):
        with patch.object(self.window, 'isActiveWindow', return_value=True):
            self.window.toggle_from_hotkey()
        self.assertFalse(self.window.isVisible())
        self.window.toggle_from_hotkey()
        self.assertTrue(self.window.isVisible())
        self.window.showMinimized()
        self.window.toggle_from_hotkey()
        self.assertFalse(self.window.isMinimized())
        self.assertTrue(self.window.isVisible())

    def test_refresh_transfers_target_without_losing_registration(self):
        replacement = reload_application(self.window)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertIs(self.manager.target(), replacement)
        self.api.RegisterHotKey.assert_called_once()
        self.api.UnregisterHotKey.assert_not_called()

    def test_busy_key_is_reported(self):
        self.manager.stop()
        self.api.RegisterHotKey.return_value = False
        self.assertFalse(self.manager.attach(self.window))
        self.assertIn('занята', self.window.hotkey_hint.text())

    def enable_polling(self):
        self.held = set()
        self.manager.keyboard_api = self.api
        self.api.GetAsyncKeyState.side_effect = lambda key: 0x8000 if key in self.held else 0
        self.manager.attach(self.window)

    def test_polling_recovers_missing_native_message_once_per_press(self):
        self.enable_polling()
        with patch.object(self.window, 'toggle_from_hotkey') as toggle, patch('window_hotkey.time.monotonic', return_value=10):
            self.held.add(VK_F4)
            self.manager.poll_keyboard()
            self.manager.poll_keyboard()
            message = wintypes.MSG()
            message.message, message.wParam = WM_HOTKEY, HOTKEY_ID
            with patch('window_hotkey.time.monotonic', return_value=12):
                self.manager.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(message))
            toggle.assert_called_once_with(foreground=False)
        self.held.clear()
        self.manager.poll_keyboard()
        with patch.object(self.window, 'toggle_from_hotkey') as toggle, patch('window_hotkey.time.monotonic', return_value=11):
            self.held.add(VK_F4)
            self.manager.poll_keyboard()
            toggle.assert_called_once()

    def test_native_message_then_poll_does_not_hide_window_again(self):
        self.enable_polling()
        self.held.add(VK_F4)
        with patch.object(self.window, 'toggle_from_hotkey') as toggle:
            self.manager.activate()
            self.manager.poll_keyboard()
            toggle.assert_called_once()

    def test_polling_respects_modifiers_and_suspension(self):
        self.enable_polling()
        self.manager.attach(self.window, 'Ctrl+H')
        with patch.object(self.window, 'toggle_from_hotkey') as toggle:
            self.held.add(0x48)
            self.manager.poll_keyboard()
            toggle.assert_not_called()
            self.held.clear()
            self.manager.poll_keyboard()
            self.held.update((0x48, 0x11))
            self.manager.poll_keyboard()
            toggle.assert_called_once()
            self.manager.stop()
            self.assertFalse(self.manager.poll_timer.isActive())
            self.held.clear()
            self.manager.poll_keyboard()
            self.held.update((0x48, 0x11))
            self.manager.poll_keyboard()
            toggle.assert_called_once()

    def test_stale_qt_active_state_does_not_hide_window_over_game(self):
        with patch.object(self.window, 'isActiveWindow', return_value=True):
            self.manager.activate()
        self.assertTrue(self.window.isVisible())
        self.api.SetWindowPos.assert_called_once_with(int(self.window.winId()), -1, 0, 0, 0, 0, 0x43)
        self.api.SetForegroundWindow.assert_called_once()

    def test_foreground_helper_hides_without_raising_it_again(self):
        self.api.GetForegroundWindow.return_value = int(self.window.winId())
        self.manager.activate()
        self.assertFalse(self.window.isVisible())
        self.api.SetWindowPos.assert_not_called()

    def test_held_key_when_resuming_does_not_activate(self):
        self.enable_polling()
        self.manager.stop()
        self.held.add(VK_F4)
        self.manager.attach(self.window)
        with patch.object(self.window, 'toggle_from_hotkey') as toggle:
            self.manager.poll_keyboard()
            toggle.assert_not_called()

    def test_topmost_disabled_setting_is_preserved(self):
        self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.manager.activate()
        self.api.SetWindowPos.assert_called_once_with(int(self.window.winId()), 0, 0, 0, 0, 0, 0x43)


if __name__ == '__main__':
    unittest.main()
