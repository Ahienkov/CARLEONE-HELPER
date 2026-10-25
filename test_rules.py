"""Run with .venv/Scripts/python.exe -m unittest test_rules."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel

from build_rules import parse_rules
from main import CarleoneWindow, SERVER_DATA, RESULT_BATCH_SIZE, SEARCH_DELAY_MS, RESIZE_SETTLE_MS
from rules_data import load_rules


class RulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = CarleoneWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_parser_retains_notes_and_ignores_amounts(self):
        text = 'Введение\n1.1 Запрет\nПримечание: условие\n15 ранг — 45000$.\n1.2.1 Уточнение'
        rules = parse_rules(text)
        self.assertEqual([r['number'] for r in rules], ['Справка', '1.1', '1.2.1'])
        self.assertIn('15 ранг', rules[1]['description'])
        self.assertEqual('\n'.join(r['description'] for r in rules), text)

    def test_all_source_text_and_appendices_retained(self):
        data = json.loads((Path(__file__).parent / 'rules' / 'murrieta.json').read_text(encoding='utf-8'))
        for doc in data['documents']:
            self.assertEqual('\n'.join(r['description'] for r in doc['rules']), doc['text'])
        self.assertEqual(len(data['documents']), 36)
        self.assertEqual(len({d['category'] for d in data['documents']}), 4)
        cards = load_rules('murrieta')
        self.assertTrue(all(c['server_id'] == 'murrieta' for c in cards))
        self.assertTrue(any('Приложение' in c['number'] and 'Максимальный выкуп' in c['description'] for c in cards))

    def test_categories_topics_priority_and_law_regression(self):
        w = self.window
        w.mode_group.button(1).click()
        self.assertEqual(len(w.category_group.buttons()), 5)
        self.assertEqual(w.topic.count(), 37)
        next(b for b in w.category_group.buttons() if b.text() == 'Госорганизации').click()
        self.assertGreater(w.topic.count(), 2)
        w.topic.setCurrentIndex(1)
        selected = w.topic.currentData()
        expected = [r for r in w.current_records() if r['topic_id'] == selected]
        self.assertEqual(w.results_layout.count(), min(len(expected), RESULT_BATCH_SIZE))
        self.assertEqual({id(r) for r in w.filtered_articles}, {id(r) for r in expected})
        w.topic.setCurrentIndex(0)
        w.search.setText('1.17')
        w.update_search()
        label = w.results_layout.itemAt(0).widget().findChild(QLabel, 'article_number')
        self.assertEqual(label.text(), 'Правило 1.17')
        w.mode_group.button(0).click()
        w.search.setText('15.6')
        w.update_search()
        label = w.results_layout.itemAt(0).widget().findChild(QLabel, 'article_number')
        self.assertEqual(label.text(), 'УАК 15.6')

    def test_server_change_never_reuses_murrieta_rules(self):
        w = CarleoneWindow({**SERVER_DATA, 'empty': {'name': 'Empty', 'laws': [], 'rules': []}})
        try:
            w.mode_group.button(1).click()
            self.assertGreater(len(w.current_records()), 0)
            w.server.setCurrentIndex(w.server.findData('empty'))
            self.assertEqual(w.current_records(), [])
            self.assertEqual(w.topic.count(), 1)
            self.assertIn('Empty', w.results_layout.itemAt(0).widget().text())
            w.server.setCurrentIndex(w.server.findData('murrieta'))
            self.assertGreater(len(w.current_records()), 0)
        finally:
            w.close()
            w.deleteLater()

    def test_switch_renders_only_first_batch_and_loads_all_in_order(self):
        w = self.window
        with patch.object(w, 'create_article_card', wraps=w.create_article_card) as create:
            w.mode_group.button(1).click()
            self.assertEqual(create.call_count, RESULT_BATCH_SIZE)
        expected = list(w.filtered_articles)
        self.assertGreater(len(expected), RESULT_BATCH_SIZE)
        self.assertEqual(w.rendered_count, RESULT_BATCH_SIZE)
        self.assertTrue(w.load_more_button.isEnabled())
        while w.rendered_count < len(expected):
            w.load_more_results()
        self.assertEqual(w.rendered_count, len(expected))
        self.assertEqual(w.results_layout.count(), len(expected))
        self.assertEqual(w.filtered_articles, expected)
        w.mode_group.button(0).click()
        self.assertEqual(w.rendered_count, RESULT_BATCH_SIZE)

    def test_typing_debounces_and_switch_cancels_pending_search(self):
        from PySide6.QtTest import QTest
        w = self.window
        w.search.setText('15')
        w.search.setText('15.')
        w.search.setText('15.6')
        self.assertTrue(w.search_timer.isActive())
        with patch.object(w, 'create_article_card', wraps=w.create_article_card) as create:
            QTest.qWait(SEARCH_DELAY_MS + 100)
            self.assertFalse(w.search_timer.isActive())
            self.assertEqual(create.call_count, len(w.filtered_articles))
            self.assertEqual(w.filtered_articles[0]['number'], '15.6')
        w.search.setText('1.1')
        w.mode_group.button(1).click()
        self.assertFalse(w.search_timer.isActive())
        self.assertTrue(all(a['kind'] == 'rule' for a in w.filtered_articles))
        self.assertEqual(w.filtered_articles[0]['number'], '1.1')

    def test_scrolling_loads_next_batch(self):
        from PySide6.QtTest import QTest
        w = self.window
        w.mode_group.button(1).click()
        w.show()
        self.app.processEvents()
        QTest.qWait(RESIZE_SETTLE_MS + 40)
        bar = w.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.app.processEvents()
        self.assertEqual(w.rendered_count, RESULT_BATCH_SIZE * 2)


if __name__ == '__main__':
    unittest.main()
