"""Build searchable rule cards from the saved official forum topics."""
import json
import re
from pathlib import Path

from rules_data import load_rules


RULE_START = re.compile(r"^(\d+(?:\.\d+)+|\d+\.)(?:\.)?\s+(.*)$")
ROOT = Path(__file__).with_name("rules")


def parse_rules(text):
    rules = []
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = RULE_START.match(line)
        if match:
            current = {"number": match[1].rstrip("."), "description": line}
            rules.append(current)
        elif current is None:
            current = {"number": "Справка", "description": line}
            rules.append(current)
        else:
            current["description"] += "\n" + line
    for index, rule in enumerate(rules):
        rule["rule_id"] = str(index)
    return rules


def compile_rules(source):
    if source.get("server_id") != "murrieta":
        raise ValueError("Wrong server snapshot")
    documents = []
    server_topic_urls = set(source["server_topic_urls"])
    for item in source["documents"]:
        document = {key: item[key] for key in ("title", "category", "source_url", "checked_at")}
        scope = "Murrieta" if item["source_url"] in server_topic_urls else "Правила проекта"
        document["topic_id"] = item["source_url"].rstrip("/").rsplit(".", 1)[-1]
        document["topic_title"] = f"{item['title']} · {scope}"
        if "PVP" in item["title"]:
            document["category"] = "Криминальные организации"
        text = item["text"]
        rules = parse_rules(text)
        for extra in item.get("additional_posts", []):
            if extra.startswith("Приложение"):
                text += "\n" + extra
                rules.append({"number": "Справка: " + extra.splitlines()[0],
                              "description": extra, "rule_id": f"appendix-{len(rules)}"})
        document["text"] = text
        document["rules"] = rules
        if not document["rules"]:
            raise ValueError(f"Empty topic: {item['title']}")
        documents.append(document)
    return {"server_id": "murrieta", "documents": documents}


def build():
    source = json.loads((ROOT / "murrieta_sources.json").read_text(encoding="utf-8"))
    data = compile_rules(source)
    temporary = ROOT / "murrieta.tmp.json"
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        cards = load_rules("murrieta", temporary)
        temporary.replace(ROOT / "murrieta.json")
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Built {len(cards)} cards from {len(data['documents'])} topics.")


if __name__ == "__main__":
    build()
