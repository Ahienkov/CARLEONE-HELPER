"""Application-level background checker; survives window refresh and hide/show."""
import threading
import weakref
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, QProcess, QProcessEnvironment
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from forum_sync import ForumSync
from software_update import check_for_update


def restart_application():
    root = Path(__file__).resolve().parent
    process = QProcess()
    if getattr(sys, 'frozen', False):
        process.setProgram(sys.executable)
    else:
        python = root / '.venv' / 'Scripts' / 'pythonw.exe'
        process.setProgram(str(python) if python.exists() else sys.executable)
        process.setArguments([str(root / 'bootstrap.py')])
    process.setWorkingDirectory(str(root))
    environment = QProcessEnvironment.systemEnvironment()
    environment.insert('PYINSTALLER_RESET_ENVIRONMENT', '1')
    process.setProcessEnvironment(environment)
    started, _pid = process.startDetached()
    if started:
        QApplication.instance().quit()
    return started


class ForumUpdates(QObject):
    completed = Signal(object)
    progress = Signal(str)

    def __init__(self, app):
        super().__init__(app)
        self.target = None
        self.running = False
        self.started = False
        self.stopping = threading.Event()
        self.text = "Форум: ожидание"
        self.detail = "Форум проверяется при запуске и по кнопке ↻. В остальное время используется локальная база."
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.check_now)
        self.completed.connect(self.finish)
        self.progress.connect(self.show_progress)
        app.aboutToQuit.connect(self.stop)

    def window(self):
        window = self.target() if self.target else None
        return window if window is not None and isValid(window) else None

    def attach(self, window):
        self.target = weakref.ref(window)
        self.update_label()
        if not self.started and QApplication.platformName() != "offscreen":
            self.started = True
            if getattr(window, 'preferences', {}).get('check_on_startup', True):
                self.start_timer.start(2000)
            else:
                self.text = 'Форум: локальная база'
                self.detail = 'Проверка при запуске отключена. Проверить обновления можно кнопкой ↻.'
                self.update_label()

    def update_label(self):
        window = self.window()
        if window is not None:
            window.forum_status.setText(self.text)
            window.forum_status.setToolTip(self.detail)
            window.forum_status.setEnabled(not self.running)

    def show_progress(self, topic):
        self.detail = f"Проверка форума в фоне: {topic}"
        self.update_label()

    def check_now(self):
        self.start_timer.stop()
        if self.running or self.stopping.is_set():
            return
        self.running = True
        self.text = "Форум: проверка…"
        self.update_label()
        threading.Thread(target=self.run_check, daemon=True, name="ForumUpdates").start()

    def run_check(self):
        application = {}
        try:
            try:
                self.safe_progress('Проверка версии GTA 5 RP HELPER')
                application = check_for_update()
            except Exception as error:
                application = {'state': 'error', 'detail': str(error)}
            if application.get('state') == 'ready':
                result = {'application': application}
            else:
                result = ForumSync(stop_event=self.stopping, progress=self.safe_progress).run()
                result['application'] = application
        except Exception as error:
            result = {"error": str(error), 'application': application}
        if not self.stopping.is_set():
            try:
                self.completed.emit(result)
            except RuntimeError:
                pass

    def safe_progress(self, message):
        if not self.stopping.is_set():
            try:
                self.progress.emit(message)
            except RuntimeError:
                pass

    def finish(self, result):
        self.running = False
        application = result.get('application', {})
        if application.get('state') == 'ready':
            self.text = 'Приложение: обновление…'
            self.detail = f"Устанавливается версия {application['version']}. Окно откроется автоматически."
            self.update_label()
            if not restart_application():
                self.text = 'Обновление загружено'
                self.detail = 'Новая версия применится при следующем запуске приложения.'
                self.update_label()
            return
        if "error" in result:
            self.text = "Форум: ошибка проверки"
            self.detail = "Используется сохранённая база. Повторить проверку можно кнопкой ↻.\n" + result["error"]
        else:
            changed = result["changed_files"]
            self.text = "Форум: обновлено" if changed else "Форум: актуально"
            self.detail = "Проверка завершена. Используется локальная база. Повторная проверка — только при запуске или по кнопке ↻."
            window = self.window()
            if changed and window is not None:
                try:
                    window.apply_forum_update(result["catalog"])
                except Exception as error:
                    self.text = "Форум: данные сохранены"
                    self.detail = f"Данные сохранены, но интерфейс не обновлён. Нажмите ↻.\n{error}"
        self.update_label()
        if application.get('state') == 'error':
            self.detail += '\nНе удалось проверить новую версию приложения: ' + application['detail']
        elif application.get('state') == 'runtime_required':
            self.text = 'Доступна новая сборка'
            self.detail += f"\nВерсия {application['version']} требует новую сборку: {application['url']}"
        self.update_label()

    def stop(self):
        self.stopping.set()
        self.start_timer.stop()


def application_updates():
    app = QApplication.instance()
    if not hasattr(app, "forum_updates"):
        app.forum_updates = ForumUpdates(app)
    return app.forum_updates
