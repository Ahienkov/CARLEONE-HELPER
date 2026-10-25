from pathlib import Path

import requests
import load_codex


load_codex.URL = (
    "https://forum.gta5rp.com/threads/"
    "dorozhnyi-kodeks-shtata-san-andreas.3237239/"
)

load_codex.SAVE_PATH = (
    Path(__file__).resolve().parent / "road_source.json"
)


if __name__ == "__main__":
    try:
        load_codex.download_codex()
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Не удалось загрузить дорожный кодекс: {error}")