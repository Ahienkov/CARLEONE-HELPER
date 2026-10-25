"""Stable entry point for source launches and the portable Windows build."""
import ctypes
import importlib
import os
import runpy
import sys
from pathlib import Path

# These explicit imports make the portable runtime include external dependencies.
import requests
import bs4
from PySide6 import QtCore, QtGui, QtWidgets


ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    if '--self-test' in sys.argv:
        try:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            namespace = runpy.run_path(str(ROOT / 'main.py'), run_name='carleone_self_test')
            app = QtWidgets.QApplication([])
            window = namespace['CarleoneWindow']()
            if not window.current_records() or window.windowIcon().isNull():
                raise RuntimeError('Portable app assets or data missing')
            window.close()
        except Exception:
            import traceback
            (ROOT / 'self-test-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise SystemExit(1)
        raise SystemExit(0)
    from elevation import ensure_administrator
    if not ensure_administrator():
        return
    try:
        updater = importlib.import_module('software_update')
        updater.apply_pending(ROOT)
        importlib.invalidate_caches()
        for path in ROOT.glob('__pycache__/*.pyc'):
            path.unlink(missing_ok=True)
    except Exception as error:
        if sys.platform == 'win32':
            ctypes.windll.user32.MessageBoxW(None, f'Обновление не применено. Будет запущена сохранённая версия.\n{error}', 'GTA 5 RP HELPER', 0x30)
    runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')


if __name__ == '__main__':
    main()
