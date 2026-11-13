import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from main import CarleoneWindow
from penalty_data import punishment_text


class ArticleCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        settings = QSettings(str(Path(self.directory.name) / 'cards.ini'), QSettings.Format.IniFormat)
        self.window = CarleoneWindow(selection_settings=settings)
        self.window.search.setText('15.6')
        self.window.update_search()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def card(self):
        return self.window.results_layout.itemAt(0).widget()

    def test_catalog_and_search_start_collapsed_with_punishment(self):
        for query in ('', '15.6'):
            self.window.search.setText(query)
            self.window.update_search()
            card = self.card()
            article = self.window.filtered_articles[0]
            self.assertTrue(card.findChild(QWidget, 'article_details').isHidden())
            self.assertFalse(card.findChild(QPushButton, 'article_toggle').isChecked())
            if article['punishment']:
                labels = card.findChildren(QLabel)
                self.assertTrue(any(label.text() == punishment_text(article, 'murrieta')
                                    and not label.isHidden() for label in labels))

    def test_title_click_and_keyboard_toggle_full_text_and_height(self):
        card = self.card()
        toggle = card.findChild(QPushButton, 'article_toggle')
        details = card.findChild(QWidget, 'article_details')
        compact_height = card.height()
        QTest.mouseClick(toggle, Qt.MouseButton.LeftButton)
        QTest.qWait(30)
        self.assertTrue(details.isVisible())
        self.assertEqual(card.findChild(QLabel, 'description').text(),
                         self.window.filtered_articles[0]['description'])
        self.assertGreater(card.height(), compact_height)
        toggle.setFocus()
        QTest.keyClick(toggle, Qt.Key.Key_Space)
        QTest.qWait(30)
        self.assertTrue(details.isHidden())
        self.assertLess(card.height(), compact_height + 5)

    def test_selection_and_copy_do_not_expand_or_collapse(self):
        card = self.card()
        toggle = card.findChild(QPushButton, 'article_toggle')
        card.findChild(QPushButton, 'suspect_add').click()
        self.assertFalse(toggle.isChecked())
        toggle.click()
        self.app.processEvents()
        description = card.findChild(QLabel, 'description')
        QTest.mouseClick(description, Qt.MouseButton.LeftButton)
        self.assertEqual(self.app.clipboard().text(), description.text())
        self.assertTrue(toggle.isChecked())

    def test_long_title_is_shortened_without_losing_full_heading(self):
        article = dict(self.window.filtered_articles[0], title='Полное название статьи ' * 15)
        card = self.window.create_article_card(article)
        try:
            self.assertLessEqual(len(card.findChild(QLabel, 'article_title').text()), 110)
            self.assertIn(article['title'], card.findChild(QLabel, 'article_full_title').text())
        finally:
            card.deleteLater()

    def test_rule_details_keep_full_original_text(self):
        self.window.mode_selector.setCurrentIndex(1)
        self.window.search.setText('')
        self.window.update_search()
        card = self.card()
        self.assertTrue(card.findChild(QWidget, 'article_details').isHidden())
        card.findChild(QPushButton, 'article_toggle').click()
        self.assertEqual(card.findChild(QLabel, 'description').text(),
                         self.window.filtered_articles[0]['description'])


if __name__ == '__main__':
    unittest.main()
