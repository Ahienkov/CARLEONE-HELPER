"""Installation-local credentials protected by Windows DPAPI, bound to the release."""
import base64
import ctypes
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path


def windows_crypt(data, entropy, decrypt=False):
    if sys.platform != 'win32':
        raise OSError('Сохранение входа поддерживается только в Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    source_buffer, salt_buffer = ctypes.create_string_buffer(data), ctypes.create_string_buffer(entropy)
    source = Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    salt = Blob(len(entropy), ctypes.cast(salt_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt32, kernel32 = ctypes.WinDLL('crypt32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes, kernel32.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, ctypes.byref(salt), None, None, 1, ctypes.byref(output)):
        raise OSError('Windows не смогла открыть сохранённый вход. Войдите снова.')
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


class SessionStore:
    def __init__(self, root, service_url, protect=None, unprotect=None):
        self.root = Path(root).resolve()
        self.path = self.root / '.discord-session.json'
        self.version = str(json.loads((self.root / 'version.json').read_text(encoding='utf-8-sig'))['version'])
        self.entropy = hashlib.sha256((str(self.root).casefold() + '|' + service_url).encode()).digest()
        self.protect = protect or (lambda data: windows_crypt(data, self.entropy))
        self.unprotect = unprotect or (lambda data: windows_crypt(data, self.entropy, decrypt=True))

    def load(self):
        try:
            if self.path.stat().st_size > 16384:
                return None
            outer = json.loads(self.path.read_text(encoding='utf-8'))
            data = json.loads(self.unprotect(base64.b64decode(outer['protected'], validate=True)))
            if data['release_id'] != self.version or not isinstance(data['session_key'], str):
                return None
            if len(data['session_key']) < 32 or not 20 <= len(data['install_id']) <= 100:
                return None
            return data
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, session):
        encrypted = self.protect(json.dumps({**session, 'release_id': self.version}, ensure_ascii=False).encode())
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'protected': base64.b64encode(encrypted).decode()}), encoding='utf-8')
        os.replace(temporary, self.path)

    def clear(self):
        self.path.unlink(missing_ok=True)

    def new_identity(self):
        return dict(install_id=secrets.token_urlsafe(32), release_id=self.version)
