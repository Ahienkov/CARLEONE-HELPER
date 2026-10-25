"""Read the Murrieta forum snapshot beside this module. No network on import."""
import json
import re
from pathlib import Path


START = re.compile(r"^\s*([🟩🟨🟥]?)\s*(\d+(?:\.\d+)+)\.?\s*(.*)$")
COMMENT = re.compile(r"^\d+\.\s*Комментарий к стать[еям]+\s+(.+)", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)+")
TYPE = re.compile(r"^\[([АAУ])\]\s*(\**)", re.I)
SANCTION = re.compile(
    r"\s+[-–—⁃]\s*(?=(?:от\s+\d|до\s+\d|\d+\s+(?:год|лет|сут)|"
    r"штраф|возмещение|компенсация|принудительное взыскание))"
    r"|(?<=\.)\s+(?=Штраф\s+в\s+размере)", re.I
)
NOTES = re.compile(r"\n(?=(?:Примечание|Исключение)\b)", re.I)
ALIASES = {
    "6.1": "ударил избил драка побои два удара",
    "6.1.1": "ударил избил драка побои три удара",
    "6.2": "нок нокнул нокнутый избил драка",
    "10.1": "украл украли кража имущество",
    "10.5": "угнал угон машину автомобиль",
}


def parse_codex(text):
    """Keep complete article text and attach both inline and end comments."""
    records = []
    comments = []
    current = None
    comment = None
    chapter = ""
    section = ""
    legend = []
    in_legend = False
    in_comments = False

    for line in text.replace("\u200b", "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Комментарий законодателя"):
            current = None
            comment = None
            in_comments = True
            continue
        match = COMMENT.match(line)
        if match:
            comment = {"numbers": NUMBER.findall(match[1]), "lines": [line]}
            comments.append(comment)
            current = None
            continue
        if line.startswith(("Глава ", "Раздел ")):
            current = None
            comment = None
            in_legend = False
            if line.startswith("Глава "):
                chapter = line
            else:
                section = line
            continue
        if line in ("Общая часть", "Особенная часть"):
            current = None
            in_legend = line == "Особенная часть"
            continue
        if in_comments:
            if comment is not None:
                comment["lines"].append(line)
            continue

        match = START.match(line)
        if match:
            marker, number, body = match.groups()
            current = {
                "number": number, "marker": marker, "body_lines": [body],
                "source_lines": [line], "chapter": chapter, "section": section,
            }
            records.append(current)
            comment = None
            in_legend = False
        elif comment is not None:
            comment["lines"].append(line)
        elif current is not None:
            current["body_lines"].append(line)
            current["source_lines"].append(line)
        elif in_legend:
            legend.append(line)

    ids = [r["number"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("В исходнике повторяются номера статей; требуется проверка.")
    if not records:
        raise ValueError("В файле не найдено статей.")

    attached = {}
    for item in comments:
        for number in item["numbers"]:
            if number not in ids:
                raise ValueError(f"Комментарий ссылается на отсутствующую статью {number}.")
            attached.setdefault(number, []).append("\n".join(item["lines"]))

    articles = []
    for record in records:
        number = record["number"]
        body = "\n".join(record["body_lines"])
        type_match = TYPE.match(body)
        category = "Общая часть"
        metadata = []
        if type_match:
            kind, stars = type_match.groups()
            category = "Уголовный" if kind.upper() == "У" else "Административный"
            metadata.append(f"[{kind}] {stars}".strip())
            body = body[type_match.end():].lstrip()
            jurisdiction = re.match(r"^\(([^)]+)\)\s*(\**)", body)
            if jurisdiction:
                metadata.append(jurisdiction[0].strip())
                body = body[jurisdiction.end():].lstrip()
        elif int(number.split('.')[0]) >= 6:
            raise ValueError(f"Не распознан вид статьи {number}; исходник сохранён.")

        body = body.lstrip("-–— ")
        heading = re.split(r",\s*то есть|\s*\(\(|\n|\.\s", body, maxsplit=1)[0]
        title = heading if len(heading) <= 110 else heading[:107].rsplit(" ", 1)[0] + "…"
        title = title or record["chapter"]

        if category == "Общая часть":
            description = body
            punishment = "Общая норма — отдельная санкция не выделяется."
        elif len(re.findall(r"(?:^|\n)ч\.\s*\d+", body)) > 1:
            # Keep every condition next to its own sanction for multipart rules.
            description = body
            punishment = "Наказания по частям указаны в полном тексте статьи выше."
        else:
            split = SANCTION.search(body)
            if split:
                description = body[:split.start()].rstrip()
                punishment = body[split.end():].strip()
                note = NOTES.search(punishment)
                if note:
                    description += "\n\n" + punishment[note.end():]
                    punishment = punishment[:note.start()].rstrip()
            else:
                description = body
                punishment = "Санкция не выделена автоматически. См. полный текст выше."

        if metadata:
            description = " ".join(metadata) + "\n\n" + description
        if attached.get(number):
            description += "\n\n" + "\n\n".join(attached[number])

        articles.append({
            "number": number, "category": category, "title": title,
            "description": description, "punishment": punishment,
            "keywords": ALIASES.get(number, ""),
            "source_text": "\n".join(record["source_lines"]),
            "comments": attached.get(number, []),
            "marker": record["marker"], "chapter": record["chapter"],
            "section": record["section"],
        })
    if legend:
        articles.append({
            "number": "Справка", "category": "Общая часть",
            "title": "Обозначения кодекса и перевод игрового времени",
            "description": "\n".join(legend),
            "punishment": "Справочная информация из кодекса.",
            "keywords": "обозначения время минуты годы сутки",
            "source_text": "\n".join(legend), "comments": [],
        })
    return articles


def load_articles(source_path=None):
    path = Path(source_path) if source_path else Path(__file__).with_name("codex_source.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            raise ValueError("Ожидается объект JSON с полем text.")
        articles = parse_codex(data["text"])
        for article in articles:
            article["source_url"] = data.get("source_url", "")
            article["checked_at"] = data.get("checked_at", "")
        return articles
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc


if __name__ == "__main__":
    from collections import Counter
    try:
        articles = load_articles()
        print(f"Готово. Записей: {len(articles)}")
        for category, count in Counter(a["category"] for a in articles).items():
            print(f"{category}: {count}")
        print("Исходный файл не изменён. Данные готовы для приложения.")
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1)
