import ctypes
import unittest
from unittest.mock import Mock
from foreground_access import ForegroundAccess


class ForegroundAccessTests(unittest.TestCase):
    def setUp(self):
        self.access = ForegroundAccess.__new__(ForegroundAccess)
        self.access.kernel = Mock()
        self.access.security = Mock()
        self.access.user32 = Mock()
        self.access.own_elevated = False
        self.access.kernel.OpenProcess.return_value = 100

        def open_token(process, access, token):
            token._obj.value = 200
            return True

        self.access.security.OpenProcessToken.side_effect = open_token

    def test_token_handles_are_closed_after_success_and_query_failure(self):
        def query(token, kind, value, size, returned):
            ctypes.cast(value, ctypes.POINTER(ctypes.c_ulong)).contents.value = 1
            return True

        self.access.security.GetTokenInformation.side_effect = query
        self.assertTrue(self.access.process_elevated(500))
        self.assertEqual(self.access.kernel.CloseHandle.call_args_list[0].args[0].value, 200)
        self.assertEqual(self.access.kernel.CloseHandle.call_args_list[1].args[0], 100)
        self.access.security.GetTokenInformation.side_effect = None
        self.access.security.GetTokenInformation.return_value = False
        self.access.kernel.CloseHandle.reset_mock()
        self.assertIsNone(self.access.process_elevated(500))
        self.assertEqual(self.access.kernel.CloseHandle.call_count, 2)

    def test_denied_process_or_token_is_unknown_not_elevated(self):
        self.access.kernel.OpenProcess.return_value = 0
        self.assertIsNone(self.access.process_elevated(500))
        self.access.kernel.CloseHandle.assert_not_called()
        self.access.kernel.OpenProcess.return_value = 100
        self.access.security.OpenProcessToken.side_effect = None
        self.access.security.OpenProcessToken.return_value = False
        self.assertIsNone(self.access.process_elevated(500))
        self.access.kernel.CloseHandle.assert_called_once_with(100)

    def test_warning_only_for_known_lower_to_higher_privilege_boundary(self):
        self.access.user32.GetForegroundWindow.return_value = 500
        def foreground_pid(handle, pid):
            pid._obj.value = 600
            return 700
        self.access.user32.GetWindowThreadProcessId.side_effect = foreground_pid
        self.access.process_elevated = Mock(return_value=True)
        self.assertTrue(self.access.blocked())
        self.access.process_elevated.return_value = None
        self.assertFalse(self.access.blocked())
        self.access.process_elevated.return_value = False
        self.assertFalse(self.access.blocked())
        self.access.own_elevated = True
        self.access.process_elevated.return_value = True
        self.assertFalse(self.access.blocked())
