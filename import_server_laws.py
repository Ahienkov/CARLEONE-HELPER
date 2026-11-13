"""Build offline law snapshots from DOM exports of authenticated forum pages.

No credentials, account headers or private messages are copied into snapshots.
"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from download_rules import extract_text
from server_laws import load_server_laws
from server_registry import SERVER_NAMES

ROOT = Path(__file__).resolve().parent


def build(root=ROOT):
    root = Path(root)
    exports = root / 'build/forum-auth'
    output = root / 'laws'
    output.mkdir(exist_ok=True)
    report = {}
    for server_id, name in SERVER_NAMES.items():
        if server_id == 'murrieta':
            continue
        listing = json.loads((exports / f'{server_id}-directory.json').read_text(encoding='utf-8'))
        documents = []
        for topic in listing['threads']:
            topic_id = topic['url'].rstrip('/').rsplit('.', 1)[-1]
            source = json.loads((exports / f'{server_id}-{topic_id}.json').read_text(encoding='utf-8'))
            if source['server_id'] != server_id or source['source_url'] != topic['url']:
                raise ValueError('Mismatched source export')
            posts = []
            for page in source['pages']:
                if page['url'].split('/page-')[0].rstrip('/') != topic['url'].rstrip('/'):
                    raise ValueError('Wrong topic page')
                server_crumbs = [c for c in page['breadcrumbs'] if c['title'].startswith('Сервер ')]
                if not server_crumbs or any(c['title'].casefold() != f'сервер {name}'.casefold() for c in server_crumbs):
                    raise ValueError(f'Wrong server breadcrumbs: {topic["url"]}')
                for post in page['posts']:
                    soup = BeautifulSoup(post['html'], 'html.parser')
                    images = [img.get('src', '') for img in soup.select('img[src]')
                              if not img.get('class') or 'smilie' not in img.get('class', [])]
                    text = extract_text(soup)
                    if not text.strip() and images:
                        text = 'Документ опубликован изображением. См. оригинал на форуме:\n' + '\n'.join(images)
                    if text.strip():
                        posts.append(dict(post_id=post['id'], text=text, images=images))
            if not posts:
                raise ValueError(f'Empty law: {topic["url"]}')
            documents.append(dict(document_id=topic_id, title=topic['title'], source_url=topic['url'],
                                  checked_at=source['checked_at'], text='\n\n'.join(p['text'] for p in posts), posts=posts))
        bundle = dict(server_id=server_id, source_url=listing['url'], checked_at=max(d['checked_at'] for d in documents),
                      directory_pages=listing['pages'], documents=documents)
        temporary = output / f'{server_id}.tmp.json'
        temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        cards = load_server_laws(server_id, temporary)
        temporary.replace(output / f'{server_id}_sources.json')
        report[server_id] = dict(documents=len(documents), cards=len(cards), source_url=listing['url'])
        print(name, report[server_id], flush=True)
    (root / 'build/server-data-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    build()
