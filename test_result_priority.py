import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from main import CarleoneWindow, law_punishment_priority
from server_registry import SERVER_NAMES


class ResultPriorityTests(unittest.TestCase):
    def test_reference_messages_are_not_penalties(self):
        for punishment in ('', 'Общая норма — отдельная санкция не выделяется.',
                           'Санкция не выделена автоматически. См. полный текст выше.',
                           'Справочная информация из кодекса.'):
            self.assertEqual(law_punishment_priority(dict(number='1', category='Уголовный', punishment=punishment)), 3)

    def test_catalog_and_search_priorities_on_every_server(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'test.ini'), QSettings.Format.IniFormat)
            window = CarleoneWindow(selection_settings=settings, favorites_settings=settings)
            try:
                for server in SERVER_NAMES:
                    window.server.setCurrentIndex(window.server.findData(server))
                    for query in ('', 'оружие', '6.1'):
                        window.search.setText(query)
                        window.update_search()
                        ranks = [law_punishment_priority(a) for a in window.filtered_articles]
                        self.assertEqual(ranks, sorted(ranks), (server, query))
                    window.search.clear()
                # Rules keep their existing number/relevance ordering.
                window.mode_selector.setCurrentIndex(1)
                window.search.setText('1.17')
                window.update_search()
                self.assertEqual(window.filtered_articles[0]['number'], '1.17')
            finally:
                window.close()
                window.deleteLater()
                app.processEvents()


if __name__ == '__main__':
    unittest.main()
