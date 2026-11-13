"""Cross-server isolation, complete source retention and real selector coverage."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from main import CarleoneWindow
from section_environment import load_section
from server_laws import load_server_laws, parse_law
from server_registry import SERVER_NAMES
from suspect_selection import article_key

ROOT = Path(__file__).parent


class ServerDataTests(unittest.TestCase):
    def test_each_new_server_covers_its_complete_directory(self):
        for server in SERVER_NAMES:
            if server == 'murrieta':
                continue
            data = json.loads((ROOT / 'laws' / f'{server}_sources.json').read_text(encoding='utf-8'))
            cards = load_server_laws(server)
            self.assertGreater(len(cards), 500, server)
            self.assertEqual({a['document_id'] for a in cards}, {d['document_id'] for d in data['documents']})
            self.assertEqual({a['server_id'] for a in cards}, {server})
            self.assertEqual(len({article_key(a) for a in cards}), len(cards), server)
            for document in data['documents']:
                parsed = [a for a in cards if a['document_id'] == document['document_id']]
                expected = '\n'.join(line.strip() for line in document['text'].splitlines() if line.strip())
                actual = '\n'.join(line.strip() for a in parsed for line in a['source_text'].splitlines() if line.strip())
                self.assertEqual(actual, expected, document['title'])

    def test_rules_only_contain_project_topics_and_own_server_topics(self):
        # Offline snapshots retain the exact category membership from collection.
        for server in SERVER_NAMES:
            cards = load_section(server, 'rules')
            self.assertTrue(cards, server)
            self.assertEqual({a['server_id'] for a in cards}, {server})
            self.assertEqual(len({article_key(a) for a in cards}), len(cards))
            if server == 'murrieta':
                continue
            data = json.loads((ROOT / 'rules' / f'{server}_sources.json').read_text(encoding='utf-8'))
            own = set(data['server_topic_urls'])
            compiled = json.loads((ROOT / 'rules' / f'{server}.json').read_text(encoding='utf-8'))
            for document in compiled['documents']:
                scope = SERVER_NAMES[server] if document['source_url'] in own else 'Правила проекта'
                self.assertTrue(document['topic_title'].endswith(' · ' + scope))

    def test_chapter_local_numbers_and_inline_comments_stay_distinct(self):
        document = dict(document_id='1', title='Процессуальный кодекс', source_url='https://forum.gta5rp.com/threads/code.1/',
                        checked_at='2026-11-13', text='Глава I. Начало\nСтатья 1. Первая\nКомментарий: пояснение\nСтатья 2. Вторая\nГлава II. Продолжение\nСтатья 1. Третья')
        cards = [a for a in parse_law(document, 'eclipse') if a['number'] != 'Справка']
        self.assertEqual([a['number'] for a in cards], ['1', '2', '1'])
        self.assertIn('Комментарий: пояснение', cards[0]['description'])
        self.assertEqual(len({article_key(a) for a in cards}), 3)

    def test_wrong_server_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            load_server_laws('eclipse', ROOT / 'laws' / 'downtown_sources.json')

    def test_all_servers_switch_both_sections_and_filter_law_topics(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat)
            window = CarleoneWindow(selection_settings=settings, earnings_settings=settings, notepad_settings=settings)
            try:
                for server in SERVER_NAMES:
                    for mode_index, mode in enumerate(('laws', 'rules')):
                        window.mode_selector.setCurrentIndex(mode_index)
                        window.server.setCurrentIndex(window.server.findData(server))
                        records = window.current_records()
                        self.assertTrue(records, (server, mode))
                        self.assertEqual(window.environments[mode].server, server)
                        self.assertIsNone(window.environments['rules' if mode == 'laws' else 'laws'].records)
                        self.assertEqual(set(window.search_index), {(server, mode)})
                        if mode == 'laws' and server != 'murrieta':
                            self.assertGreater(window.topic.count(), 20)
                            window.topic.setCurrentIndex(1)
                            self.assertTrue(window.filtered_articles)
                            self.assertEqual({a['topic_id'] for a in window.filtered_articles}, {window.topic.currentData()})
                            window.topic.setCurrentIndex(0)
            finally:
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
