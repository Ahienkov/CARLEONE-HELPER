import os
import subprocess
import unittest
from unittest.mock import Mock, patch

import elevation


class ElevationTests(unittest.TestCase):
    def test_already_elevated_process_does_not_request_consent_again(self):
        api = Mock()
        api.IsUserAnAdmin.return_value = True
        with patch.object(elevation.sys, 'platform', 'win32'):
            self.assertTrue(elevation.ensure_administrator(api))
        api.ShellExecuteW.assert_not_called()

    def test_source_launch_uses_bootstrap_and_quotes_user_arguments(self):
        api = Mock()
        api.IsUserAnAdmin.return_value = False
        api.ShellExecuteW.return_value = 42
        with patch.object(elevation.sys, 'platform', 'win32'), \
             patch.object(elevation.sys, 'frozen', False, create=True), \
             patch.object(elevation.sys, 'executable', 'C:/Missing Python/python.exe'), \
             patch.object(elevation.sys, 'argv', ['main.py', '--note', 'текст с пробелами']):
            self.assertFalse(elevation.ensure_administrator(api))
        call = api.ShellExecuteW.call_args.args
        self.assertEqual(call[1], 'runas')
        self.assertEqual(call[3], subprocess.list2cmdline([
            str(elevation.Path(elevation.__file__).resolve().parent / 'bootstrap.py'),
            '--note', 'текст с пробелами']))

    def test_frozen_restart_resets_bootloader_environment_and_restores_parent(self):
        api = Mock()
        api.IsUserAnAdmin.return_value = False
        def launch(*args):
            self.assertEqual(os.environ['PYINSTALLER_RESET_ENVIRONMENT'], '1')
            self.assertEqual(args[3], '--example')
            return 42
        api.ShellExecuteW.side_effect = launch
        with patch.object(elevation.sys, 'platform', 'win32'), \
             patch.object(elevation.sys, 'frozen', True, create=True), \
             patch.object(elevation.sys, 'executable', 'C:/Example App/GTA 5 RP HELPER.exe'), \
             patch.object(elevation.sys, 'argv', ['GTA 5 RP HELPER.exe', '--example']), \
             patch.dict(os.environ, {'PYINSTALLER_RESET_ENVIRONMENT': 'previous'}):
            self.assertFalse(elevation.ensure_administrator(api))
            self.assertEqual(os.environ['PYINSTALLER_RESET_ENVIRONMENT'], 'previous')

    def test_declining_consent_never_continues_with_normal_privileges(self):
        api = Mock()
        api.IsUserAnAdmin.return_value = False
        api.ShellExecuteW.return_value = 5
        with patch.object(elevation.sys, 'platform', 'win32'):
            self.assertFalse(elevation.ensure_administrator(api))
        api.ShellExecuteW.assert_called_once()

    def test_non_windows_does_not_use_windows_api(self):
        api = Mock()
        with patch.object(elevation.sys, 'platform', 'linux'):
            self.assertTrue(elevation.ensure_administrator(api))
        api.IsUserAnAdmin.assert_not_called()
