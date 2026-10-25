"""Versioned GitHub updates: verify a package now, apply it at the next start."""
import hashlib
import io
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parent
MAX_PACKAGE_SIZE = 30 * 1024 * 1024
MAX_UNPACKED_SIZE = 100 * 1024 * 1024


def version_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Некорректная версия приложения.")
    return tuple(int(part) for part in value.split('.'))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_package(payload, manifest):
    if len(payload) != manifest['size'] or len(payload) > MAX_PACKAGE_SIZE:
        raise ValueError("Размер обновления не совпадает с описанием.")
    if hashlib.sha256(payload).hexdigest() != manifest['sha256']:
        raise ValueError("Контрольная сумма обновления не совпадает.")
    files = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 500:
            raise ValueError("Слишком много файлов в обновлении.")
        unpacked_size = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename
                    or path.as_posix() != info.filename or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError("Небезопасный путь внутри обновления.")
            allowed = (len(path.parts) == 1 and path.suffix in ('.py', '.json')) or (
                len(path.parts) == 2 and path.parts[0] in ('assets', 'rules')
                and path.suffix in ('.png', '.ico', '.json'))
            if not allowed or info.filename.casefold() in {name.casefold() for name in files}:
                raise ValueError("Недопустимый или повторный файл в обновлении.")
            unpacked_size += info.file_size
            if unpacked_size > MAX_UNPACKED_SIZE:
                raise ValueError("Распакованный пакет слишком большой.")
            data = archive.read(info)
            if path.suffix == '.py':
                compile(data, info.filename, 'exec')
            elif path.suffix == '.json':
                json.loads(data.decode('utf-8-sig'))
            files[info.filename] = data
    for name in ('main.py', 'version.json', 'software_update.py', 'bootstrap.py', 'app_update_config.json'):
        if name not in files:
            raise ValueError(f"В обновлении отсутствует {name}.")
    metadata = json.loads(files['version.json'])
    if metadata['version'] != manifest['version'] or metadata['runtime_version'] != manifest['runtime_version']:
        raise ValueError("Версия пакета не совпадает с описанием.")
    return files


def check_for_update(root=ROOT, session=None):
    root = Path(root)
    config = read_json(root / 'app_update_config.json')
    if config.get('development_mode', True):
        return {"state": "development"}
    repository = config['repository']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError("Некорректный репозиторий обновлений.")
    local = read_json(root / 'version.json')
    base = f'https://github.com/{repository}/releases/'
    client = session or requests.Session()
    try:
        response = client.get(base + 'latest/download/latest.json', timeout=(5, 15))
        if response.status_code == 404:
            return {"state": "no_release"}
        response.raise_for_status()
        if len(response.content) > 64 * 1024:
            raise ValueError("Описание обновления слишком большое.")
        manifest = response.json()
        if version_key(manifest['version']) <= version_key(local['version']):
            return {"state": "current", "version": local['version']}
        if manifest['runtime_version'] != local['runtime_version']:
            return {"state": "runtime_required", "version": manifest['version'], "url": base + 'latest'}
        url = manifest['package_url']
        if not isinstance(url, str) or not url.startswith(base + 'download/') or '?' in url or '#' in url:
            raise ValueError("Пакет обновления должен находиться в релизах выбранного репозитория.")
        if not isinstance(manifest['size'], int) or not 0 < manifest['size'] <= MAX_PACKAGE_SIZE:
            raise ValueError("Недопустимый размер обновления.")
        pending = root / '.updates'
        pending.mkdir(exist_ok=True)
        with client.get(url, stream=True, timeout=(5, 30)) as download:
            download.raise_for_status()
            hostname = urlparse(download.url).hostname or ''
            if hostname != 'github.com' and not hostname.endswith('.githubusercontent.com'):
                raise ValueError("Неожиданный адрес загрузки обновления.")
            chunks, size = [], 0
            for chunk in download.iter_content(128 * 1024):
                size += len(chunk)
                if size > manifest['size']:
                    raise ValueError("Получено слишком много данных обновления.")
                chunks.append(chunk)
        payload = b''.join(chunks)
        read_package(payload, manifest)
        (pending / 'package.tmp').write_bytes(payload)
        os.replace(pending / 'package.tmp', pending / 'package.zip')
        (pending / 'pending.tmp').write_text(json.dumps(manifest), encoding='utf-8')
        os.replace(pending / 'pending.tmp', pending / 'pending.json')
        return {"state": "ready", "version": manifest['version']}
    finally:
        client.close()


def apply_pending(root=ROOT):
    root = Path(root).resolve()
    pending = root / '.updates'
    description = pending / 'pending.json'
    if not description.exists():
        return False
    manifest = read_json(description)
    metadata = read_json(root / 'version.json')
    if metadata['runtime_version'] != manifest['runtime_version']:
        raise ValueError("Обновление требует новую среду приложения.")
    if version_key(manifest['version']) <= version_key(metadata['version']):
        description.unlink()
        return False
    files = read_package((pending / 'package.zip').read_bytes(), manifest)
    current_config = read_json(root / 'app_update_config.json')
    new_config = json.loads(files['app_update_config.json'])
    if new_config.get('repository') != current_config.get('repository') or new_config.get('development_mode'):
        raise ValueError("Обновление пытается сменить источник версий.")
    originals = {name: (root / name).read_bytes() if (root / name).exists() else None for name in files}
    installed = []
    with tempfile.TemporaryDirectory(prefix='install-', dir=pending) as directory:
        stage = Path(directory)
        for name, data in files.items():
            target = (root / name).resolve()
            if not target.is_relative_to(root) or target.is_symlink():
                raise ValueError("Файл обновления находится вне папки приложения.")
            saved = stage / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(data)
        backup = pending / 'previous-version.zip'
        with zipfile.ZipFile(backup, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in originals.items():
                if data is not None:
                    archive.writestr(name, data)
        try:
            names = [name for name in files if name != 'version.json'] + ['version.json']
            for name in names:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / name, target)
                installed.append(name)
        except Exception:
            for name in reversed(installed):
                target = root / name
                if originals[name] is None:
                    target.unlink(missing_ok=True)
                else:
                    saved = stage / name
                    saved.write_bytes(originals[name])
                    os.replace(saved, target)
            raise
    description.unlink()
    return True
