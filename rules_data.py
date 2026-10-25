"""Load rules belonging to one server; never fall back to another server."""
import json
from pathlib import Path


def load_rules(server_id, source_path=None):
    path = Path(source_path) if source_path else Path(__file__).with_name("rules") / f"{server_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or data.get("server_id") != server_id:
            raise ValueError("Исходник правил принадлежит другому серверу.")
        documents = data.get("documents")
        if not isinstance(documents, list):
            raise ValueError("Ожидается список разделов documents.")
        result = []
        for document in documents:
            if not isinstance(document, dict) or not isinstance(document.get("title"), str):
                raise ValueError("У раздела правил отсутствует название.")
            if not isinstance(document.get("rules"), list):
                raise ValueError("У раздела отсутствует список rules.")
            seen = set()
            for rule in document["rules"]:
                if not isinstance(rule, dict) or any(
                    not isinstance(rule.get(field), str) or not rule[field].strip()
                    for field in ("number", "description")
                ):
                    raise ValueError("У правила отсутствует номер или текст.")
                identity = rule.get("rule_id", rule["number"])
                if identity in seen:
                    raise ValueError(f"Повтор номера правила {rule['number']} в разделе.")
                seen.add(identity)
                result.append({
                    **rule, "server_id": server_id, "kind": "rule", "code": "Правило",
                    "category": document.get("category", document["title"]),
                    "chapter": document.get("topic_title", document["title"]),
                    "topic_id": document.get("topic_id", document["title"]),
                    "title": rule.get("title", document.get("topic_title", document["title"])),
                    "punishment": rule.get("punishment", ""),
                    "keywords": rule.get("keywords", ""),
                    "source_url": document.get("source_url", ""),
                    "checked_at": document.get("checked_at", ""),
                })
        return result
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
