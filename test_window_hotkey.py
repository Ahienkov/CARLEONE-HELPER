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
            toggle.assert_called_once()
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

    def test_visible_helper_hides_even_when_game_keeps_foreground(self):
        with patch.object(self.window, 'isActiveWindow', return_value=False):
            self.manager.activate()
        self.assertFalse(self.window.isVisible())
        self.api.SetWindowPos.assert_not_called()

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
        self.window.hide()
        self.manager.activate()
        self.api.SetWindowPos.assert_called_once_with(int(self.window.winId()), 0, 0, 0, 0, 0, 0x53)

    def test_native_message_after_polling_keeps_game_foreground_without_second_toggle(self):
        self.enable_polling()
        self.held.add(VK_F4)
        self.window.hide()
        with patch.object(self.window, 'toggle_from_hotkey', wraps=self.window.toggle_from_hotkey) as toggle:
            self.manager.poll_keyboard()
            self.api.SetForegroundWindow.reset_mock()
            message = wintypes.MSG()
            message.message, message.wParam = WM_HOTKEY, HOTKEY_ID
            self.manager.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(message))
            toggle.assert_called_once()
            self.assertTrue(self.window.isVisible())
            self.api.SetForegroundWindow.assert_not_called()
            self.api.SetWindowPos.assert_called_with(int(self.window.winId()), -1, 0, 0, 0, 0, 0x53)

    def test_hotkey_shows_panel_without_requesting_keyboard_activation(self):
        self.prepare_return_window()
        self.window.hide()
        with patch.object(self.window, 'activateWindow') as activate:
            self.manager.activate()
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertFalse(self.window.search.hasFocus())
        activate.assert_not_called()
        self.api.SetForegroundWindow.assert_not_called()
        self.api.SetWindowPos.assert_called_once_with(int(self.window.winId()), -1, 0, 0, 0, 0, 0x53)

    def test_passive_show_hide_cycle_does_not_switch_foreground(self):
        self.prepare_return_window()
        self.window.hide()
        for tick in (10, 11):
            with patch('window_hotkey.time.monotonic', return_value=tick):
                self.manager.activate()
        self.assertFalse(self.window.isVisible())
        self.api.SetForegroundWindow.assert_not_called()

    def test_privilege_warning_changes_with_foreground_application(self):
        self.enable_polling()
        self.manager.access_check = Mock()
        self.manager.access_check.blocked.return_value = True
        self.manager.poll_keyboard()
        self.assertIn('администратора', self.window.hotkey_hint.text())
        self.manager.last_access_check = float('-inf')
        self.manager.access_check.blocked.return_value = False
        self.manager.poll_keyboard()
        self.assertNotIn('администратора', self.window.hotkey_hint.text())

    def prepare_return_window(self, handle=777, pid=888):
        self.api.IsWindow.return_value = True
        self.api.IsWindowVisible.return_value = True
        def window_pid(window, output):
            output._obj.value = pid
            return 1
        self.api.GetWindowThreadProcessId.side_effect = window_pid
        self.api.GetForegroundWindow.return_value = handle

    def test_hiding_returns_input_to_previous_game_before_handler_returns(self):
        self.prepare_return_window()
        self.window.hide()
        with patch('window_hotkey.time.monotonic', return_value=10):
            self.manager.activate()
        self.assertTrue(self.window.isVisible())
        self.api.SetForegroundWindow.reset_mock()
        self.api.GetForegroundWindow.return_value = int(self.window.winId())
        visible_at_restore = []
        self.api.SetForegroundWindow.side_effect = lambda handle: visible_at_restore.append(self.window.isVisible()) or True
        with patch('window_hotkey.time.monotonic', return_value=11):
            self.manager.activate()
        self.assertFalse(self.window.isVisible())
        self.api.SetForegroundWindow.assert_called_once_with(777)
        self.assertEqual(visible_at_restore, [True])

    def test_late_native_message_retries_return_to_game_without_reopening(self):
        self.enable_polling()
        self.prepare_return_window()
        self.manager.return_window = (777, 888)
        self.api.GetForegroundWindow.return_value = int(self.window.winId())
        self.window.hide()
        self.manager.key_down = True
        message = wintypes.MSG()
        message.message, message.wParam = WM_HOTKEY, HOTKEY_ID
        self.manager.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(message))
        self.assertFalse(self.window.isVisible())
        self.api.SetForegroundWindow.assert_called_once_with(777)

    def test_closed_hidden_or_reused_return_window_is_not_activated(self):
        for exists, visible, pid in ((False, True, 888), (True, False, 888), (True, True, 999)):
            with self.subTest(exists=exists, visible=visible, pid=pid):
                self.prepare_return_window(pid=pid)
                self.api.IsWindow.return_value = exists
                self.api.IsWindowVisible.return_value = visible
                self.manager.return_window = (777, 888)
                self.manager.restore_foreground()
                self.api.SetForegroundWindow.assert_not_called()
                self.assertIsNone(self.manager.return_window)

    def test_hiding_releases_own_mouse_grab(self):
        grabber = Mock()
        grabber.window.return_value = self.window
        with patch('main.QWidget.mouseGrabber', return_value=grabber):
            self.window.toggle_from_hotkey(foreground=True)
        grabber.releaseMouse.assert_called_once()
        self.assertFalse(self.window.isVisible())

    def test_return_focus_failure_retries_after_hiding(self):
        self.prepare_return_window()
        self.manager.return_window = (777, 888)
        self.api.GetForegroundWindow.return_value = int(self.window.winId())
        visible_at_restore = []
        def restore(handle):
            visible_at_restore.append(self.window.isVisible())
            return len(visible_at_restore) > 1
        self.api.SetForegroundWindow.side_effect = restore
        self.manager.activate()
        self.assertFalse(self.window.isVisible())
        self.assertEqual(visible_at_restore, [True, False])

    def test_mouse_is_released_before_foreground_is_returned(self):
        grabber = Mock()
        grabber.window.return_value = self.window
        def before_hide():
            self.assertTrue(self.window.isVisible())
            grabber.releaseMouse.assert_called_once()
        with patch('main.QWidget.mouseGrabber', return_value=grabber):
            self.window.toggle_from_hotkey(foreground=True, before_hide=before_hide)
        self.assertFalse(self.window.isVisible())

    def test_hotkey_reopens_and_hides_without_clicking_search(self):
        self.window.hide()
        with patch.object(self.window, 'isActiveWindow', return_value=False):
            for tick in (10, 11, 12, 13):
                with patch('window_hotkey.time.monotonic', return_value=tick):
                    self.manager.activate()
                self.assertEqual(self.window.isVisible(), tick % 2 == 0)
                self.assertFalse(self.window.search.hasFocus())
        self.window.toggle_from_hotkey(foreground=False)
        self.window.activateWindow()
        self.app.processEvents()
        from PySide6.QtTest import QTest
        QTest.mouseClick(self.window.search, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertIs(self.window.focusWidget(), self.window.search)

    def test_diagnostic_records_return_result_without_cursor_coordinates(self):
        import tempfile
        import json
        from pathlib import Path
        self.manager.diagnostics = True
        self.api.GetCursorInfo.return_value = False
        self.manager.return_window = (777, 888)
        with tempfile.TemporaryDirectory() as directory:
            with patch('window_hotkey.Path', return_value=Path(directory) / 'window_hotkey.py'):
                self.manager.record_diagnostic('return_focus', target=777, accepted=False)
            record = json.loads((Path(directory) / '.hotkey-debug.jsonl').read_text())
        self.assertEqual(record['event'], 'return_focus')
        self.assertEqual(record['target'], 777)
        self.assertFalse(record['accepted'])
        self.assertIsNone(record['cursor_visible'])
        self.assertNotIn('ptScreenPos', record)


if __name__ == '__main__':
    unittest.main()
