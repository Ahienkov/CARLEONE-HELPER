import os
import tempfile
import unittest
from pathlib import Path
from string import Formatter

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from app_settings import DEFAULTS, SettingsStore, SettingsDialog
from i18n import CATALOG, LANGUAGES, LocalizedLabel, tr
from main import CarleoneWindow


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.app.setProperty('ui_language', 'ru')
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.store = SettingsStore(QSettings(str(Path(self.directory.name) / 'prefs.ini'), QSettings.Format.IniFormat))

    def tearDown(self):
        self.app.setProperty('ui_language', 'ru')
        self.directory.cleanup()

    def test_russian_default_and_language_persistence(self):
        self.assertEqual(self.store.load()['language'], 'ru')
        self.store.save({**DEFAULTS, 'language': 'uk'})
        self.assertEqual(self.store.load()['language'], 'uk')
        with self.assertRaises(ValueError):
            self.store.save({**DEFAULTS, 'language': 'unknown'})

    def test_every_translation_preserves_template_fields(self):
        fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name}
        for source, variants in CATALOG.items():
            self.assertEqual(set(variants), set(LANGUAGES))
            for language, translation in variants.items():
                self.assertTrue(translation)
                self.assertEqual(fields(source), fields(translation), (source, language))

    def test_switching_language_keeps_filter_query_and_forum_text(self):
        window = CarleoneWindow()
        window.settings_store = self.store
        try:
            next(b for b in window.category_group.buttons() if b.property('category') == 'Дорожный').click()
            window.search.setText('69')
            window.update_search()
            original = window.filtered_articles[0]['description']
            for language, laws, traffic in (('en', 'Laws', 'Traffic'), ('uk', 'Закони', 'Дорожній'), ('ru', 'Законы', 'Дорожный')):
                window.apply_preferences({**DEFAULTS, 'language': language})
                self.assertEqual(window.mode_selector.itemText(0), laws)
                self.assertEqual(window.category, 'Дорожный')
                self.assertEqual(window.search.text(), '69')
                self.assertEqual(window.filtered_articles[0]['description'], original)
                button = next(b for b in window.category_group.buttons() if b.property('category') == 'Дорожный')
                self.assertEqual(button.text(), traffic)
                window.mode_selector.setCurrentIndex(1)
                window.mode_selector.setCurrentIndex(0)
                next(b for b in window.category_group.buttons() if b.property('category') == 'Дорожный').click()
        finally:
            window.close()
            window.deleteLater()

    def test_settings_and_background_status_are_translated(self):
        self.app.setProperty('ui_language', 'en')
        dialog = SettingsDialog({**DEFAULTS, 'language': 'en'}, lambda values: None)
        self.assertEqual(dialog.windowTitle(), 'GTA 5 RP HELPER settings')
        self.assertEqual(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).text(), 'Save')
        self.assertEqual(dialog.language.currentData(), 'en')
        label = LocalizedLabel('Форум: актуально')
        self.assertEqual(label.text(), 'Forum: up to date')
        self.app.setProperty('ui_language', 'uk')
        label.retranslate()
        self.assertEqual(label.text(), 'Форум: актуально')
        self.assertEqual(tr('F4 — показать / скрыть'), 'F4 — показати / приховати')
        dialog.reject()
        dialog.deleteLater()
        label.deleteLater()


if __name__ == '__main__':
    unittest.main()
