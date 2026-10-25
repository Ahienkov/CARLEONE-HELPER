import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from bs4 import BeautifulSoup
from PySide6.QtWidgets import QApplication

import forum_sync
from forum_sync import ROOT, SNAPSHOTS, ForumSync, fingerprint, install_bundle, read_json
from forum_updates import ForumUpdates
from main import CarleoneWindow, SERVER_DATA


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        for name in SNAPSHOTS:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.payload = {name: read_json(self.root / name) for name in SNAPSHOTS}
        self.original = {name: (self.root / name).read_bytes() for name in SNAPSHOTS}

    def tearDown(self):
        self.temp.cleanup()

    def test_unchanged_content_is_not_rewritten(self):
        for value in self.payload.values():
            value['checked_at'] = 'new check time'
        self.assertEqual(install_bundle(self.root, self.payload)['changed_files'], [])
        for name in SNAPSHOTS:
            self.assertEqual((self.root / name).read_bytes(), self.original[name])

    def test_valid_change_installs_with_previous_backup(self):
        name = 'road_source.json'
        self.payload[name]['text'] += '\nПримечание: Проверка автоматического обновления.'
        result = install_bundle(self.root, self.payload)
        self.assertEqual(result['changed_files'], [name])
        self.assertEqual((self.root / (name + '.bak')).read_bytes(), self.original[name])
        self.assertTrue(any('Проверка автоматического обновления' in a['description'] for a in result['catalog']['laws']))

    def test_invalid_download_does_not_replace_any_data(self):
        self.payload['road_source.json']['text'] = ''
        self.payload['codex_source.json']['text'] += '\nНовое примечание.'
        with self.assertRaises(RuntimeError):
            install_bundle(self.root, self.payload)
        for name in SNAPSHOTS:
            self.assertEqual((self.root / name).read_bytes(), self.original[name])

    def test_failed_commit_rolls_back_previous_files(self):
        self.payload['road_source.json']['text'] += '\nПримечание: новая запись.'
        self.payload['procedure_source.json']['text'] += '\nПримечание: новая запись.'
        actual_replace = forum_sync.os.replace
        failed = False
        def replace(source, destination):
            nonlocal failed
            if Path(destination).name == 'procedure_source.json' and not failed:
                failed = True
                raise OSError('Simulated file lock')
            return actual_replace(source, destination)
        with patch('forum_sync.os.replace', side_effect=replace):
            with self.assertRaises(OSError):
                install_bundle(self.root, self.payload)
        for name in SNAPSHOTS:
            self.assertEqual((self.root / name).read_bytes(), self.original[name])

    def test_unavailable_forum_keeps_local_database(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = TimeoutError('offline')
        with self.assertRaises(TimeoutError):
            ForumSync(self.root, session=session).run()
        session.close.assert_called_once()
        for name in SNAPSHOTS:
            self.assertEqual((self.root / name).read_bytes(), self.original[name])

    def test_new_topics_are_discovered_in_all_four_forums(self):
        sync = ForumSync(self.root)
        def fetch(url):
            index = next(i for i, (_, address) in enumerate(forum_sync.FORUMS) if address == url)
            return BeautifulSoup(f'<div class="structItem-title"><a href="/threads/rules.{100 + index}/">New topic</a></div>', 'html.parser')
        def topic(url):
            return BeautifulSoup('<h1 class="p-title-value">New rules</h1><div class="message-body"><div class="bbWrapper">1.1 ' + 'Правило с подробным описанием. ' * 5 + '</div></div>', 'html.parser')
        with patch.object(sync, 'fetch', side_effect=fetch), patch.object(sync, 'topic', side_effect=topic):
            data = sync.collect_rules({'documents': [], 'server_topic_urls': []}, 'now')
        self.assertEqual(len(data['documents']), 4)
        self.assertEqual(len({d['category'] for d in data['documents']}), 4)
        self.assertEqual(len(data['server_topic_urls']), 4)
        sync.session.close()


class UpdateUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_only_startup_timer_and_explicit_refresh(self):
        manager = ForumUpdates(self.app)
        window = CarleoneWindow()
        try:
            with patch('forum_updates.QApplication') as application:
                application.platformName.return_value = 'windows'
                manager.attach(window)
                self.assertTrue(manager.start_timer.isActive())
                self.assertTrue(manager.start_timer.isSingleShot())
                manager.start_timer.stop()
                manager.attach(window)
                self.assertFalse(manager.start_timer.isActive())
            self.assertFalse(hasattr(manager, 'timer'))
            with patch('forum_updates.threading.Thread') as thread:
                manager.check_now()
                manager.check_now()
                thread.assert_called_once()
        finally:
            manager.stop()
            self.app.aboutToQuit.disconnect(manager.stop)
            manager.deleteLater()
            window.close()
            window.deleteLater()

    def test_apply_new_data_keeps_query_category_and_visibility(self):
        window = CarleoneWindow(copy.deepcopy(SERVER_DATA))
        try:
            next(b for b in window.category_group.buttons() if b.text() == 'Дорожный').click()
            window.search.setText('69')
            window.update_search()
            data = copy.deepcopy(window.server_data['murrieta'])
            target = next(a for a in data['laws'] if a['category'] == 'Дорожный' and a['number'] == '69')
            target['description'] += '\nОбновлённый текст с форума.'
            window.apply_forum_update(data)
            self.assertEqual(window.category, 'Дорожный')
            self.assertEqual(window.search.text(), '69')
            self.assertFalse(window.isVisible())
            self.assertEqual(window.filtered_articles[0]['number'], '69')
            self.assertIn('Обновлённый текст', window.filtered_articles[0]['description'])
        finally:
            window.close()
            window.deleteLater()


if __name__ == '__main__':
    unittest.main()
