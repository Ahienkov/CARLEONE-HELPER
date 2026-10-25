"""Download and validate the Murrieta labor code before replacing the snapshot."""
from pathlib import Path

import requests
import load_codex
from labor_data import parse_labor


if __name__ == "__main__":
    load_codex.URL = (
        "https://forum.gta5rp.com/threads/"
        "trudovoi-kodeks-shtata-san-andreas.3237240/"
    )
    load_codex.SAVE_PATH = Path(__file__).with_name("labor_source.json")
    try:
        load_codex.download_codex(required_fragment="Статья 1", validator=parse_labor)
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Не удалось загрузить трудовой кодекс: {error}")
        raise SystemExit(1)
