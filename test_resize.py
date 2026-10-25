import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import CarleoneWindow, RESIZE_SETTLE_MS


class ResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = CarleoneWindow()
        self.window.show()
        self.window.mode_selector.setCurrentIndex(1)
        self.app.processEvents()
        QTest.qWait(RESIZE_SETTLE_MS + 100)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_rapid_resize_reflows_content_once_after_settling(self):
        w = self.window
        width = w.scroll.widget().width()
        count = w.rendered_count
        for step in range(12):
            w.resize(1150 + step * 10, 760)
            self.app.processEvents()
        self.assertTrue(w.results_width_timer.isActive())
        self.assertEqual(w.scroll.widget().width(), width)
        QTest.qWait(RESIZE_SETTLE_MS + 100)
        self.assertEqual(w.scroll.widget().width(), w.scroll.viewport().width())
        self.assertEqual(w.rendered_count, count)
        last = w.results_layout.itemAt(w.results_layout.count() - 1).widget()
        self.assertLessEqual(last.geometry().bottom(), w.scroll.widget().height())

    def test_unchanged_tab_arrangement_is_not_rebuilt(self):
        w = self.window
        w.resize(1500, 740)
        self.app.processEvents()
        QTest.qWait(RESIZE_SETTLE_MS + 100)
        with patch.object(w, 'refresh_category_visibility', wraps=w.refresh_category_visibility) as refresh:
            for width in range(1510, 1600, 10):
                w.resize(width, 740)
                self.app.processEvents()
            refresh.assert_not_called()
        with patch.object(w, 'reflow_categories') as reflow:
            w.resize(1590, 760)
            self.app.processEvents()
            reflow.assert_not_called()

    def test_resize_keeps_all_cards_reachable(self):
        w = self.window
        for width in (920, 1500, 1000):
            w.resize(width, 600)
            self.app.processEvents()
            QTest.qWait(RESIZE_SETTLE_MS + 100)
            self.assertEqual(w.scroll.widget().width(), w.scroll.viewport().width())
            self.assertGreater(w.scroll.verticalScrollBar().maximum(), 0)
        count = w.rendered_count
        w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertGreater(w.rendered_count, count)


if __name__ == '__main__':
    unittest.main()
