"""Download the Murrieta procedural code snapshot."""
from pathlib import Path

import requests
import load_codex
from procedure_data import parse_procedure


load_codex.URL = (
    "https://forum.gta5rp.com/threads/"
    "protsessual-nyi-kodeks-shtata-san-andreas.3237253/"
)
load_codex.SAVE_PATH = Path(__file__).with_name("procedure_source.json")


if __name__ == "__main__":
    try:
        load_codex.download_codex(required_fragment="Статья 1", validator=parse_procedure)
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Не удалось загрузить процессуальный кодекс: {error}")
        raise SystemExit(1)
