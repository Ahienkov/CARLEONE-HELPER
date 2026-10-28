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


def verify_distribution(root=ROOT):
    """Exercise every lazy section using disposable settings, in the actual EXE."""
    import tempfile

    namespace = runpy.run_path(str(root / 'main.py'), run_name='carleone_self_test')
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    verified = []
    with tempfile.TemporaryDirectory(prefix='carleone-self-test-') as directory:
        settings = QtCore.QSettings(str(Path(directory) / 'test.ini'), QtCore.QSettings.Format.IniFormat)
        for mode in ('laws', 'rules', 'earnings', 'notepad'):
            window = namespace['CarleoneWindow'](initial_mode=mode, selection_settings=settings,
                                                 earnings_settings=settings, notepad_settings=settings)
            try:
                if window.windowIcon().isNull():
                    raise RuntimeError('Portable app icon missing')
                if mode in ('laws', 'rules') and not window.current_records():
                    raise RuntimeError(f'Portable app data missing: {mode}')
                if mode == 'earnings':
                    panel = window.earnings_panel
                    if panel is None or panel.tabs.count() != 2:
                        raise RuntimeError('Earnings/reselling panels missing')
                    entry = panel.store.add('murrieta', 'income', 100, 'Distribution self-test')
                    deal = panel.reselling.store.add('murrieta', 'Distribution self-test', 50, 5, 80)
                    if not entry['id'] or not deal['id']:
                        raise RuntimeError('UUID generation failed in packaged runtime')
                    panel.refresh()
                    if panel.table.rowCount() != 1:
                        raise RuntimeError('Earnings table did not load the test entry')
                if mode == 'notepad':
                    panel = window.notepad_panel
                    if panel is None:
                        raise RuntimeError('Notepad panel missing')
                    panel.editor.setPlainText('Проверка сборки')
                    if not panel.flush() or panel.store.load()['tabs'][0]['text'] != 'Проверка сборки':
                        raise RuntimeError('Packaged notepad could not save')
                verified.append(mode)
            finally:
                window.close()
                window.deleteLater()
                QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    return verified


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    if '--self-test' in sys.argv:
        try:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            verified = verify_distribution()
            (ROOT / 'self-test-success.txt').write_text(
                'PASS: ' + ', '.join(verified) + '; income/reselling UUIDs; isolated storage', encoding='utf-8')
        except Exception:
            import traceback
            (ROOT / 'self-test-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise SystemExit(1)
        raise SystemExit(0)
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
