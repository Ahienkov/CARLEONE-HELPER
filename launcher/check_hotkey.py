"""Brief native Windows smoke check; opens and closes its own HELPER window."""
import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from main import CarleoneWindow
from window_hotkey import application_hotkey, WM_HOTKEY, HOTKEY_ID


app = QApplication([])
window = CarleoneWindow()
window.show()
thread_id = ctypes.windll.kernel32.GetCurrentThreadId()


def send_hotkey():
    try:
        if not application_hotkey().registered:
            raise RuntimeError('F4 is already registered by another application')
        window.showMinimized()
        if not ctypes.windll.user32.PostThreadMessageW(thread_id, WM_HOTKEY, HOTKEY_ID, 0):
            raise RuntimeError('Cannot post native hotkey message')
        QTimer.singleShot(300, verify)
    except Exception as error:
        print(error, flush=True)
        window.close()
        app.exit(1)


def verify():
    success = window.isVisible() and not window.isMinimized() and application_hotkey().registered
    print('OK: F4 registered; native WM_HOTKEY restored the minimized window.' if success else 'Hotkey check failed.', flush=True)
    window.close()
    app.exit(0 if success else 1)


QTimer.singleShot(300, send_hotkey)
sys.exit(app.exec())
