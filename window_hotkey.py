"""Windows global hotkey shared by application windows and live refreshes."""
import ctypes
import sys
import weakref
import time
import json
from pathlib import Path
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from hotkey_config import parse_hotkey, display_hotkey
from i18n import tr


WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4348
VK_F4 = 0x73
MOD_NOREPEAT = 0x4000


class CursorInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class WindowHotkey(QAbstractNativeEventFilter):
    api_version = 8
    def __init__(self, app, api=None, keyboard_api=None):
        super().__init__()
        self.app = app
        self.target = None
        self.registered = False
        self.key_name = 'F4'
        self.modifiers, self.virtual_key = 0, VK_F4
        self.api = api
        self.keyboard_api = keyboard_api
        self.key_down = False
        self.last_activation = float('-inf')
        self.return_window = None
        self.diagnostics = False
        self.trace_generation = 0
        self.access_check = None
        self.last_access_check = float('-inf')
        self.poll_timer = QTimer()
        self.poll_timer.setInterval(20)
        self.poll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.poll_timer.timeout.connect(self.poll_keyboard)
        if self.api is None and sys.platform == "win32" and app.platformName() != "offscreen":
            self.api = ctypes.WinDLL("user32", use_last_error=True)
        if isinstance(self.api, ctypes.CDLL):
            # Also configure a user32 handle inherited from the previous service
            # during live refresh (ctypes otherwise truncates HWND on 64-bit).
            self.api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.api.RegisterHotKey.restype = wintypes.BOOL
            self.api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.api.UnregisterHotKey.restype = wintypes.BOOL
            self.api.SetForegroundWindow.argtypes = [wintypes.HWND]
            self.api.SetForegroundWindow.restype = wintypes.BOOL
            self.api.GetForegroundWindow.argtypes = []
            self.api.GetForegroundWindow.restype = wintypes.HWND
            self.api.IsWindow.argtypes = [wintypes.HWND]
            self.api.IsWindow.restype = wintypes.BOOL
            self.api.IsWindowVisible.argtypes = [wintypes.HWND]
            self.api.IsWindowVisible.restype = wintypes.BOOL
            self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            self.api.GetWindowThreadProcessId.restype = wintypes.DWORD
            self.api.GetCursorInfo.argtypes = [ctypes.POINTER(CursorInfo)]
            self.api.GetCursorInfo.restype = wintypes.BOOL
            self.api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            self.api.SetWindowPos.restype = wintypes.BOOL
            self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
            self.api.GetAsyncKeyState.restype = ctypes.c_short
            self.keyboard_api = self.api
            from foreground_access import ForegroundAccess
            self.access_check = ForegroundAccess(self.api)
            self.diagnostics = True
            self.record_diagnostic('service_started')
        app.installNativeEventFilter(self)
        app.aboutToQuit.connect(self.stop)

    def attach(self, window, key_name=None):
        name, modifiers, virtual_key = parse_hotkey(key_name if key_name is not None else self.key_name)
        if name != self.key_name:
            self.stop()
            self.key_name = name
        self.modifiers, self.virtual_key = modifiers, virtual_key
        self.target = weakref.ref(window)
        if self.key_name == 'disabled':
            window.hotkey_hint.setText('Горячая клавиша отключена')
            return True
        if self.api is None:
            window.hotkey_hint.setText(f'{display_hotkey(self.key_name)} — показать / скрыть')
            return True
        if not self.registered:
            self.registered = bool(self.api.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT | modifiers, virtual_key))
        if self.registered and self.keyboard_api is not None and not self.poll_timer.isActive():
            # Do not fire a shortcut still held after closing the key recorder.
            self.key_down = bool(self.keyboard_api.GetAsyncKeyState(virtual_key) & 0x8000)
            self.poll_timer.start()
        if not self.registered:
            window.status.setText(f"{self.key_name} занята другим приложением · Глобальный вызов недоступен")
        window.hotkey_hint.setText(f"{self.key_name} — показать / скрыть" if self.registered else f"{self.key_name} занята другой программой")
        return self.registered

    def try_change(self, window, key_name):
        old = self.key_name
        if self.attach(window, key_name):
            return True
        self.attach(window, old)
        return False

    def detach(self, window):
        if self.target is not None and self.target() is window:
            self.target = None
            self.stop()

    def stop(self):
        self.poll_timer.stop()
        self.trace_generation += 1
        self.key_down = False
        if self.registered:
            self.api.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False

    def poll_keyboard(self):
        if not self.registered or self.keyboard_api is None:
            return
        if self.access_check is not None and time.monotonic() - self.last_access_check >= 1:
            self.last_access_check = time.monotonic()
            window = self.target() if self.target else None
            if window is not None and isValid(window):
                blocked = self.access_check.blocked()
                window.hotkey_hint.setText(tr('{key}: активная программа запущена от администратора. Перезапустите помощник от администратора.',
                                             key=display_hotkey(self.key_name)) if blocked else
                                           f'{display_hotkey(self.key_name)} — показать / скрыть')
        modifiers, key = self.modifiers, self.virtual_key
        down = bool(self.keyboard_api.GetAsyncKeyState(key) & 0x8000)
        was_down, self.key_down = self.key_down, down
        if not down or was_down:
            return
        pressed_modifiers = 0
        for flag, keys in ((1, (0x12,)), (2, (0x11,)), (4, (0x10,)), (8, (0x5B, 0x5C))):
            if any(self.keyboard_api.GetAsyncKeyState(k) & 0x8000 for k in keys):
                pressed_modifiers |= flag
        if pressed_modifiers == modifiers:
            self.activate()

    def activate(self):
        window = self.target() if self.target else None
        if window is None or not isValid(window):
            return
        # WM_HOTKEY and the fallback may observe the same press. Never toggle twice.
        now = time.monotonic()
        if now - self.last_activation < 0.15:
            return
        self.last_activation = now
        if self.keyboard_api is not None:
            self.key_down = True
        foreground_handle = self.api.GetForegroundWindow() if self.api is not None else None
        foreground = None if self.api is None else foreground_handle == int(window.winId())
        if self.api is not None and foreground_handle and not foreground:
            pid = wintypes.DWORD()
            self.api.GetWindowThreadProcessId(foreground_handle, ctypes.byref(pid))
            self.return_window = (foreground_handle, pid.value) if pid.value else None
        self.trace_generation += 1
        hiding = window.isVisible() and not window.isMinimized()
        restored = False
        def return_input():
            nonlocal restored
            restored = self.restore_foreground()
        if hiding:
            window.toggle_from_hotkey(foreground=foreground, before_hide=return_input)
            self.record_diagnostic('hidden', restored=restored)
            self.trace_return_focus()
        else:
            window.toggle_from_hotkey(foreground=foreground)
        if window.isVisible() or not restored:
            self.raise_target(window)

    def raise_target(self, window):
        if not window.isVisible():
            self.restore_foreground()
            return
        if window.isVisible() and self.api is not None:
            handle = int(window.winId())
            # Raise only the visual panel. The game must retain keyboard/mouse
            # input until the user explicitly clicks into the helper.
            top = -1 if window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint else 0
            self.api.SetWindowPos(handle, top, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040 | 0x0010)

    def restore_foreground(self):
        # Transfer activation while we still own the foreground, BEFORE hiding.
        # After hide Windows may already have activated a different window and
        # our right to call SetForegroundWindow may have been lost.
        if self.api is None or self.return_window is None:
            return False
        handle, expected_pid = self.return_window
        if not self.api.IsWindow(handle) or not self.api.IsWindowVisible(handle):
            self.return_window = None
            return False
        pid = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value != expected_pid:
            self.return_window = None
            return False
        if self.api.GetForegroundWindow() == handle:
            return True
        accepted = bool(self.api.SetForegroundWindow(handle))
        self.record_diagnostic('return_focus', target=handle, accepted=accepted)
        return accepted

    def record_diagnostic(self, event, **fields):
        if not self.diagnostics:
            return
        cursor = CursorInfo()
        cursor.cbSize = ctypes.sizeof(cursor)
        cursor_known = self.api.GetCursorInfo(ctypes.byref(cursor))
        record = dict(event=event, revision=self.api_version, time=time.time(),
                      foreground=self.api.GetForegroundWindow(),
                      target=self.return_window[0] if self.return_window else None,
                      cursor_visible=bool(cursor.flags & 1) if cursor_known else None)
        record.update(fields)
        try:
            path = Path(__file__).with_name('.hotkey-debug.jsonl')
            if path.exists() and path.stat().st_size > 262144:
                path.replace(path.with_suffix('.jsonl.1'))
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record) + '\n')
        except OSError:
            pass  # Diagnostics must never interrupt a hotkey.

    def trace_return_focus(self):
        if not self.diagnostics:
            return
        generation = self.trace_generation
        for delay in (100, 500, 1500):
            def sample(delay=delay):
                if self.trace_generation == generation:
                    self.record_diagnostic('after_hide', delay_ms=delay)
            QTimer.singleShot(delay, sample)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            native = wintypes.MSG.from_address(int(message))
            if native.message == WM_HOTKEY and native.wParam == HOTKEY_ID and self.registered:
                if self.keyboard_api is None or not self.key_down:
                    self.activate()
                else:
                    # The fallback may have shown the panel first. A late native
                    # event must neither activate it nor toggle it again.
                    window = self.target() if self.target else None
                    if window is not None and isValid(window):
                        self.raise_target(window)
                return True, 0
        return False, 0


def application_hotkey():
    app = QApplication.instance()
    previous = getattr(app, 'window_hotkey', None)
    if previous is not None and getattr(previous, 'api_version', 0) != WindowHotkey.api_version:
        # Upgrade the service of an already running pre-settings version without
        # releasing its Windows registration during a live window refresh.
        manager = WindowHotkey(app, api=previous.api,
                               keyboard_api=getattr(previous, 'keyboard_api', previous.api))
        manager.registered = previous.registered
        manager.target = previous.target
        manager.key_name = getattr(previous, 'key_name', 'F4')
        manager.return_window = getattr(previous, 'return_window', None)
        previous.registered = False
        if hasattr(previous, 'poll_timer'):
            previous.poll_timer.stop()
        if hasattr(previous, 'trace_generation'):
            previous.trace_generation += 1
        app.removeNativeEventFilter(previous)
        try:
            app.aboutToQuit.disconnect(previous.stop)
        except (RuntimeError, TypeError):
            pass
        app.window_hotkey = manager
    if not hasattr(app, "window_hotkey"):
        app.window_hotkey = WindowHotkey(app)
    return app.window_hotkey
