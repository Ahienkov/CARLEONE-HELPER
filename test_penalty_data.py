import copy
import json
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from codex_data import load_articles
from road_data import load_road_articles
from main import CarleoneWindow, CopyLabel
from penalty_data import PENALTIES, SOURCE_PATH, penalty_supplement, punishment_text
from import_penalties import parse_sheet


class PenaltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.laws = {a['number']: a for a in load_articles()}
        cls.roads = {a['number']: a for a in load_road_articles()}

    def setUp(self):
        self.app.setProperty('ui_language', 'ru')

    def tearDown(self):
        self.app.setProperty('ui_language', 'ru')

    def test_reviewed_snapshot_matches_all_local_articles(self):
        data = json.loads(SOURCE_PATH.read_text(encoding='utf-8'))
        self.assertEqual(len(data['articles']), 102)
        self.assertEqual(sum(bool(r['minutes']) for r in data['articles']), 81)
        for row in data['articles']:
            article = (self.laws if row['code'] == 'УАК' else self.roads)[row['number']]
            self.assertEqual(article['title'], row['forum_title'])
            self.assertEqual(bool(penalty_supplement(article, 'murrieta')), bool(row['minutes']))

    def test_three_destinations_and_ranges(self):
        for number, expected in (('6.1', '(15–30 мин, КПЗ)'), ('10.5', '(30 мин, СИЗО)'),
                                 ('6.2', '(90 мин, ФТ)'), ('15.6', '(60–120 мин, ФТ)')):
            self.assertEqual(penalty_supplement(self.laws[number], 'murrieta'), expected)
        self.assertEqual(penalty_supplement(self.roads['1'], 'murrieta'), '(10 мин, КПЗ)')

    def test_no_invented_minutes_for_dash_or_missing_article(self):
        for number in ('11.6', '12.6.1', '12.8.2', '15.6.1', '1.1'):
            self.assertEqual(punishment_text(self.laws[number], 'murrieta'), self.laws[number]['punishment'])
        self.assertEqual(penalty_supplement(self.roads['2'], 'murrieta'), '')

    def test_exact_code_server_and_kind(self):
        article = self.laws['6.2']
        self.assertEqual(penalty_supplement(article, 'senora'), '')
        self.assertEqual(penalty_supplement({**article, 'code': 'ПК'}, 'murrieta'), '')
        self.assertEqual(penalty_supplement({**article, 'kind': 'rule'}, 'murrieta'), '')
        self.assertEqual(penalty_supplement({**article, 'number': '6.2.9'}, 'murrieta'), '')

    def test_forum_updates_preserve_supplement_without_mutating_source(self):
        article = copy.deepcopy(self.laws['15.6'])
        article['punishment'] = 'Новый текст наказания с форума.'
        original = copy.deepcopy(article)
        self.assertEqual(punishment_text(article, 'murrieta'), 'Новый текст наказания с форума.\n(60–120 мин, ФТ)')
        self.assertEqual(article, original)
        article['title'] = 'Иное содержание статьи'
        self.assertEqual(penalty_supplement(article, 'murrieta'), '')
        article = {**self.laws['6.2'], 'marker': '🟩'}
        self.assertEqual(penalty_supplement(article, 'murrieta'), '')

    def test_localized_minutes(self):
        self.app.setProperty('ui_language', 'uk')
        self.assertEqual(penalty_supplement(self.laws['6.2'], 'murrieta'), '(90 хв, ФТ)')
        self.app.setProperty('ui_language', 'en')
        self.assertEqual(penalty_supplement(self.laws['6.2'], 'murrieta'), '(90 min, ФТ)')

    def test_copy_punishment_includes_supplement(self):
        window = CarleoneWindow()
        card = window.create_article_card(self.laws['15.6'])
        card.show()
        try:
            label = card.findChild(CopyLabel, 'criminal_punishment')
            self.assertTrue(label.text().endswith('(60–120 мин, ФТ)'))
            QTest.mouseClick(label, Qt.MouseButton.LeftButton)
            self.assertEqual(self.app.clipboard().text(), label.text())
        finally:
            card.close()
            card.deleteLater()
            window.close()
            window.deleteLater()

    def test_import_rejects_wrong_server(self):
        with self.assertRaises(ValueError):
            parse_sheet('[SENORA]')


if __name__ == '__main__':
    unittest.main()
