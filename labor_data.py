"""Load the saved Murrieta labor code with complete article text."""
import json
from pathlib import Path

from procedure_data import parse_procedure


def parse_labor(text):
    return parse_procedure(text, category="Трудовой", code="ТК")


def load_labor_articles(source_path=None):
    path = Path(source_path) if source_path else Path(__file__).with_name("labor_source.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            raise ValueError("Ожидается объект JSON с полем text.")
        articles = parse_labor(data["text"])
        for article in articles:
            article["source_url"] = data.get("source_url", "")
            article["checked_at"] = data.get("checked_at", "")
        return articles
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
