"""Build and publish the trusted catalog using the owner's existing helper session."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from section_environment import load_section
from server_registry import SERVER_NAMES
from discord_session import SessionStore
from discord_access import load_config
import requests


def build_catalog():
    documents = {}
    for server in SERVER_NAMES:
        for kind in ('laws', 'rules'):
            for row in load_section(server, kind):
                if row.get('category') == 'История изменений' or row['number'].startswith('Справка'):
                    continue
                url = row.get('source_url', '')
                if urlparse(url).hostname != 'forum.gta5rp.com' or not url.startswith('https://'):
                    continue
                code = str(row.get('code', 'Правила' if kind == 'rules' else 'УАК'))[:80]
                key = json.dumps([server, kind, url, code, row['number'], row['title']], ensure_ascii=False)
                ident = hashlib.sha256(key.encode()).hexdigest()
                # Sanctions are kept before potentially long explanatory text.
                body = ('Наказание: ' + row.get('punishment', '') + '\n' + row.get('description', '')).strip()[:7500]
                documents[ident] = dict(id=ident, server=server, kind=kind, title=row['title'][:700], body=body,
                    url=url, code=code, number=row['number'][:120], category=row['category'][:200])
    rows = sorted(documents.values(), key=lambda doc: doc['id'])
    revision = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return dict(revision=revision, documents=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    catalog = build_catalog()
    destination = ROOT / 'build' / 'ai-catalog.json'
    destination.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
    print('Catalog:', len(catalog['documents']), 'articles;', 'revision', catalog['revision'][:12], flush=True)
    if not args.upload:
        return
    config = load_config(ROOT)
    saved = SessionStore(ROOT, config['service_url']).load()
    if not saved:
        raise SystemExit('Sign in to the helper as the owner before importing.')
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + saved['session_key']
    identity = {key: saved[key] for key in ('install_id', 'release_id')}
    def post(data):
        for retry in range(4):
            result = session.post(config['service_url'] + '/v1/ai/admin/import', json={**identity, **data}, timeout=(5, 60), allow_redirects=False)
            if result.status_code in (429, 503) and retry < 3:
                time.sleep(3)
                continue
            if result.status_code != 200:
                raise SystemExit(f'Import failed {result.status_code}: {result.text[:300]}')
            return result.json()
    batch = []
    sent = 0
    for doc in catalog['documents']:
        batch.append(doc)
        if len(batch) >= 120 or len(json.dumps(batch, ensure_ascii=False).encode()) > 380000:
            post(dict(revision=catalog['revision'], documents=batch))
            sent += len(batch)
            batch = []
            print('Uploaded', sent, flush=True)
    if batch:
        post(dict(revision=catalog['revision'], documents=batch))
    print(post(dict(revision=catalog['revision'], publish=True, count=len(catalog['documents']))), flush=True)


if __name__ == '__main__':
    main()
