import unittest
from unittest.mock import Mock

from elevation import ensure_administrator


class ElevationTests(unittest.TestCase):
    def test_old_entry_point_continues_without_requesting_privileges(self):
        api = Mock()
        api.IsUserAnAdmin.return_value = False
        self.assertTrue(ensure_administrator(api))
        api.IsUserAnAdmin.assert_not_called()
        api.ShellExecuteW.assert_not_called()

    def test_normal_startup_needs_no_windows_api(self):
        self.assertTrue(ensure_administrator())
