"""Windows global hotkey shared by application windows and live refreshes."""
import ctypes
import sys
import weakref
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from hotkey_config import parse_hotkey, display_hotkey


WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4348
VK_F4 = 0x73
MOD_NOREPEAT = 0x4000


class WindowHotkey(QAbstractNativeEventFilter):
    api_version = 2
    def __init__(self, app, api=None):
        super().__init__()
        self.app = app
        self.target = None
        self.registered = False
        self.key_name = 'F4'
        self.api = api
        if self.api is None and sys.platform == "win32" and app.platformName() != "offscreen":
            self.api = ctypes.WinDLL("user32", use_last_error=True)
            self.api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.api.RegisterHotKey.restype = wintypes.BOOL
            self.api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.api.UnregisterHotKey.restype = wintypes.BOOL
            self.api.SetForegroundWindow.argtypes = [wintypes.HWND]
            self.api.SetForegroundWindow.restype = wintypes.BOOL
        app.installNativeEventFilter(self)
        app.aboutToQuit.connect(self.stop)

    def attach(self, window, key_name=None):
        name, modifiers, virtual_key = parse_hotkey(key_name if key_name is not None else self.key_name)
        if name != self.key_name:
            self.stop()
            self.key_name = name
        self.target = weakref.ref(window)
        if self.key_name == 'disabled':
            window.hotkey_hint.setText('Горячая клавиша отключена')
            return True
        if self.api is None:
            window.hotkey_hint.setText(f'{display_hotkey(self.key_name)} — показать / скрыть')
            return True
        if not self.registered:
            self.registered = bool(self.api.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT | modifiers, virtual_key))
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
        if self.registered:
            self.api.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False

    def activate(self):
        window = self.target() if self.target else None
        if window is None or not isValid(window):
            return
        window.toggle_from_hotkey()
        if window.isVisible() and self.api is not None:
            self.api.SetForegroundWindow(int(window.winId()))

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            native = wintypes.MSG.from_address(int(message))
            if native.message == WM_HOTKEY and native.wParam == HOTKEY_ID and self.registered:
                self.activate()
                return True, 0
        return False, 0


def application_hotkey():
    app = QApplication.instance()
    previous = getattr(app, 'window_hotkey', None)
    if previous is not None and getattr(previous, 'api_version', 0) != WindowHotkey.api_version:
        # Upgrade the service of an already running pre-settings version without
        # releasing its Windows registration during a live window refresh.
        manager = WindowHotkey(app, api=previous.api)
        manager.registered = previous.registered
        manager.target = previous.target
        manager.key_name = getattr(previous, 'key_name', 'F4')
        previous.registered = False
        app.removeNativeEventFilter(previous)
        try:
            app.aboutToQuit.disconnect(previous.stop)
        except (RuntimeError, TypeError):
            pass
        app.window_hotkey = manager
    if not hasattr(app, "window_hotkey"):
        app.window_hotkey = WindowHotkey(app)
    return app.window_hotkey
