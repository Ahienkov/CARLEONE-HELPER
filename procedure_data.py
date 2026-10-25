"""Parse the Murrieta procedural code, preserving chapter-local numbering."""
import json
import re
from pathlib import Path

from road_data import ARTICLE, IMAGE


CHAPTER = re.compile(r"^Глава\s+([IVXLCDM]+)\b\s*(.*)$")


def parse_procedure(text, *, category="Процессуальный", code="ПК"):
    articles = []
    chapter = ""
    chapter_number = ""
    current = None
    seen = set()

    for raw in text.replace("\u200b", "").splitlines():
        line = raw.strip()
        if not line or IMAGE.fullmatch(line):
            continue
        match = CHAPTER.match(line)
        if match:
            chapter, chapter_number = line, match[1]
            current = None
            continue
        match = ARTICLE.match(line)
        if match:
            number, heading = match.groups()
            key = (chapter_number, number)
            if not chapter_number or key in seen:
                raise ValueError(f"Неоднозначная статья: {chapter} / {number}.")
            seen.add(key)
            title = heading if len(heading) <= 110 else heading[:107].rsplit(" ", 1)[0] + "…"
            current = {
                "number": number, "category": category, "code": code,
                "chapter": chapter, "chapter_number": chapter_number,
                "title": title or f"Статья {number}", "description": heading,
                "punishment": "", "keywords": "", "comments": [],
                "source_text": line,
            }
            articles.append(current)
        elif current is not None:
            current["description"] += ("\n" if current["description"] else "") + line
            current["source_text"] += "\n" + line
        else:
            # Keep chapter introductions as independent reference cards.
            number = "Справка"
            current = {
                "number": number, "category": category, "code": code,
                "chapter": chapter, "chapter_number": chapter_number,
                "title": chapter or "Вводные положения", "description": line,
                "punishment": "", "keywords": "", "comments": [], "source_text": line,
            }
            articles.append(current)
    if not seen:
        raise ValueError(f"В исходнике не найдены статьи кодекса {code}.")
    return articles


def load_procedure_articles(source_path=None):
    path = Path(source_path) if source_path else Path(__file__).with_name("procedure_source.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            raise ValueError("Ожидается объект JSON с полем text.")
        articles = parse_procedure(data["text"])
        for article in articles:
            article["source_url"] = data.get("source_url", "")
            article["checked_at"] = data.get("checked_at", "")
        return articles
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
