"""Fetch the four Murrieta rule forums and keep original topic snapshots."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


FORUMS = [
    ("Общие правила", "https://forum.gta5rp.com/forums/obshchiye-pravila.1699/"),
    ("Госорганизации", "https://forum.gta5rp.com/forums/pravila-dlya-gosudarstvennykh-organizatsii.1700/"),
    ("Криминальные организации", "https://forum.gta5rp.com/forums/pravila-dlya-kriminal-nykh-organizatsii.1701/"),
    ("Неофициальные организации", "https://forum.gta5rp.com/forums/pravila-neofitsial-nykh-organizatsii.1702/"),
]
SNAPSHOT = Path(__file__).with_name("rules") / "murrieta_sources.json"


def rule_links(soup, url):
    links = {}
    for link in soup.select(".message-body .bbWrapper a[href]"):
        title = link.get_text(" ", strip=True)
        target = urljoin(url, link["href"]).split("#")[0].split("?")[0]
        if ("правил" in title.casefold() and urlparse(target).hostname == "forum.gta5rp.com"
                and urlparse(target).path.startswith("/threads/")):
            links[target] = title
    return [{"title": title, "url": target} for target, title in links.items()]


def topic_content(soup):
    posts = soup.select(".message-body .bbWrapper")
    if not posts:
        raise ValueError("No rule text in topic")
    title_node = soup.select_one(".p-title-value")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    title = title.removeprefix("Важно ")
    # Replies announce revisions; the first post contains the current rules.
    return title, extract_text(posts[0]), len(posts), [extract_text(post) for post in posts[1:]]


def extract_text(post):
    for image in post.find_all("img"):
        alt = image.get("alt", "")
        image.replace_with(alt if alt in ("🟩", "🟨", "🟥") else "")
    for br in post.find_all("br"):
        br.replace_with("\n")
    for block in post.find_all(["div", "p", "li", "tr", "h1", "h2", "h3", "h4"]):
        block.insert_before("\n")
        block.insert_after("\n")
    return "\n".join(
        " ".join(line.split()) for line in post.get_text().replace("\u200b", "").splitlines() if line.strip()
    )


def download(refresh=False):
    session = requests.Session()
    session.headers["User-Agent"] = "CarleoneHelper/0.1"
    def fetch(url):
        if urlparse(url).hostname != "forum.gta5rp.com":
            raise ValueError("Unexpected forum hostname")
        response = session.get(url, timeout=(10, 40))
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")

    cached = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {"server_id": "murrieta", "documents": []}
    by_url = {d["source_url"]: d for d in cached["documents"]}
    documents = []
    for category, start in FORUMS:
        queue, visited, topics = [start], set(), {}
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            soup = fetch(url)
            links = soup.select(".structItem-title a[href*='/threads/']")
            if not links:
                raise ValueError(f"No topics in {url}")
            for link in links:
                target = urljoin(url, link["href"]).split("#")[0].split("?")[0]
                topics[target] = link.get_text(" ", strip=True)
            for link in soup.select(".pageNav-jump--next"):
                target = urljoin(url, link["href"])
                if urlparse(target).path.startswith(urlparse(start).path):
                    queue.append(target)
        for url, title in topics.items():
            if not refresh and url in by_url and "additional_posts" in by_url[url]:
                document = dict(by_url[url], category=category)
            else:
                soup = fetch(url)
                links = rule_links(soup, url)
                posts = soup.select(".message-body .bbWrapper")
                if not posts:
                    raise ValueError(f"No rule text in {url}")
                if soup.select_one(".pageNav-jump--next"):
                    raise ValueError(f"Topic has additional pages; review required: {url}")
                actual_title, text, post_count, additional_posts = topic_content(soup)
                if len(text) < 80:
                    raise ValueError(f"Rule topic is too short: {url}")
                document = {"title": actual_title or title, "category": category, "source_url": url,
                            "checked_at": datetime.now(timezone.utc).isoformat(), "text": text,
                            "links": links, "post_count": post_count, "additional_posts": additional_posts}
                by_url[url] = document
                SNAPSHOT.write_text(json.dumps({"server_id": "murrieta", "documents": list(by_url.values())}, ensure_ascii=False, indent=2), encoding="utf-8")
            documents.append(document)
            print(f"{category}: {title} ({len(document['text'])} chars)", flush=True)
    server_topic_urls = [d["source_url"] for d in documents]
    known_ids = {urlparse(d["source_url"]).path.rstrip("/").rsplit(".", 1)[-1] for d in documents}
    dependencies = [(d["category"], link) for d in documents for link in d.get("links", [])]
    for category, link in dependencies:
        url, title = link["url"], link["title"]
        topic_id = urlparse(url).path.rstrip("/").rsplit(".", 1)[-1]
        if topic_id in known_ids:
            continue
        known_ids.add(topic_id)
        if not refresh and url in by_url and "additional_posts" in by_url[url]:
            document = dict(by_url[url], category=category)
        else:
            soup = fetch(url)
            links = rule_links(soup, url)
            posts = soup.select(".message-body .bbWrapper")
            if not posts or soup.select_one(".pageNav-jump--next"):
                raise ValueError(f"Linked rules unavailable or paginated: {url}")
            actual_title, text, post_count, additional_posts = topic_content(soup)
            document = {"title": actual_title or title, "category": category, "source_url": url,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "text": text, "links": links, "post_count": post_count, "additional_posts": additional_posts}
            if len(document["text"]) < 80:
                raise ValueError(f"Linked rules are too short: {url}")
            by_url[url] = document
            SNAPSHOT.write_text(json.dumps({"server_id": "murrieta", "documents": list(by_url.values())}, ensure_ascii=False, indent=2), encoding="utf-8")
        documents.append(document)
        print(f"Linked: {title} ({len(document['text'])} chars)", flush=True)
    SNAPSHOT.write_text(json.dumps({"server_id": "murrieta", "server_topic_urls": server_topic_urls, "documents": documents}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Downloaded {len(documents)} topics.")


if __name__ == "__main__":
    download(refresh="--refresh" in sys.argv)
