"""Load rules belonging to one server; never fall back to another server."""
import json
import re
from pathlib import Path


SANCTION = re.compile(
    r'деморган|\bwarn\b|\bban\b|\bkick\b|\bmute\b|\bмут\b|\bбан\b|блокировк|'
    r'предупреждени|выговор|балл|откат|отстранени|дисквалификац|обнулени|'
    r'черн[ыо]й список|чёрный список|принудительн.+смен|удаление бумбокса|'
    r'приравнивается к|наказание в соответствии|IC наказуемо|^слив склада$', re.I)
INLINE_NOTE = re.compile(r'\s+(?=(?:Примечание|Исключение|Пример|Пояснение|Важно)\s*:)', re.I)


def split_rule_punishment(text, existing=''):
    """Extract sanctions by line, keeping following notes and unrelated pipes."""
    body, sanctions = [], []
    for line in text.splitlines():
        split = re.search(r'\||\bНаказание\s*:', line, re.I)
        if not split:
            body.append(line)
            continue
        prefix, suffix = line[:split.start()].rstrip(), line[split.end():].strip()
        if not SANCTION.search(suffix):
            body.append(line)
            continue
        parts = INLINE_NOTE.split(suffix, maxsplit=1)
        sanction = parts[0]
        if prefix:
            body.append(prefix)
        if len(parts) > 1:
            body.append(parts[1])
        sanctions.append((prefix, sanction))
    # Preserve each condition when one rule specifies several different sanctions.
    extracted = '\n\n'.join((f'{prefix}\n{sanction}' if len(sanctions) > 1 and prefix else sanction)
                              for prefix, sanction in sanctions)
    if existing and extracted != existing:
        extracted = '\n\n'.join(filter(None, (existing, extracted)))
    return '\n'.join(body), extracted


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
                description, punishment = split_rule_punishment(rule['description'], rule.get('punishment', ''))
                result.append({
                    **rule, "server_id": server_id, "kind": "rule", "code": "Правило",
                    "category": document.get("category", document["title"]),
                    "chapter": document.get("topic_title", document["title"]),
                    "topic_id": document.get("topic_id", document["title"]),
                    "title": rule.get("title", document.get("topic_title", document["title"])),
                    "description": description,
                    "source_text": rule['description'],
                    "punishment": punishment,
                    "keywords": rule.get("keywords", ""),
                    "source_url": document.get("source_url", ""),
                    "checked_at": document.get("checked_at", ""),
                })
        return result
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
