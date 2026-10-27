import unittest

from law_search import LawSearchIndex, within_edits


class LawSearchTests(unittest.TestCase):
    def setUp(self):
        self.articles = [
            {'number': '6.1', 'text': 'Незаконное хранение оружия'},
            {'number': '6.2', 'text': 'Ограбление автомобиля с оружием'},
            {'number': '6.3', 'text': 'Кража имущества'},
            {'number': '6.4', 'text': 'Правила дорожного движения'},
        ]
        self.index = LawSearchIndex([(a, a['number'] + ' ' + a['text'].casefold())
                                    for a in self.articles])

    def results(self, query):
        scores = self.index.scores(query)
        return [a['number'] for a in sorted(self.articles, key=lambda a: scores.get(id(a), 999))
                if id(a) in scores]

    def test_typos_including_transposition_and_missing_letter(self):
        self.assertEqual(self.results('храенние'), ['6.1'])
        self.assertEqual(self.results('ограблние'), ['6.2'])
        self.assertEqual(self.results('краша'), ['6.3'])

    def test_inflections_and_exact_first(self):
        self.assertEqual(self.results('оружия'), ['6.1', '6.2'])
        self.assertEqual(self.results('оружием'), ['6.2', '6.1'])
        self.assertEqual(self.results('кражей'), ['6.3'])
        self.assertEqual(self.results('дорожным'), ['6.4'])

    def test_all_words_required_and_numbers_not_fuzzy(self):
        self.assertEqual(self.results('незаконное храенние оружия'), ['6.1'])
        self.assertEqual(self.results('кража оружия'), [])
        self.assertEqual(self.results('6.9'), [])
        self.assertEqual(self.results('6.1 оружя'), ['6.1'])
        self.assertEqual(self.results('ук'), [])

    def test_empty_normalized_and_irrelevant_queries(self):
        self.assertEqual(len(self.results('')), 4)
        self.assertEqual(self.results('НЕЗАКОННОЕ'), ['6.1'])
        self.assertEqual(self.results('самолетостроение'), [])

    def test_edit_distance_boundaries(self):
        self.assertTrue(within_edits('оружя', 'оружия', 1))
        self.assertTrue(within_edits('кража', 'каржа', 1))
        self.assertFalse(within_edits('кража', 'крыша', 1))
        self.assertFalse(within_edits('а', 'автомобиль', 2))

    def test_synonyms_and_inflections_keep_all_query_constraints(self):
        self.assertEqual(self.results('украл'), ['6.3'])
        self.assertEqual(self.results('украли имущество'), ['6.3'])
        self.assertEqual(set(self.results('ствол')), {'6.1', '6.2'})
        self.assertEqual(set(self.results('стволами')), {'6.1', '6.2'})
        self.assertEqual(self.results('ограбил тачку'), ['6.2'])
        self.assertEqual(self.results('украл ствол'), [])
        self.assertEqual(self.results('6.3 украл'), ['6.3'])
        self.assertEqual(self.results('6.9 ствол'), [])

    def test_literal_match_ranks_above_synonym(self):
        literal = {'number': '7', 'text': 'Найден ствол дерева'}
        index = LawSearchIndex([(a, a['text'].casefold()) for a in [*self.articles, literal]])
        scores = index.scores('ствол')
        self.assertLess(scores[id(literal)], scores[id(self.articles[0])])

    def test_synonyms_find_formal_legal_wording(self):
        rows = [{'text': 'Хранение наркотических веществ'}, {'text': 'Грабеж имущества'}]
        index = LawSearchIndex([(a, a['text'].casefold()) for a in rows])
        self.assertIn(id(rows[0]), index.scores('наркота'))
        self.assertIn(id(rows[1]), index.scores('ограбил'))

    def test_different_offences_are_not_synonyms(self):
        self.assertEqual(self.results('ограбил'), ['6.2'])
        self.assertNotIn('6.2', self.results('украл'))
        self.assertEqual(self.results('угнал'), [])
        self.assertEqual(self.results('стол'), [])

    def test_window_uses_similarity_and_keeps_category_filter(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from main import CarleoneWindow
        app = QApplication.instance() or QApplication([])
        records = [dict(a, title=a['text'], description=a['text'], punishment='', keywords='',
                        category='Уголовный' if a['number'] != '6.2' else 'Административный')
                   for a in self.articles]
        window = CarleoneWindow({'murrieta': {'name': 'Murrieta', 'laws': records, 'rules': []}})
        try:
            window.search.setText('оружием')
            window.update_search()
            self.assertEqual([a['number'] for a in window.filtered_articles], ['6.2', '6.1'])
            window.category = 'Уголовный'
            window.update_search()
            self.assertEqual([a['number'] for a in window.filtered_articles], ['6.1'])
            window.search.setText('храенние')
            window.update_search()
            self.assertEqual([a['number'] for a in window.filtered_articles], ['6.1'])
            window.search.setText('ствол')
            window.update_search()
            self.assertEqual([a['number'] for a in window.filtered_articles], ['6.1'])
            environment = window.environments['laws']
            window.mode_selector.setCurrentIndex(1)
            self.assertIsNone(environment.law_search)
        finally:
            window.close()
            window.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
