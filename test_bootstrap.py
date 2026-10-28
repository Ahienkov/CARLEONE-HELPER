import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from bootstrap import verify_distribution


class DistributionTests(unittest.TestCase):
    def test_all_packaged_sections_and_uuid_operations(self):
        self.assertEqual(verify_distribution(), ['laws', 'rules', 'earnings', 'notepad'])

    def test_missing_lazy_dependency_fails_distribution_check(self):
        from main import CarleoneWindow

        def create_window(**kwargs):
            if kwargs['initial_mode'] == 'earnings':
                raise ModuleNotFoundError("No module named 'uuid'")
            return CarleoneWindow(**kwargs)

        with patch('bootstrap.runpy.run_path', return_value={'CarleoneWindow': create_window}):
            with self.assertRaisesRegex(ModuleNotFoundError, 'uuid'):
                verify_distribution()


if __name__ == '__main__':
    unittest.main()
