"""Import public project rules and each server's own additions, with source URLs.

Run explicitly; importing this module performs no network or filesystem writes.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from build_rules import compile_rules
from download_rules import topic_content, rule_links
from rules_data import load_rules
from server_registry import SERVER_NAMES

ROOT = Path(__file__).resolve().parent
BASE = 'https://forum.gta5rp.com/'


def category(title):
    title = title.casefold()
    if 'государств' in title or 'гос.' in title:
        return 'Госорганизации'
    if 'неофициал' in title:
        return 'Неофициальные организации'
    if any(word in title for word in ('криминал', 'банд', 'мафи', 'рейд', 'капт', 'ограблен', 'войн', 'pvp', 'захват', 'террорист')):
        return 'Криминальные организации'
    return 'Общие правила'


class Collector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'CarleoneHelper/1.0 (forum snapshots)'
        self.cache = ROOT / 'build' / 'forum-cache'
        self.cache.mkdir(parents=True, exist_ok=True)

    def fetch(self, url):
        if urlparse(url).hostname != 'forum.gta5rp.com' or urlparse(url).scheme != 'https':
            raise ValueError('Unexpected forum URL')
        import hashlib
        path = self.cache / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        if path.exists():
            return BeautifulSoup(path.read_bytes(), 'html.parser')
        for attempt in range(3):
            response = self.session.get(url, timeout=(10, 40))
            if response.status_code in (429, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            if urlparse(response.url).hostname != 'forum.gta5rp.com':
                raise ValueError('Unexpected redirect')
            path.write_bytes(response.content)
            return BeautifulSoup(response.content, 'html.parser')
        raise RuntimeError(f'Forum unavailable: {url}')

    def listing(self, start):
        queue, seen, topics = [(start, None)], set(), {}
        while queue:
            url, inherited_category = queue.pop(0)
            if url in seen:
                continue
            if len(seen) >= 60:
                raise ValueError('Unexpectedly large rule directory')
            seen.add(url)
            soup = self.fetch(url)
            for node in soup.select('h3.node-title a'):
                target = urljoin(url, node['href'])
                if urlparse(target).path.startswith(('/forums/', '/categories/')):
                    queue.append((target, category(node.get_text(' ', strip=True))))
            for node in soup.select('.structItem-title a[href*="/threads/"]'):
                target = urljoin(url, node['href']).split('?')[0].split('#')[0]
                title = node.get_text(' ', strip=True)
                topics[target] = (title, inherited_category or category(title))
            for node in soup.select('.pageNav-jump--next'):
                target = urljoin(url, node['href'])
                if urlparse(target).path.startswith(urlparse(url).path.split('/page-')[0]):
                    queue.append((target, inherited_category))
        return topics

    def documents(self, topics):
        documents, queue, seen = [], list(topics.items()), set()
        while queue:
            url, (title, group) = queue.pop(0)
            topic_id = urlparse(url).path.rstrip('/').rsplit('.', 1)[-1]
            if topic_id in seen:
                continue
            seen.add(topic_id)
            soup = self.fetch(url)
            actual, text, count, extra = topic_content(soup)
            if len(text) < 30:
                raise ValueError(f'Incomplete topic: {url}')
            links = rule_links(soup, url)
            documents.append(dict(title=actual or title, category=group,
                                  source_url=url, text=text, links=links,
                                  checked_at=datetime.now(timezone.utc).isoformat(),
                                  post_count=count, additional_posts=extra))
            # Cross-links can lead to other servers. Only the explicitly listed
            # topics belong to this scope; global topics are collected separately.
            print(f'  {actual or title}', flush=True)
        return documents

    def run(self):
        home = self.fetch(BASE)
        roots = {a.get_text(' ', strip=True).removeprefix('Сервер ').lower(): urljoin(BASE, a['href'])
                 for a in home.select('h3.node-title a') if a.get_text(' ', strip=True).startswith('Сервер ')}
        project = next(urljoin(BASE, a['href']) for a in home.select('h3.node-title a')
                       if a.get_text(' ', strip=True) == 'Правила проекта')
        project_topics = self.listing(project)
        project_docs = self.documents(project_topics)
        for server_id, name in SERVER_NAMES.items():
            if server_id == 'murrieta':
                continue  # Preserve the existing reviewed Murrieta snapshot.
            print(name, flush=True)
            root = self.fetch(roots[server_id])
            rule_root = next(urljoin(roots[server_id], a['href']) for a in root.select('h3.node-title a')
                             if 'правил' in a.get_text(' ', strip=True).casefold())
            own_topics = self.listing(rule_root)
            own_docs = self.documents(own_topics)
            own_urls = set(own_topics)
            documents = {d['source_url']: d for d in project_docs}
            documents.update({d['source_url']: d for d in own_docs})
            snapshot = dict(server_id=server_id, server_topic_urls=sorted(own_urls), documents=list(documents.values()))
            compiled = compile_rules(snapshot)
            directory = ROOT / 'rules'
            temporary = directory / f'{server_id}.tmp.json'
            temporary.write_text(json.dumps(compiled, ensure_ascii=False, indent=2), encoding='utf-8')
            cards = load_rules(server_id, temporary)
            temporary.replace(directory / f'{server_id}.json')
            (directory / f'{server_id}_sources.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'{name}: {len(documents)} topics, {len(cards)} cards', flush=True)


if __name__ == '__main__':
    Collector().run()
