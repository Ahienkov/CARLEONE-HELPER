"""Read the saved road code without network access."""
import json
import re
from pathlib import Path


ARTICLE = re.compile(r"^Статья\s+(\d+(?:\.\d+)*)(?:\.(?!\d))?\s*(.*)$")
IMAGE = re.compile(r"^(?:https?://\S+|\S+[.-](?:png|jpg|jpeg|gif|webp)(?:\.\d+)?)$", re.I)


def parse_road(text):
    records = []
    current = None
    chapter = "Вводные положения"
    context = []
    references = []

    def save_context():
        if context:
            references.append((chapter, "\n".join(context)))
            context.clear()

    for raw in text.replace("\u200b", "").splitlines():
        line = raw.strip()
        if not line or IMAGE.fullmatch(line):
            continue
        if line == "Вводные положения":
            continue
        if line.startswith("Глава "):
            save_context()
            chapter = line
            current = None
            continue
        match = ARTICLE.match(line)
        if match:
            save_context()
            current = {"number": match[1], "chapter": chapter,
                       "lines": [match[2]] if match[2] else [],
                       "source_lines": [line]}
            records.append(current)
        elif current is not None:
            current["lines"].append(line)
            current["source_lines"].append(line)
        else:
            context.append(line)
    save_context()

    numbers = [r["number"] for r in records]
    if not records or len(numbers) != len(set(numbers)):
        raise ValueError("Статьи дорожного кодекса отсутствуют или их номера повторяются.")

    articles = []
    for record in records:
        body = "\n".join(record["lines"])
        sanction = re.search(r"(?m)^Наказание:\s*", body)
        description = body
        punishment = "Отдельное наказание в этой статье не указано."
        if sanction:
            description = body[:sanction.start()].strip()
            punishment = body[sanction.end():].strip()
            note = re.search(r"(?m)^(?:Примечание|Исключение)\b", punishment)
            if note:
                description += "\n\n" + punishment[note.start():]
                punishment = punishment[:note.start()].strip()
        heading = description.split("\n", 1)[0]
        title = heading if len(heading) <= 110 else heading[:107].rsplit(" ", 1)[0] + "…"
        articles.append({
            "number": record["number"], "category": "Дорожный", "code": "ДК",
            "title": title, "description": description, "punishment": punishment,
            "keywords": "", "source_text": "\n".join(record["source_lines"]),
            "chapter": record["chapter"], "comments": [],
        })
    for index, (heading, body) in enumerate(references, 1):
        articles.append({
            "number": f"Справка {index}", "category": "Дорожный", "code": "ДК",
            "title": heading, "description": body,
            "punishment": "Общие положения дорожного кодекса.",
            "keywords": "", "source_text": body, "chapter": heading, "comments": [],
        })
    return articles


def load_road_articles(source_path=None):
    path = Path(source_path) if source_path else Path(__file__).with_name("road_source.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            raise ValueError("Ожидается объект JSON с полем text.")
        articles = parse_road(data["text"])
        for article in articles:
            article["source_url"] = data.get("source_url", "")
            article["checked_at"] = data.get("checked_at", "")
        return articles
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
