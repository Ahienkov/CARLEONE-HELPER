import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from main import CarleoneWindow
from notepad import NotepadStore
from app_refresh import reload_application


class NotepadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.directory.name) / 'notes.ini'), QSettings.Format.IniFormat)
        self.window = CarleoneWindow(initial_mode='notepad', notepad_settings=self.settings)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.directory.cleanup()

    def test_autosave_switch_reload_and_clear(self):
        w = self.window
        text = 'Заметка\nКонтакты: 123\n<текст> 🎮'
        w.notepad_panel.editor.setPlainText(text)
        self.assertEqual(NotepadStore(self.settings).load()['tabs'][0]['text'], text)
        w.mode_selector.setCurrentIndex(w.mode_selector.findData('laws'))
        self.assertIsNone(w.notepad_panel)
        w.mode_selector.setCurrentIndex(w.mode_selector.findData('notepad'))
        self.assertEqual(w.notepad_panel.editor.toPlainText(), text)
        self.assertTrue(w.server.isHidden())
        self.assertEqual(w.current_records(), [])
        replacement = reload_application(w)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.notepad_panel.editor.toPlainText(), text)
        replacement.notepad_panel.editor.clear()
        self.assertEqual(NotepadStore(self.settings).load()['tabs'][0]['text'], '')

    def test_failed_save_keeps_editor_and_blocks_leaving(self):
        w = self.window
        with patch.object(w.notepad_panel.store, 'save', side_effect=OSError('disk error')):
            w.notepad_panel.editor.setPlainText('keep this')
            w.mode_selector.setCurrentIndex(w.mode_selector.findData('laws'))
            self.assertEqual(w.mode, 'notepad')
            self.assertEqual(w.mode_selector.currentData(), 'notepad')
            self.assertFalse(w.close())
            self.assertEqual(w.notepad_panel.editor.toPlainText(), 'keep this')
        self.assertTrue(w.notepad_panel.flush())
        self.assertEqual(NotepadStore(self.settings).load()['tabs'][0]['text'], 'keep this')

    def test_tabs_survive_restart_with_names_text_and_selection(self):
        panel = self.window.notepad_panel
        panel.editor.setPlainText('Первая заметка')
        panel.add_button.click()
        panel.editor.setPlainText('Вторая заметка')
        with patch('notepad.QInputDialog.getText', return_value=('Контакты', True)):
            panel.rename_tab(1)
        panel.add_tab()
        panel.editor.setPlainText('Третья заметка')
        panel.tabs.setCurrentIndex(1)
        self.window.close()
        self.window.deleteLater()
        self.window = CarleoneWindow(initial_mode='notepad', notepad_settings=self.settings)
        panel = self.window.notepad_panel
        self.assertEqual(panel.tabs.count(), 3)
        self.assertEqual(panel.tabs.currentIndex(), 1)
        self.assertEqual(panel.tabs.tabText(1), 'Контакты')
        self.assertEqual(panel.editor.toPlainText(), 'Вторая заметка')
        panel.tabs.setCurrentIndex(0)
        self.assertEqual(panel.editor.toPlainText(), 'Первая заметка')
        panel.tabs.setCurrentIndex(2)
        self.assertEqual(panel.editor.toPlainText(), 'Третья заметка')

    def test_migration_preserves_old_text(self):
        self.settings.setValue('notepad/v1/text', 'Старые заметки')
        self.settings.sync()
        store = NotepadStore(self.settings)
        document = store.load()
        self.assertEqual(document['tabs'][0]['text'], 'Старые заметки')
        store.save(document)
        self.assertEqual(store.load(), document)
        self.assertEqual(self.settings.value('notepad/v1/text'), 'Старые заметки')

    def test_delete_requires_confirmation_and_keeps_other_tabs(self):
        panel = self.window.notepad_panel
        panel.editor.setPlainText('Сохранить')
        panel.add_tab()
        with patch('notepad.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            panel.remove_tab(0)
        self.assertEqual(panel.tabs.count(), 2)
        with patch('notepad.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            panel.remove_tab(1)
        self.assertEqual(panel.tabs.count(), 1)
        self.assertEqual(panel.editor.toPlainText(), 'Сохранить')
        panel.remove_tab(0)
        self.assertEqual(len(NotepadStore(self.settings).load()['tabs']), 1)

    def test_invalid_saved_document_is_not_overwritten(self):
        self.settings.setValue('notepad/v2/document', '{broken')
        self.settings.sync()
        from notepad import NotepadPanel
        panel = NotepadPanel(NotepadStore(self.settings))
        try:
            self.assertTrue(panel.editor.isReadOnly())
            self.assertFalse(panel.add_button.isEnabled())
            self.assertTrue(panel.flush())
            self.assertEqual(self.settings.value('notepad/v2/document'), '{broken')
        finally:
            panel.deleteLater()

    def test_translating_keeps_text(self):
        w = self.window
        w.notepad_panel.editor.setPlainText('Мои заметки')
        self.app.setProperty('ui_language', 'en')
        try:
            w.retranslate_ui()
            self.assertEqual(w.notepad_panel.title.text(), 'Notepad')
            self.assertEqual(w.notepad_panel.editor.toPlainText(), 'Мои заметки')
        finally:
            self.app.setProperty('ui_language', 'ru')


if __name__ == '__main__':
    unittest.main()
