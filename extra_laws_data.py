"""Additional Murrieta laws, stored separately from the code snapshots."""
import json
from pathlib import Path

from procedure_data import parse_procedure


EXTRA_LAWS = (
    {"category": "Охота и рыбалка", "code": "Охота", "url": "https://forum.gta5rp.com/threads/zakon-o-lyubitel-skom-i-professional-nom-rybolovstve-i-okhote.3237180/"},
    {"category": "Оборот оружия", "code": "Оружие", "url": "https://forum.gta5rp.com/threads/zakon-o-regulirovanii-oborota-oruzhiya-boyepripasov-i-spetssredstv-v-shtate-san-andreas.3237222/"},
    {"category": "Адвок. Деятельность", "code": "Адвокатура", "url": "https://forum.gta5rp.com/threads/zakon-ob-advokat-skoi-deyatel-nosti-i-advokature-v-shtate-san-andreas.3237238/"},
)
SOURCE_PATH = Path(__file__).with_name("extra_laws_source.json")


def parse_extra_law(document):
    records = parse_procedure(document["text"], category=document["category"], code=document["code"])
    for article in records:
        article["source_url"] = document["source_url"]
        article["checked_at"] = document["checked_at"]
        article["keywords"] = document["category"]
        article["server_id"] = "murrieta"
    return records


def load_extra_laws(source_path=None):
    path = Path(source_path) if source_path else SOURCE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("server_id") != "murrieta":
            raise ValueError("Исходник законов принадлежит другому серверу.")
        return [article for document in data["documents"] for article in parse_extra_law(document)]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Не удалось прочитать {path.name}: {exc}") from exc
