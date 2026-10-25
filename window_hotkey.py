"""Windows global hotkey shared by application windows and live refreshes."""
import ctypes
import sys
import weakref
import time
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from hotkey_config import parse_hotkey, display_hotkey


WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4348
VK_F4 = 0x73
MOD_NOREPEAT = 0x4000


class WindowHotkey(QAbstractNativeEventFilter):
    api_version = 3
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
            self.api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            self.api.SetWindowPos.restype = wintypes.BOOL
            self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
            self.api.GetAsyncKeyState.restype = ctypes.c_short
            self.keyboard_api = self.api
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
        self.key_down = False
        if self.registered:
            self.api.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False

    def poll_keyboard(self):
        if not self.registered or self.keyboard_api is None:
            return
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
        foreground = None if self.api is None else self.api.GetForegroundWindow() == int(window.winId())
        window.toggle_from_hotkey(foreground=foreground)
        if window.isVisible() and self.api is not None:
            handle = int(window.winId())
            # Reassert the native Z order; Qt's active-window state can lag while
            # switching away from a game. Keep the user's always-on-top setting.
            top = -1 if window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint else 0
            self.api.SetWindowPos(handle, top, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
            self.api.SetForegroundWindow(handle)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            native = wintypes.MSG.from_address(int(message))
            if native.message == WM_HOTKEY and native.wParam == HOTKEY_ID and self.registered:
                if self.keyboard_api is None or not self.key_down:
                    self.activate()
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
        previous.registered = False
        if hasattr(previous, 'poll_timer'):
            previous.poll_timer.stop()
        app.removeNativeEventFilter(previous)
        try:
            app.aboutToQuit.disconnect(previous.stop)
        except (RuntimeError, TypeError):
            pass
        app.window_hotkey = manager
    if not hasattr(app, "window_hotkey"):
        app.window_hotkey = WindowHotkey(app)
    return app.window_hotkey
