"""Require an elevated Windows process using the normal UAC consent flow."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
from ctypes import wintypes


def ensure_administrator(api=None):
    """True only when this process may run the UI; otherwise request a new one."""
    if sys.platform != 'win32':
        return True
    if api is None:
        api = ctypes.WinDLL('shell32', use_last_error=True)
        api.IsUserAnAdmin.argtypes = []
        api.IsUserAnAdmin.restype = wintypes.BOOL
        api.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                      wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
        api.ShellExecuteW.restype = wintypes.HINSTANCE
    if api.IsUserAnAdmin():
        return True
    frozen = getattr(sys, 'frozen', False)
    root = Path(sys.executable).resolve().parent if frozen else Path(__file__).resolve().parent
    executable = Path(sys.executable)
    arguments = sys.argv[1:]
    if not frozen:
        pythonw = executable.with_name('pythonw.exe')
        if pythonw.exists():
            executable = pythonw
        arguments = [str(root / 'bootstrap.py'), *arguments]
    # A PyInstaller restart must initialize its own runtime rather than inherit
    # the bootloader state of the process which is about to exit.
    previous = os.environ.get('PYINSTALLER_RESET_ENVIRONMENT')
    try:
        if frozen:
            os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        api.ShellExecuteW(None, 'runas', str(executable), subprocess.list2cmdline(arguments), str(root), 1)
    finally:
        if previous is None:
            os.environ.pop('PYINSTALLER_RESET_ENVIRONMENT', None)
        else:
            os.environ['PYINSTALLER_RESET_ENVIRONMENT'] = previous
    # Whether consent succeeded or was cancelled, never continue with lower
    # privileges or retry the consent prompt in a loop.
    return False
