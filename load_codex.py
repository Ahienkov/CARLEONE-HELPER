import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = (
    "https://forum.gta5rp.com/threads/"
    "ugolovno-administrativnyi-kodeks-shtata-san-andreas.3237254/"
)

SAVE_PATH = Path(__file__).resolve().parent / "codex_source.json"


def download_codex(required_fragment="6.1", validator=None):
    print("Загружаю кодекс с форума...")

    response = requests.get(
        URL,
        timeout=(10, 40),
        headers={"User-Agent": "CarleoneHelper/0.1"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    full_text = extract_codex_text(soup)

    if (
        len(full_text) < 5000
        or required_fragment not in full_text
        or "кодекс" not in full_text.casefold()
    ):
        raise ValueError("Полученная страница не похожа на полный кодекс. Предыдущий сохранённый файл оставлен.")
    if validator is not None:
        validator(full_text)
    data = {"source_url": URL, "checked_at": datetime.now(timezone.utc).isoformat(), "text": full_text}
    temporary_path = SAVE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(SAVE_PATH)
    print(f"Готово! Текст кодекса сохранён. Символов: {len(full_text)} · Файл: {SAVE_PATH.name}")


def extract_codex_text(soup):
    posts = soup.select(".message-body .bbWrapper")

    if not posts:
        raise ValueError(
            "Текст сообщений не найден. "
            "Возможно, форум временно ограничил доступ."
        )

    texts = []

    for post in posts:
        # Сохраняем обозначения, представленные картинками.
        for image in post.find_all("img"):
            image.replace_with(image.get("alt", ""))

        # Разделяем строки, сохраняя текст внутри выделений.
        for br in post.find_all("br"):
            br.replace_with("\n")

        for block in post.find_all(
            ["div", "p", "li", "tr", "h1", "h2", "h3"]
        ):
            block.insert_before("\n")
            block.insert_after("\n")

        text = post.get_text()
        text = text.replace("\u200b", "").replace("\xa0", " ")

        lines = [
            " ".join(line.split())
            for line in text.splitlines()
            if line.strip()
        ]
        texts.append("\n".join(lines))

    return "\n\n".join(texts)


if __name__ == "__main__":
    try:
        download_codex()
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Не удалось загрузить кодекс: {error}")
