"""Verify local source refresh without terminating the application process."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from app_refresh import reload_application
from main import CarleoneWindow


class RefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_recreates_source_and_keeps_view_in_same_process(self):
        window = CarleoneWindow()
        window.show()
        window.mode_selector.setCurrentIndex(1)
        next(b for b in window.category_group.buttons() if b.text() == 'Госорганизации').click()
        window.topic.setCurrentIndex(1)
        topic = window.topic.currentData()
        window.search.setText('1.17')
        window.update_search()
        process_id = os.getpid()
        replacement = reload_application(window)
        self.assertIsNotNone(replacement)
        try:
            self.assertEqual(os.getpid(), process_id)
            self.assertIsNot(type(window), type(replacement))
            self.assertEqual(replacement.mode, 'rules')
            self.assertEqual(replacement.category, 'Госорганизации')
            self.assertEqual(replacement.topic.currentData(), topic)
            self.assertEqual(replacement.search.text(), '1.17')
            self.assertEqual(replacement.server.currentData(), 'murrieta')
            self.assertTrue(replacement.isVisible())
            self.assertIs(self.app.main_window, replacement)
            second = reload_application(replacement)
            self.assertIsNotNone(second)
            replacement = second
            self.assertEqual(replacement.search.text(), '1.17')
        finally:
            replacement.close()
            replacement.deleteLater()

    def test_failed_refresh_keeps_existing_window(self):
        window = CarleoneWindow()
        window.show()
        try:
            with patch('app_refresh.runpy.run_path', side_effect=SyntaxError('test error')):
                with patch('app_refresh.QMessageBox.warning') as warning:
                    self.assertIsNone(reload_application(window))
                    warning.assert_called_once()
            self.assertTrue(window.isVisible())
            self.assertTrue(window.refresh_button.isEnabled())
            self.assertTrue(window.current_records())
        finally:
            window.close()
            window.deleteLater()


if __name__ == '__main__':
    unittest.main()
