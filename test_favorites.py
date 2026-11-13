import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from main import CarleoneWindow
from suspect_selection import article_key, FavoritesStore, SuspectStore
from app_refresh import reload_application


class FavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'favorites.ini')
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.window = CarleoneWindow(selection_settings=self.settings)
        self.article = next(a for a in self.window.current_records() if a['number'] == '15.6')
        self.key = article_key(self.article)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_star_saves_immediately_without_touching_suspect_or_details(self):
        w = self.window
        w.search.setText('15.6')
        w.update_search()
        card = w.results_layout.itemAt(0).widget()
        star = card.findChild(QPushButton, 'favorite_add')
        star.click()
        self.assertTrue(star.isChecked())
        self.assertEqual(FavoritesStore(QSettings(self.path, QSettings.Format.IniFormat)).load()['murrieta'], {self.key})
        self.assertFalse(SuspectStore(self.settings).load())
        self.assertFalse(card.findChild(QPushButton, 'article_toggle').isChecked())
        star.click()
        self.assertFalse(w.selected_favorite_keys())
        self.assertEqual(w.search.text(), '15.6')

    def test_new_window_restores_favorites(self):
        self.window.toggle_favorite_article(self.key)
        self.window.close()
        self.window.deleteLater()
        self.window = CarleoneWindow(selection_settings=QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(self.window.selected_favorite_keys(), {self.key})
        self.assertEqual(self.window.favorites_button.text(), 'Избранное (1)')

    def test_favorites_filter_search_and_remove_last(self):
        w = self.window
        w.toggle_favorite_article(self.key)
        w.search.setText('no match')
        w.favorites_button.click()
        self.assertEqual([article_key(a) for a in w.filtered_articles], [self.key])
        w.search.setText('no match')
        w.update_search()
        self.assertEqual(w.filtered_articles, [])
        w.search.clear()
        w.update_search()
        w.results_layout.itemAt(0).widget().findChild(QPushButton, 'favorite_add').click()
        self.assertEqual(w.filtered_articles, [])
        self.assertFalse(w.selected_favorite_keys())

    def test_favorite_and_suspect_filters_are_independent(self):
        w = self.window
        w.toggle_favorite_article(self.key)
        other = ('ДК', '1')
        w.toggle_suspect_article(other)
        w.suspect_button.click()
        w.favorites_button.click()
        self.assertFalse(w.suspect_button.isChecked())
        self.assertEqual([article_key(a) for a in w.filtered_articles], [self.key])
        w.suspect_button.click()
        self.assertFalse(w.favorites_button.isChecked())
        self.assertEqual([article_key(a) for a in w.filtered_articles], [other])
        self.assertEqual(w.selected_favorite_keys(), {self.key})

    def test_rules_and_servers_keep_separate_lists_and_live_refresh(self):
        w = self.window
        w.toggle_favorite_article(self.key)
        w.mode_selector.setCurrentIndex(1)
        rules = [r for r in w.current_records() if r['number'] == '1.1']
        first = rules[0]
        other = next(r for r in rules if r['topic_id'] != first['topic_id'])
        w.toggle_favorite_article(article_key(first))
        w.favorites_button.click()
        self.assertEqual([article_key(a) for a in w.filtered_articles], [article_key(first)])
        self.assertNotIn(article_key(other), w.selected_favorite_keys())
        replacement = reload_application(w)
        self.assertIsNotNone(replacement)
        self.window = w = replacement
        self.assertTrue(w.favorites_button.isChecked())
        self.assertEqual([article_key(a) for a in w.filtered_articles], [article_key(first)])
        w.mode_selector.setCurrentIndex(0)
        self.assertEqual(w.selected_favorite_keys(), {self.key})
        w.server.addItem('Test', 'test')
        w.server.setCurrentIndex(w.server.findData('test'))
        self.assertFalse(w.selected_favorite_keys())
        w.toggle_favorite_article(self.key)
        w.server.setCurrentIndex(w.server.findData('murrieta'))
        self.assertEqual(w.selected_favorite_keys(), {self.key})

    def test_save_failure_restores_star_and_does_not_lose_saved_selection(self):
        w = self.window
        w.search.setText('15.6')
        w.update_search()
        star = w.results_layout.itemAt(0).widget().findChild(QPushButton, 'favorite_add')
        with patch.object(w.favorites_store, 'save', side_effect=OSError('Не удалось сохранить избранное.')):
            with patch('main.QMessageBox.warning') as warning:
                star.click()
                warning.assert_called_once()
        self.assertFalse(star.isChecked())
        self.assertFalse(w.selected_favorite_keys())


if __name__ == '__main__':
    unittest.main()
