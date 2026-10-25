"""Read-only diagnosis of the Windows input privilege boundary."""
import ctypes
import os
from ctypes import wintypes


class ForegroundAccess:
    def __init__(self, user32):
        self.user32 = user32
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.security = ctypes.WinDLL('advapi32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        self.security.OpenProcessToken.restype = wintypes.BOOL
        self.security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                     wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.security.GetTokenInformation.restype = wintypes.BOOL
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.own_elevated = self.process_elevated(os.getpid())

    def process_elevated(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid)
        if not process:
            return None
        token = wintypes.HANDLE()
        try:
            if not self.security.OpenProcessToken(process, 0x0008, ctypes.byref(token)):
                return None
            try:
                elevation, size = wintypes.DWORD(), wintypes.DWORD()
                if not self.security.GetTokenInformation(token, 20, ctypes.byref(elevation),
                                                         ctypes.sizeof(elevation), ctypes.byref(size)):
                    return None
                return bool(elevation.value)
            finally:
                self.kernel.CloseHandle(token)
        finally:
            self.kernel.CloseHandle(process)

    def blocked(self):
        if self.own_elevated is not False:
            return False
        foreground = self.user32.GetForegroundWindow()
        if not foreground:
            return False
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
        return bool(pid.value and self.process_elevated(pid.value) is True)
