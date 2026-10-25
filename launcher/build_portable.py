"""Build a portable Windows distribution and its source update package."""
import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from build_release import ROOT, build_release


def build(version, repository):
    url = f'https://github.com/{repository}/releases/download/v{version}/carleone-helper-{version}.zip'
    update_zip, manifest = build_release(ROOT, url, version)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed', '--uac-admin',
        '--name', 'GTA 5 RP HELPER', '--icon', str(ROOT / 'assets/app-icon.ico'),
        '--distpath', str(ROOT / 'build/portable'), '--workpath', str(ROOT / 'build/pyinstaller'),
        '--specpath', str(ROOT / 'build'), str(ROOT / 'bootstrap.py'),
    ], cwd=ROOT, check=True)
    application = ROOT / 'build/portable/GTA 5 RP HELPER'
    with zipfile.ZipFile(update_zip) as package:
        package.extractall(application)
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    subprocess.run([str(application / 'GTA 5 RP HELPER.exe'), '--self-test'],
                   cwd=application, env=environment, check=True, timeout=60)
    portable_zip = update_zip.parent / f'GTA-5-RP-HELPER-Windows-{version}.zip'
    with zipfile.ZipFile(portable_zip, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(application.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                package.write(path, path.relative_to(application.parent).as_posix())
    print(f'Windows build: {portable_zip}')
    print(f'Application update: {update_zip}')
    print(f'Manifest: {manifest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--repository', default='Ahienkov/CARLEONE-HELPER')
    args = parser.parse_args()
    build(args.version, args.repository)
