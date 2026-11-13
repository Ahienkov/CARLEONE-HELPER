import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from ai_search import AiSearchPanel
from main import CarleoneWindow


class AiSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def wait(self,panel):
        deadline=time.monotonic()+3
        while panel.busy and time.monotonic()<deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.app.processEvents()
        self.assertFalse(panel.busy)

    def test_search_sends_only_question_and_renders_verified_sources_as_safe_text(self):
        client=Mock()
        client.post.return_value={'quota':{'remaining':5,'limit':5}}
        panel=AiSearchPanel(client=client)
        try:
            panel.set_server('murrieta');self.wait(panel)
            client.post.return_value={'status':'ready','answer':'<script>example</script> [1]', 'cached':True,
                'quota':{'remaining':5,'limit':5},'sources':[{'ref':1,'title':'Статья 1','url':'https://forum.gta5rp.com/threads/test/'},
                {'ref':2,'title':'unsafe','url':'file:///C:/secret'}]}
            panel.question.setPlainText('Игрок угнал чужую машину')
            panel.search();self.wait(panel)
            self.assertEqual(client.post.call_args.args[0],'search')
            self.assertEqual(set(client.post.call_args.args[1]),{'query','server','scope'})
            self.assertIn('<script>example</script>',panel.answer.toPlainText())
            self.assertNotIn('file://',panel.answer.toHtml())
            self.assertIn('не расходуется',panel.status.text())
            self.assertIn('5 из 5',panel.quota_label.text())
        finally:
            panel.stop();panel.deleteLater()

    def test_stale_server_response_is_discarded(self):
        panel=AiSearchPanel(client=Mock())
        try:
            with patch.object(panel,'work'):
                panel.set_server('murrieta');old=panel.generation
                panel.set_server('eclipse')
            panel.finish({'generation':old,'phase':'search','value':{'status':'ready','answer':'Wrong server','sources':[]}})
            self.assertNotIn('Wrong server',panel.answer.toPlainText())
        finally:
            panel.stop();panel.deleteLater()

    def test_dedicated_section_preserves_ordinary_search_and_its_own_question(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=QSettings(str(Path(directory)/'test.ini'),QSettings.Format.IniFormat)
            with patch('ai_search.AiClient') as client:
                client.return_value.post.return_value={'quota':{'remaining':5,'limit':5}}
                window=CarleoneWindow(selection_settings=settings,notepad_settings=settings,earnings_settings=settings)
                try:
                    window.search.setText('оружие')
                    window.nav_buttons['ai'].click()
                    self.wait(window.ai_panel)
                    self.assertTrue(window.search.isHidden())
                    self.assertEqual(window.current_records(),[])
                    window.ai_panel.question.setPlainText('Игрок угнал чужую машину')
                    window.nav_buttons['laws'].click()
                    self.assertEqual(window.search.text(),'оружие')
                    window.nav_buttons['ai'].click()
                    self.assertEqual(window.ai_panel.question.toPlainText(),'Игрок угнал чужую машину')
                finally:
                    if window.ai_panel:window.ai_panel.stop()
                    window.close();window.deleteLater()
