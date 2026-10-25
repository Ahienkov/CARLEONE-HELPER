import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from main import CarleoneWindow, SERVER_DATA
from section_environment import load_section
from app_refresh import reload_application


class SectionEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = CarleoneWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_only_active_section_keeps_database_and_index(self):
        w = self.window
        self.assertNotIn('laws', SERVER_DATA['murrieta'])
        self.assertNotIn('rules', SERVER_DATA['murrieta'])
        self.assertIsNone(w.environments['rules'].records)
        self.assertEqual(set(w.search_index), {('murrieta', 'laws')})
        old_cards = [w.results_layout.itemAt(i).widget() for i in range(w.results_layout.count())]
        with patch('section_environment.load_section', wraps=load_section) as load:
            w.mode_selector.setCurrentIndex(1)
            load.assert_called_once_with('murrieta', 'rules')
            self.assertIsNone(w.environments['laws'].records)
            self.assertIsNone(w.environments['laws'].index)
            self.assertEqual(set(w.search_index), {('murrieta', 'rules')})
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertTrue(all(not isValid(card) for card in old_cards))
            w.mode_selector.setCurrentIndex(0)
            self.assertEqual(load.call_count, 2)
            self.assertIsNone(w.environments['rules'].records)
            self.assertIsNone(w.environments['rules'].index)

    def configure_independent_sections(self):
        w = self.window
        next(b for b in w.category_group.buttons() if b.property('category') == 'Уголовный').click()
        w.search.setText('15.6')
        w.update_search()
        w.mode_selector.setCurrentIndex(1)
        self.assertEqual(w.search.text(), '')
        next(b for b in w.category_group.buttons() if b.property('category') == 'Госорганизации').click()
        w.topic.setCurrentIndex(1)
        topic = w.topic.currentData()
        w.search.setText('1.1')
        w.update_search()
        return topic

    def test_query_category_topic_and_server_belong_to_section(self):
        w = self.window
        topic = self.configure_independent_sections()
        w.mode_selector.setCurrentIndex(0)
        self.assertEqual(w.search.text(), '15.6')
        self.assertEqual(w.category, 'Уголовный')
        self.assertTrue(w.filtered_articles)
        w.server.setCurrentIndex(w.server.findData('eclipse'))
        w.mode_selector.setCurrentIndex(1)
        self.assertEqual(w.server.currentData(), 'murrieta')
        self.assertEqual(w.search.text(), '1.1')
        self.assertEqual(w.category, 'Госорганизации')
        self.assertEqual(w.topic.currentData(), topic)
        w.mode_selector.setCurrentIndex(0)
        self.assertEqual(w.server.currentData(), 'eclipse')

    def test_refresh_preserves_both_section_states_without_loading_inactive_data(self):
        topic = self.configure_independent_sections()
        replacement = reload_application(self.window)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.mode, 'rules')
        self.assertIsNone(replacement.environments['laws'].records)
        self.assertEqual(replacement.topic.currentData(), topic)
        replacement.mode_selector.setCurrentIndex(0)
        self.assertEqual(replacement.search.text(), '15.6')
        self.assertEqual(replacement.category, 'Уголовный')

    def test_forum_update_keeps_only_active_data_and_reads_inactive_snapshot_later(self):
        w = self.window
        updated = [dict(article) for article in w.current_records()]
        updated[0]['description'] += '\nОбновление.'
        w.apply_forum_update({'name': 'Murrieta', 'laws': updated, 'rules': []})
        self.assertIn('Обновление.', w.current_records()[0]['description'])
        self.assertNotIn('laws', w.server_data['murrieta'])
        self.assertNotIn('rules', w.server_data['murrieta'])
        self.assertIsNone(w.environments['rules'].records)
        with patch('section_environment.load_section', wraps=load_section) as load:
            w.mode_selector.setCurrentIndex(1)
            load.assert_called_once_with('murrieta', 'rules')
            self.assertTrue(w.current_records())

    def test_rules_can_start_without_loading_laws(self):
        with patch('section_environment.load_section', wraps=load_section) as load:
            other = CarleoneWindow(initial_mode='rules')
            try:
                load.assert_called_once_with('murrieta', 'rules')
                self.assertIsNone(other.environments['laws'].records)
                self.assertEqual(set(other.search_index), {('murrieta', 'rules')})
            finally:
                other.close()
                other.deleteLater()
