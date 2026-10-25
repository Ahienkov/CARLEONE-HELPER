import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest

from main import CarleoneWindow, SERVER_DATA
from suspect_selection import article_key, SuspectStore
from app_refresh import reload_application


class SuspectSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.directory.name) / 'selection.ini'), QSettings.Format.IniFormat)
        self.window = CarleoneWindow(selection_settings=self.settings)
        self.article = next(a for a in self.window.current_records() if a['number'] == '15.6')
        self.key = article_key(self.article)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.setProperty('ui_language', 'ru')
        self.directory.cleanup()

    def test_add_remove_without_duplicates_and_keep_search(self):
        w = self.window
        w.search.setText('15.6')
        w.update_search()
        button = w.results_layout.itemAt(0).widget().findChild(QPushButton, 'suspect_add')
        self.assertIsNotNone(button)
        position = w.scroll.verticalScrollBar().value()
        button.click()
        self.assertEqual(w.selected_suspect_keys(), {self.key})
        self.assertEqual(w.search.text(), '15.6')
        self.assertEqual(w.scroll.verticalScrollBar().value(), position)
        self.assertTrue(button.isChecked())
        button.click()
        self.assertEqual(w.selected_suspect_keys(), set())
        self.assertFalse(button.isChecked())

    def test_filter_opens_all_selected_and_search_narrows(self):
        w = self.window
        w.toggle_suspect_article(self.key)
        w.toggle_suspect_article(('ДК', '1'))
        w.search.setText('no match')
        w.suspect_button.click()
        self.assertEqual(w.mode, 'laws')
        self.assertEqual(w.search.text(), '')
        self.assertEqual(w.category, 'Все')
        self.assertEqual({article_key(a) for a in w.filtered_articles}, {self.key, ('ДК', '1')})
        w.search.setText('15.6')
        w.update_search()
        self.assertEqual([article_key(a) for a in w.filtered_articles], [self.key])
        w.toggle_suspect_article(self.key)
        self.assertEqual(w.filtered_articles, [])
        w.clear_suspect_button.click()
        self.assertEqual(w.selected_suspect_keys(), set())

    def test_restart_and_live_refresh_preserve_selection(self):
        w = self.window
        w.toggle_suspect_article(self.key)
        w.suspect_button.click()
        self.assertEqual(SuspectStore(self.settings).load()['murrieta'], {self.key})
        replacement = reload_application(w)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.selected_suspect_keys(), {self.key})
        self.assertTrue(replacement.suspect_button.isChecked())
        self.assertEqual([article_key(a) for a in replacement.filtered_articles], [self.key])

    def test_servers_and_codes_do_not_share_selections(self):
        w = self.window
        w.toggle_suspect_article(self.key)
        w.server_data = {**w.server_data, 'test': {'name': 'Test', 'laws': w.current_records(), 'rules': []}}
        w.server.addItem('Test', 'test')
        w.server.setCurrentIndex(w.server.findData('test'))
        self.assertFalse(w.selected_suspect_keys())
        w.toggle_suspect_article(('ПК', '15.6'))
        self.assertEqual(w.selected_suspect_keys(), {('ПК', '15.6')})
        w.server.setCurrentIndex(w.server.findData('murrieta'))
        self.assertEqual(w.selected_suspect_keys(), {self.key})

    def test_rules_selection_is_separate_and_title_changes(self):
        w = self.window
        w.toggle_suspect_article(self.key)
        w.suspect_button.click()
        w.mode_selector.setCurrentIndex(1)
        self.assertFalse(w.suspect_button.isChecked())
        self.assertEqual(w.selected_suspect_keys(), set())
        rule = next(r for r in w.current_records() if not r['number'].startswith('Справка'))
        w.toggle_suspect_article(article_key(rule))
        self.assertEqual(w.suspect_button.text(), 'Нарушения игрока (1)')
        w.suspect_button.click()
        self.assertEqual([article_key(r) for r in w.filtered_articles], [article_key(rule)])
        self.assertIsNotNone(w.results_layout.itemAt(0).widget().findChild(QPushButton, 'suspect_add'))
        w.clear_suspect_button.click()
        self.assertFalse(w.selected_suspect_keys())
        w.mode_selector.setCurrentIndex(0)
        self.assertEqual(w.selected_suspect_keys(), {self.key})
        self.assertTrue(w.suspect_button.isChecked())
        self.assertEqual(w.suspect_button.text(), 'Нарушения подозреваемого (1)')

    def test_equal_rule_numbers_in_different_topics_are_independent(self):
        w = self.window
        w.mode_selector.setCurrentIndex(1)
        rules = [r for r in w.current_records() if r['number'] == '1.1']
        first = rules[0]
        other = next(r for r in rules if r['topic_id'] != first['topic_id'])
        self.assertNotEqual(article_key(first), article_key(other))
        w.toggle_suspect_article(article_key(first))
        w.suspect_button.click()
        self.assertEqual([article_key(r) for r in w.filtered_articles], [article_key(first)])

    def test_rule_selection_survives_live_refresh(self):
        w = self.window
        w.mode_selector.setCurrentIndex(1)
        rule = next(r for r in w.current_records() if r['number'] == '6.1.1')
        key = article_key(rule)
        w.toggle_suspect_article(key)
        w.suspect_button.click()
        replacement = reload_application(w)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.mode, 'rules')
        self.assertTrue(replacement.suspect_button.isChecked())
        self.assertEqual([article_key(r) for r in replacement.filtered_articles], [key])

    def test_corrupt_settings_fall_back_to_empty(self):
        for value in ('{broken', 'null', '[]', '{"murrieta": [null, 8, [1, 2]]}'):
            self.settings.setValue('suspect_articles', value)
            self.assertFalse(SuspectStore(self.settings).load().get('murrieta'))

    def test_repeated_empty_filter_does_not_collapse_restored_cards(self):
        w = self.window
        w.show()
        QTest.qWait(180)
        for _ in range(4):
            w.suspect_button.click()
            QTest.qWait(100)
            self.assertEqual(w.filtered_articles, [])
            w.suspect_button.click()
            QTest.qWait(100)
            self.assertGreater(w.rendered_count, 0)
            results = w.scroll.widget()
            self.assertGreaterEqual(results.height(), w.results_layout.totalHeightForWidth(results.width()))
            for index in range(w.results_layout.count()):
                self.assertGreater(w.results_layout.itemAt(index).widget().height(), 100)
        suspect_top = w.suspect_button.mapTo(w, w.suspect_button.rect().topLeft()).y()
        suspect_bottom = w.suspect_button.mapTo(w, w.suspect_button.rect().bottomLeft()).y()
        self.assertGreater(suspect_top, w.search.geometry().bottom())
        self.assertLess(suspect_bottom, w.server.y())

    def test_empty_search_restores_full_height_without_refresh(self):
        w = self.window
        w.show()
        QTest.qWait(180)
        for query in ('no-such-article', '', '15.6', ''):
            w.search.setText(query)
            w.update_search()
            QTest.qWait(100)
            if w.filtered_articles:
                results = w.scroll.widget()
                self.assertGreaterEqual(results.height(), w.results_layout.totalHeightForWidth(results.width()))
                self.assertGreater(w.results_layout.itemAt(0).widget().height(), 100)


if __name__ == '__main__':
    unittest.main()
