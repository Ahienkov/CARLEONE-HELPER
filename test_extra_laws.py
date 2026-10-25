"""Coverage and UI checks for the additional Murrieta laws."""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel

from extra_laws_data import EXTRA_LAWS, SOURCE_PATH, parse_extra_law
from main import CarleoneWindow, RESULT_BATCH_SIZE
from procedure_data import ARTICLE, CHAPTER
from road_data import IMAGE


class ExtraLawsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_complete_text_and_article_identifiers(self):
        source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(source['documents']), 3)
        for document in source['documents']:
            articles = parse_extra_law(document)
            expected = []
            chapter = ''
            combined = '\n'.join(a['source_text'] for a in articles)
            for raw in document['text'].splitlines():
                line = raw.replace('\u200b', '').strip()
                if not line or IMAGE.fullmatch(line):
                    continue
                match = CHAPTER.match(line)
                if match:
                    chapter = match[1]
                    continue
                match = ARTICLE.match(line)
                if match:
                    expected.append((chapter, match[1]))
                self.assertIn(line, combined)
            actual = [(a['chapter_number'], a['number']) for a in articles if a['number'] != 'Справка']
            self.assertEqual(actual, expected)
            self.assertTrue(all(a['server_id'] == 'murrieta' for a in articles))

    def test_filters_number_priority_and_batch_limit(self):
        w = CarleoneWindow()
        try:
            for law in EXTRA_LAWS:
                next(b for b in w.category_group.buttons() if b.text() == law['category']).click()
                self.assertTrue(w.filtered_articles)
                self.assertTrue(all(a['category'] == law['category'] for a in w.filtered_articles))
                self.assertLessEqual(w.rendered_count, RESULT_BATCH_SIZE)
                target = next(a for a in w.filtered_articles if a['number'] != 'Справка')
                w.search.setText(target['number'])
                w.update_search()
                self.assertEqual(w.filtered_articles[0]['number'], target['number'])
                label = w.results_layout.itemAt(0).widget().findChild(QLabel, 'article_number')
                self.assertTrue(label.text().startswith(law['code']))
                w.search.clear()
                w.update_search()
            w.mode_group.button(1).click()
            self.assertFalse(any(a['category'] in {law['category'] for law in EXTRA_LAWS} for a in w.current_records()))
        finally:
            w.close()
            w.deleteLater()

    def test_category_buttons_fit_small_window(self):
        w = CarleoneWindow()
        try:
            w.resize(920, 500)
            w.show()
            self.app.processEvents()
            for button in w.category_group.buttons():
                self.assertTrue(w.rect().contains(button.geometry()))
                self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()))
        finally:
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
