import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import software_update
from launcher.build_release import build_release
from software_update import apply_pending, check_for_update, read_package


class SoftwareUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.directory.name)
        (self.root / 'assets').mkdir()
        (self.root / 'rules').mkdir()
        (self.root / 'version.json').write_text(json.dumps({'version': '1.0.0', 'runtime_version': 1, 'channel': 'stable'}))
        (self.root / 'app_update_config.json').write_text(json.dumps({'repository': 'Ahienkov/CARLEONE-HELPER', 'development_mode': False}))
        for name in ('main.py', 'software_update.py', 'bootstrap.py'):
            (self.root / name).write_text('VALUE = 1\n')
        (self.root / 'main.py').write_text('VALUE = 2\n')
        archive, manifest = build_release(self.root, 'https://github.com/Ahienkov/CARLEONE-HELPER/releases/download/v1.0.1/carleone-helper-1.0.1.zip', '1.0.1')
        self.package = archive.read_bytes()
        self.manifest = json.loads(manifest.read_text())
        (self.root / 'main.py').write_text('VALUE = 1\n')

    def tearDown(self):
        self.directory.cleanup()

    def stage(self):
        pending = self.root / '.updates'
        pending.mkdir(exist_ok=True)
        (pending / 'package.zip').write_bytes(self.package)
        (pending / 'pending.json').write_text(json.dumps(self.manifest))

    def test_apply_verified_update_keeps_previous_version_backup(self):
        self.stage()
        self.assertTrue(apply_pending(self.root))
        self.assertEqual((self.root / 'main.py').read_text(), 'VALUE = 2\n')
        self.assertEqual(json.loads((self.root / 'version.json').read_text())['version'], '1.0.1')
        with zipfile.ZipFile(self.root / '.updates/previous-version.zip') as backup:
            self.assertEqual(backup.read('main.py').decode().replace('\r\n', '\n'), 'VALUE = 1\n')
        self.assertFalse((self.root / '.updates/pending.json').exists())

    def test_bad_checksum_does_not_change_application(self):
        self.stage()
        (self.root / '.updates/package.zip').write_bytes(self.package[:-1] + b'X')
        with self.assertRaises(ValueError):
            apply_pending(self.root)
        self.assertEqual((self.root / 'main.py').read_text(), 'VALUE = 1\n')

    def test_path_traversal_and_case_collisions_rejected(self):
        for bad_name in ('../escape.py', 'MAIN.py'):
            buffer = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.package)) as source, zipfile.ZipFile(buffer, 'w') as target:
                for name in source.namelist():
                    target.writestr(name, source.read(name))
                target.writestr(bad_name, 'VALUE = 3')
            payload = buffer.getvalue()
            manifest = {**self.manifest, 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            with self.assertRaises(ValueError):
                read_package(payload, manifest)

    def test_failed_installation_rolls_back(self):
        self.stage()
        original_replace = software_update.os.replace
        failed = False
        def replace(source, target):
            nonlocal failed
            if Path(target).name == 'main.py' and not failed:
                failed = True
                raise OSError('Locked file')
            return original_replace(source, target)
        with patch('software_update.os.replace', side_effect=replace), self.assertRaises(OSError):
            apply_pending(self.root)
        self.assertEqual((self.root / 'main.py').read_text(), 'VALUE = 1\n')
        self.assertEqual(json.loads((self.root / 'version.json').read_text())['version'], '1.0.0')

    def test_development_folder_is_not_overwritten(self):
        (self.root / 'app_update_config.json').write_text(json.dumps({'development_mode': True}))
        session = Mock()
        self.assertEqual(check_for_update(self.root, session)['state'], 'development')
        session.get.assert_not_called()

    def test_first_unpublished_release_is_normal(self):
        session = Mock()
        session.get.return_value.status_code = 404
        self.assertEqual(check_for_update(self.root, session)['state'], 'no_release')
        session.close.assert_called_once()

    def test_new_package_is_verified_and_staged_without_editing_live_code(self):
        session = Mock()
        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = self.manifest
        download = Mock()
        download.url = self.manifest['package_url']
        download.iter_content.return_value = [self.package]
        context = Mock()
        context.__enter__ = Mock(return_value=download)
        context.__exit__ = Mock(return_value=False)
        session.get.side_effect = [response, context]
        self.assertEqual(check_for_update(self.root, session)['state'], 'ready')
        self.assertTrue((self.root / '.updates/pending.json').exists())
        self.assertEqual((self.root / 'main.py').read_text(), 'VALUE = 1\n')


if __name__ == '__main__':
    unittest.main()
