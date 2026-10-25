"""Fetch, validate and atomically install forum data; never download executable code."""
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from build_rules import compile_rules
from codex_data import load_articles
from download_rules import FORUMS, rule_links, topic_content, extract_text
from extra_laws_data import EXTRA_LAWS, load_extra_laws
from labor_data import load_labor_articles
from load_codex import extract_codex_text
from procedure_data import load_procedure_articles
from road_data import load_road_articles
from rules_data import load_rules


ROOT = Path(__file__).resolve().parent
SNAPSHOTS = (
    "codex_source.json", "road_source.json", "procedure_source.json", "labor_source.json",
    "extra_laws_source.json", "rules/murrieta_sources.json", "rules/murrieta.json",
)
CODE_LOADERS = (
    ("codex_source.json", load_articles), ("road_source.json", load_road_articles),
    ("procedure_source.json", load_procedure_articles), ("labor_source.json", load_labor_articles),
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fingerprint(data):
    def meaningful(item):
        if isinstance(item, dict):
            return {k: meaningful(v) for k, v in item.items() if k != "checked_at"}
        if isinstance(item, list):
            return [meaningful(v) for v in item]
        return item
    return hashlib.sha256(json.dumps(meaningful(data), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def guard_text(text, previous, minimum=80):
    if len(text.strip()) < minimum or (previous and len(text) < len(previous) * 0.35):
        raise ValueError("Форум вернул слишком короткий или неполный текст; сохранённая база оставлена.")


def validate_bundle(root):
    laws = [article for name, loader in CODE_LOADERS for article in loader(root / name)]
    laws += load_extra_laws(root / "extra_laws_source.json")
    rules = load_rules("murrieta", root / "rules/murrieta.json")
    if not laws or not rules:
        raise ValueError("Обновлённая база пуста.")
    return {"name": "Murrieta", "laws": laws, "rules": rules}


def install_bundle(root, payloads, stop_event=None):
    """Validate all files first; keep backups and roll back a failed installation."""
    changed = [name for name, value in payloads.items()
               if fingerprint(value) != fingerprint(read_json(root / name))]
    with tempfile.TemporaryDirectory(prefix=".forum-update-", dir=root) as directory:
        stage = Path(directory)
        for name, value in payloads.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        catalog = validate_bundle(stage)
        if stop_event is not None and stop_event.is_set():
            raise InterruptedError("Проверка остановлена.")
        old = {name: (root / name).read_bytes() for name in changed}
        installed = []
        try:
            for name in changed:
                target = root / name
                backup = target.with_suffix(target.suffix + ".bak")
                backup.write_bytes(old[name])
                os.replace(stage / name, target)
                installed.append(name)
        except Exception:
            for name in reversed(installed):
                rollback = stage / name
                rollback.write_bytes(old[name])
                os.replace(rollback, root / name)
            raise
    return {"changed_files": changed, "catalog": catalog}


class ForumSync:
    def __init__(self, root=ROOT, session=None, stop_event=None, progress=None):
        self.root = Path(root)
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = "CarleoneHelper/0.1"
        self.stop = stop_event or threading.Event()
        self.progress = progress or (lambda message: None)
        self.cache = {}

    def fetch(self, url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "forum.gta5rp.com":
            raise ValueError("Разрешены только HTTPS-страницы форума GTA5RP.")
        if self.stop.is_set():
            raise InterruptedError("Проверка остановлена.")
        if url not in self.cache:
            response = self.session.get(url, timeout=(5, 20))
            response.raise_for_status()
            if urlparse(response.url).hostname != "forum.gta5rp.com":
                raise ValueError("Форум перенаправил запрос на другой сайт.")
            self.cache[url] = response.content
        return BeautifulSoup(self.cache[url], "html.parser")

    def topic(self, url):
        soup = self.fetch(url)
        if soup.select_one(".pageNav-jump--next"):
            raise ValueError(f"Структура темы изменилась: обнаружены дополнительные страницы ({url}).")
        return soup

    def collect_rules(self, previous, checked_at):
        old_topics = {d["source_url"]: d for d in previous["documents"]}
        documents, fetched, server_urls = [], set(), []

        def add_topic(url, title, category):
            topic_id = urlparse(url).path.rstrip("/").rsplit(".", 1)[-1]
            if topic_id in fetched:
                return
            fetched.add(topic_id)
            self.progress(title)
            soup = self.topic(url)
            links = rule_links(soup, url)
            actual_title, text, count, extra = topic_content(soup)
            guard_text(text, old_topics.get(url, {}).get("text", ""))
            documents.append({"title": actual_title or title, "category": category,
                              "source_url": url, "checked_at": checked_at, "text": text,
                              "links": links, "post_count": count, "additional_posts": extra})

        for category, start in FORUMS:
            queue, visited = [start], set()
            while queue:
                url = queue.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 20:
                    raise ValueError("Слишком много страниц в разделе правил.")
                visited.add(url)
                soup = self.fetch(url)
                links = soup.select(".structItem-title a[href*='/threads/']")
                if not links:
                    raise ValueError("В разделе форума не найдены темы правил.")
                for link in links:
                    target = urljoin(url, link["href"]).split("#")[0].split("?")[0]
                    server_urls.append(target)
                    add_topic(target, link.get_text(" ", strip=True), category)
                for link in soup.select(".pageNav-jump--next"):
                    target = urljoin(url, link["href"])
                    if urlparse(target).path.startswith(urlparse(start).path):
                        queue.append(target)
        server_urls = list(dict.fromkeys(server_urls))
        if len(server_urls) < len(previous["server_topic_urls"]) * 0.35:
            raise ValueError("Список тем правил выглядит неполным.")
        dependencies = [(d["category"], link) for d in documents for link in d["links"]]
        for category, link in dependencies:
            add_topic(link["url"], link["title"], category)
        return {"server_id": "murrieta", "server_topic_urls": server_urls, "documents": documents}

    def run(self):
        checked_at = datetime.now(timezone.utc).isoformat()
        previous = {name: read_json(self.root / name) for name in SNAPSHOTS}
        payloads = {}
        try:
            for name, _loader in CODE_LOADERS:
                old = previous[name]
                self.progress(name)
                text = extract_codex_text(self.topic(old["source_url"]))
                guard_text(text, old["text"], minimum=500)
                payloads[name] = {**old, "checked_at": checked_at, "text": text}
            extra = []
            old_extra = {d["source_url"]: d for d in previous["extra_laws_source.json"]["documents"]}
            for law in EXTRA_LAWS:
                self.progress(law["category"])
                soup = self.topic(law["url"])
                posts = soup.select(".message-body .bbWrapper")
                if not posts:
                    raise ValueError("Текст закона не найден.")
                text = "\n\n".join(extract_text(post) for post in posts)
                guard_text(text, old_extra[law["url"]]["text"], minimum=500)
                extra.append({**old_extra[law["url"]], "text": text, "checked_at": checked_at})
            payloads["extra_laws_source.json"] = {"server_id": "murrieta", "documents": extra}
            sources = self.collect_rules(previous["rules/murrieta_sources.json"], checked_at)
            payloads["rules/murrieta_sources.json"] = sources
            payloads["rules/murrieta.json"] = compile_rules(sources)
            result = install_bundle(self.root, payloads, self.stop)
            result["checked_at"] = checked_at
            return result
        finally:
            self.session.close()


if __name__ == "__main__":
    result = ForumSync(progress=print).run()
    print("Изменённые файлы:", result["changed_files"])
