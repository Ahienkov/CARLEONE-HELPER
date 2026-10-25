"""Windows F4 hotkey shared by application windows, including live refreshes."""
import ctypes
import sys
import weakref
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4348
VK_F4 = 0x73
MOD_NOREPEAT = 0x4000


class WindowHotkey(QAbstractNativeEventFilter):
    def __init__(self, app, api=None):
        super().__init__()
        self.app = app
        self.target = None
        self.registered = False
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

    def attach(self, window):
        self.target = weakref.ref(window)
        if self.api is None:
            return False
        if not self.registered:
            self.registered = bool(self.api.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F4))
        if not self.registered:
            window.status.setText("F4 занята другим приложением · Глобальный вызов недоступен")
        window.hotkey_hint.setText("F4 — показать / скрыть" if self.registered else "F4 занята другой программой")
        return self.registered

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
    if not hasattr(app, "window_hotkey"):
        app.window_hotkey = WindowHotkey(app)
    return app.window_hotkey
