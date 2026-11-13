import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse, urlencode

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QWidget
from access_service.server import Config, Service, AccessError, GUILD_ID, ROLE_ID, require_role
from discord_access import Client, LoginError, AccountManager, load_config
from discord_session import SessionStore, windows_crypt


class AccountServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Config('https://accounts.example.com', '123456789012345678', 'secret-for-test', 'bot-for-test',
                             str(Path(self.directory.name) / 'accounts.sqlite3'))
        self.discord = Mock()
        self.discord.exchange.return_value = dict(id='123456789012345678', username='example')
        self.service = Service(self.config, self.discord)
        self.identity = dict(install_id='installation-123456789012345678', release_id='1.0.4')

    def tearDown(self):
        self.directory.cleanup()

    def login(self):
        result = self.service.new_login(self.identity, 'test')
        params = {k: v[0] for k, v in parse_qs(urlparse(result['browser_url']).query).items()}
        self.assertEqual(params['scope'], 'identify guilds.members.read')
        self.assertEqual(params['code_challenge_method'], 'S256')
        self.service.callback(dict(state=params['state'], code='test-code', iss='https://discord.com'))
        response = self.service.poll(result['login_id'], result['polling_secret'])
        return result, params, response

    def test_confirmed_account_and_device_session_survive_service_restart(self):
        _, _, result = self.login()
        restarted = Service(self.config, self.discord)
        checked = restarted.check(result['session_key'], self.identity)
        self.assertEqual(checked['account'], result['account'])
        self.assertEqual(checked['role_id'], ROLE_ID)
        self.discord.check_member.assert_called_with('123456789012345678')
        _, _, second = self.login()
        self.assertEqual(second['account']['id'], result['account']['id'])
        with self.assertRaises(AccessError):
            restarted.check(result['session_key'], self.identity)
        database_bytes = Path(self.config.database).read_bytes()
        self.assertNotIn(second['session_key'].encode(), database_bytes)
        self.assertNotIn(b'bot-for-test', database_bytes)

    def test_role_is_required_even_for_a_server_member(self):
        for member in ({'roles': []}, {'roles': [GUILD_ID]}, {'roles': [ROLE_ID], 'pending': True}):
            with self.assertRaises(AccessError):
                require_role(member)
        require_role({'roles': [ROLE_ID], 'pending': False})

    def test_removed_role_revokes_saved_device_session(self):
        _, _, result = self.login()
        self.discord.check_member.side_effect = AccessError(403, 'Нет роли')
        with self.assertRaises(AccessError) as error:
            self.service.check(result['session_key'], self.identity)
        self.assertEqual(error.exception.status, 403)
        self.discord.check_member.side_effect = None
        with self.assertRaises(AccessError) as error:
            self.service.check(result['session_key'], self.identity)
        self.assertEqual(error.exception.status, 401)

    def test_network_problem_preserves_device_session(self):
        _, _, result = self.login()
        self.discord.check_member.side_effect = AccessError(503, 'Недоступно')
        with self.assertRaises(AccessError):
            self.service.check(result['session_key'], self.identity)
        self.discord.check_member.side_effect = None
        self.assertEqual(self.service.check(result['session_key'], self.identity)['status'], 'authorized')

    def test_update_or_other_installation_cannot_reuse_session(self):
        _, _, result = self.login()
        for identity in ({**self.identity, 'release_id': '1.0.5'},
                         {**self.identity, 'install_id': 'another-installation-123456789'}):
            with self.assertRaises(AccessError) as error:
                self.service.check(result['session_key'], identity)
            self.assertEqual(error.exception.status, 401)

    def test_oauth_state_and_poll_secret_are_single_use_and_independent(self):
        login, params, result = self.login()
        with self.assertRaises(AccessError):
            self.service.callback(dict(state=params['state'], code='test-code'))
        with self.assertRaises(AccessError):
            self.service.poll(login['login_id'], login['polling_secret'])
        other = self.service.new_login(self.identity, 'test')
        with self.assertRaises(AccessError):
            self.service.poll(other['login_id'], other['login_id'])
        self.assertNotIn(login['polling_secret'], login['browser_url'])
        self.assertNotIn(result['session_key'], login['browser_url'])

    def test_denied_confirmation_does_not_create_an_account(self):
        login = self.service.new_login(self.identity, 'test')
        state = parse_qs(urlparse(login['browser_url']).query)['state'][0]
        self.discord.exchange.side_effect = AccessError(403, 'Нет роли')
        with self.assertRaises(AccessError):
            self.service.callback(dict(state=state, code='test-code'))
        with self.service.accounts.connect() as database:
            self.assertEqual(database.execute('SELECT count(*) FROM accounts').fetchone()[0], 0)

    def test_expired_login_is_rejected_and_rate_limit_applies(self):
        service = Service(self.config, self.discord, clock=lambda: 1000)
        login = service.new_login(self.identity, 'test')
        service.clock = lambda: 1601
        with self.assertRaises(AccessError):
            service.poll(login['login_id'], login['polling_secret'])
        for _ in range(10):
            service.new_login(self.identity, 'test')
        with self.assertRaises(AccessError) as error:
            service.new_login(self.identity, 'test')
        self.assertEqual(error.exception.status, 429)

    def test_wsgi_does_not_disclose_errors_or_accept_cross_origin_requests(self):
        body = json.dumps(self.identity).encode()
        environ = dict(REQUEST_METHOD='POST', PATH_INFO='/v1/login', CONTENT_TYPE='application/json',
                       CONTENT_LENGTH=str(len(body)), REMOTE_ADDR='test', **{'wsgi.input': io.BytesIO(body)})
        start = Mock()
        self.service({**environ, 'HTTP_ORIGIN': 'https://other.example'}, start)
        self.assertTrue(start.call_args.args[0].startswith('403'))
        with patch.object(self.service, 'new_login', side_effect=RuntimeError('secret-for-test')):
            result = b''.join(self.service(environ, start))
        self.assertTrue(start.call_args.args[0].startswith('503'))
        self.assertNotIn(b'secret-for-test', result)


class DeviceSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / 'version.json').write_text('{"version":"1.0.4"}')
        self.store = SessionStore(self.root, 'https://accounts.example.com', protect=lambda b: b, unprotect=lambda b: b)
        self.session = dict(session_key='x' * 64, install_id='i' * 32, account={'id': 'account'})

    def tearDown(self):
        self.directory.cleanup()

    def test_relaunch_keeps_entry_and_release_update_requires_login(self):
        self.store.save(self.session)
        store = SessionStore(self.root, 'https://accounts.example.com', protect=lambda b: b, unprotect=lambda b: b)
        self.assertEqual(store.load()['session_key'], self.session['session_key'])
        (self.root / 'version.json').write_text('{"version":"1.0.5"}')
        upgraded = SessionStore(self.root, 'https://accounts.example.com', protect=lambda b: b, unprotect=lambda b: b)
        self.assertIsNone(upgraded.load())

    def test_clean_reinstall_and_corrupted_session_require_login(self):
        self.store.save(self.session)
        self.store.clear()
        self.assertIsNone(self.store.load())
        self.store.path.write_text('{broken')
        self.assertIsNone(self.store.load())

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_real_windows_protection_and_installation_binding(self):
        store = SessionStore(self.root, 'https://accounts.example.com')
        store.save(self.session)
        self.assertEqual(store.load()['session_key'], self.session['session_key'])
        self.assertNotIn(self.session['session_key'], store.path.read_text())
        changed = SessionStore(self.root, 'https://different.example.com')
        self.assertIsNone(changed.load())

    def test_enabled_configuration_fails_closed_without_service(self):
        config = dict(enabled=True, service_url='', guild_id=GUILD_ID, role_id=ROLE_ID)
        (self.root / 'discord_access.json').write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            load_config(self.root)


class AccountUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_saved_account_checks_silently_and_role_loss_locks_app(self):
        store = Mock()
        store.load.return_value = dict(install_id='i' * 32, release_id='1.0.4', session_key='s' * 64)
        manager = AccountManager(self.app, {'service_url': 'https://accounts.example.com'}, '.', QWidget, store=store, client=Mock())
        try:
            with patch.object(manager, 'work') as work, patch('discord_access.QDesktopServices.openUrl') as browser:
                manager.retry()
                self.assertEqual(work.call_args.args[0], 'check')
                browser.assert_not_called()
            manager.finish(dict(phase='check', generation=0, value=dict(status='authorized', account={'id': 'a', 'display_name': 'Test', 'discord_id': '123'})))
            self.assertTrue(manager.authorized)
            self.assertTrue(manager.window().isEnabled())
            manager.finish(dict(phase='check', generation=0, error='Нет роли', status=403))
            self.assertFalse(manager.authorized)
            self.assertFalse(manager.window().isEnabled())
            self.assertFalse(manager.window().isVisible())
            store.clear.assert_called_once()
        finally:
            manager.stop()
            manager.dialog.hide()
            if manager.window() is not None:
                manager.window().close()
                manager.window().deleteLater()
            self.app.aboutToQuit.disconnect(manager.stop)
            manager.dialog.deleteLater()
            manager.deleteLater()
            self.app.setQuitOnLastWindowClosed(True)

    def test_credentials_submit_uses_password_login_and_clears_password_fields(self):
        store = Mock()
        store.load.return_value = None
        store.new_identity.return_value = dict(install_id='i' * 32, release_id='1.0.4')
        client = Mock()
        manager = AccountManager(self.app, {'service_url': 'https://accounts.example.com'}, '.', QWidget, store=store, client=client)
        try:
            name, password, _ = manager.dialog.fields['login']
            name.setText('TestUser')
            password.setText('test-password-12345')
            with patch.object(manager, 'work') as work:
                manager.submit_credentials()
                self.assertEqual(work.call_args.args[0], 'signin')
                work.call_args.args[1]()
            self.assertEqual(client.post.call_args.args[0], '/v2/login')
            self.assertEqual(client.post.call_args.args[1]['username'], 'TestUser')
            self.assertEqual(password.text(), '')
            manager.dialog.select_mode('register')
            name, password, repeat = manager.dialog.fields['register']
            name.setText('TestUser')
            password.setText('test-password-12345')
            repeat.setText('different-password')
            with patch.object(manager, 'work') as work:
                manager.submit_credentials()
                work.assert_not_called()
            self.assertIn('не совпадают', manager.dialog.status.text())
        finally:
            manager.stop()
            manager.dialog.hide()
            self.app.aboutToQuit.disconnect(manager.stop)
            manager.dialog.deleteLater()
            manager.deleteLater()

    def test_legacy_saved_session_requires_choosing_credentials_before_opening_app(self):
        store = Mock()
        store.load.return_value = dict(install_id='i' * 32, release_id='1.0.4', session_key='s' * 64)
        manager = AccountManager(self.app, {'service_url': 'https://accounts.example.com'}, '.', QWidget, store=store, client=Mock())
        try:
            manager.finish(dict(phase='check', generation=0, value=dict(status='setup_required', account={'id': 'a'})))
            self.assertFalse(manager.authorized)
            self.assertTrue(manager.setup_required)
            self.assertIsNone(manager.window())
            self.assertEqual(manager.dialog.tabs.currentIndex(), 1)
            self.assertFalse(manager.dialog.tabs.isTabEnabled(0))
            name, password, repeat = manager.dialog.fields['register']
            name.setText('TestUser')
            password.setText('test-password-12345')
            repeat.setText('test-password-12345')
            with patch.object(manager, 'work') as work:
                manager.submit_credentials()
                self.assertEqual(work.call_args.args[0], 'setup')
                work.call_args.args[1]()
            self.assertEqual(manager.client.post.call_args.args[0], '/v2/account/setup')
            self.assertEqual(manager.client.post.call_args.args[2], 's' * 64)
        finally:
            manager.stop()
            manager.dialog.hide()
            self.app.aboutToQuit.disconnect(manager.stop)
            manager.dialog.deleteLater()
            manager.deleteLater()


if __name__ == '__main__':
    unittest.main()
