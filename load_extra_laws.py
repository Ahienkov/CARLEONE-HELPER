"""Download the three additional laws and validate before replacing the snapshot."""
import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from download_rules import extract_text
from extra_laws_data import EXTRA_LAWS, SOURCE_PATH, parse_extra_law


def download():
    documents = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "CarleoneHelper/0.1"
        for law in EXTRA_LAWS:
            response = session.get(law["url"], timeout=(10, 40))
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            posts = soup.select(".message-body .bbWrapper")
            if not posts or soup.select_one(".pageNav-jump--next"):
                raise ValueError(f"Текст закона отсутствует или содержит дополнительные страницы: {law['category']}")
            text = "\n\n".join(extract_text(post) for post in posts)
            if len(text) < 500 or "Статья " not in text:
                raise ValueError(f"Неполный текст закона: {law['category']}")
            document = {
                "title": soup.select_one(".p-title-value").get_text(" ", strip=True),
                "category": law["category"], "code": law["code"],
                "source_url": law["url"], "checked_at": datetime.now(timezone.utc).isoformat(),
                "text": text,
            }
            records = parse_extra_law(document)
            print(f"{law['category']}: {len(records)} записей, {len(text)} символов", flush=True)
            documents.append(document)
    temporary = SOURCE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"server_id": "murrieta", "documents": documents}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SOURCE_PATH)


if __name__ == "__main__":
    download()
