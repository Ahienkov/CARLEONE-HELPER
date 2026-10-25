"""Create a versioned source-update ZIP and a checksum manifest for hosting."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent


def build_release(root, download_url, version=None):
    root = Path(root)
    if urlparse(download_url).scheme != "https" or not urlparse(download_url).hostname:
        raise ValueError("Для пакета обновления требуется HTTPS-ссылка.")
    metadata = json.loads((root / "version.json").read_text(encoding="utf-8"))
    version = version or metadata["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Версия должна иметь формат 1.0.0.")
    metadata["version"] = version
    output = root / "releases" / version
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"carleone-helper-{version}.zip"
    files = [p for p in root.glob("*.py") if not p.name.startswith("test_")]
    files += list(root.glob("*_source.json"))
    files += list((root / "rules").glob("*.json"))
    files += [p for p in (root / "assets").iterdir() if p.suffix.lower() in (".png", ".ico")]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("version.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        config = json.loads((root / 'app_update_config.json').read_text(encoding='utf-8'))
        config['development_mode'] = False
        package.writestr('app_update_config.json', json.dumps(config, ensure_ascii=False, indent=2))
        for path in sorted(files):
            package.write(path, path.relative_to(root).as_posix())
    manifest = {**metadata, "package_url": download_url,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "size": archive.stat().st_size}
    manifest_path = output / "latest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive, manifest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-url", required=True, help="HTTPS-ссылка, по которой будет опубликован ZIP")
    parser.add_argument("--version")
    arguments = parser.parse_args()
    for path in build_release(ROOT, arguments.download_url, arguments.version):
        print(path)
