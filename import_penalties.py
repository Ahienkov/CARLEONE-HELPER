"""Explicitly import the reviewed Murrieta sheet into a bundled offline snapshot."""
import csv
import io
import json
import re
import urllib.request
from datetime import datetime, timezone

from codex_data import load_articles
from road_data import load_road_articles
from penalty_data import DESTINATIONS, SOURCE_PATH


SOURCE_URL = 'https://docs.google.com/spreadsheets/d/14u26aSKsD22zjRe-bWIzDJ0hELDo8HXy1HVimfjdEzU/edit?gid=0'
CSV_URL = SOURCE_URL.split('/edit')[0] + '/export?format=csv&gid=0'


def parse_sheet(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or not any('[MURRIETA]' in cell for cell in rows[0]):
        raise ValueError('Expected the Murrieta sheet.')
    if len(rows) < 7 or rows[6][0] != 'Статья [У]' or rows[6][8] != 'Время ФТ' or rows[6][17] != 'Время КПЗ':
        raise ValueError('Unexpected spreadsheet columns.')
    catalogs = {'УАК': {a['number']: a for a in load_articles()},
                'ДК': {a['number']: a for a in load_road_articles()}}
    entries, seen = [], set()
    for position, row in enumerate(rows, 1):
        for column, title_column, time_column in ((0, 1, 8), (9, 10, 17)):
            if len(row) <= time_column:
                continue
            label = row[column].strip()
            law = re.fullmatch(r'([🟩🟨🟥])(\d+(?:\.\d+)+)[*РФДНВ/\s]*', label)
            road = re.fullmatch(r'Ст\.\s*(\d+(?:\.\d+)*)', label)
            if not law and not road:
                continue
            code, number = ('УАК', law[2]) if law else ('ДК', road[1])
            key = code, number
            if key in seen:
                raise ValueError(f'Duplicate article: {key}')
            seen.add(key)
            article = catalogs[code].get(number)
            if article is None:
                raise ValueError(f'Article missing from local forum snapshot: {key}')
            marker = law[1] if law else ''
            if law and article.get('marker') != marker:
                raise ValueError(f'Punishment type differs from forum: {key}')
            duration = row[time_column].strip()
            minutes = ''
            if duration not in ('', '-', '—', '–'):
                match = re.fullmatch(r'(\d+)(?:\s*[-–—]\s*(\d+))?\s*мин\.?', duration)
                if not match or (match[2] and int(match[2]) < int(match[1])):
                    raise ValueError(f'Invalid duration at row {position}: {duration}')
                minutes = match[1] + ('–' + match[2] if match[2] else '')
            entries.append({'code': code, 'number': number, 'marker': marker,
                            'minutes': minutes, 'destination': DESTINATIONS.get(marker, 'КПЗ'),
                            'sheet_title': row[title_column].strip(), 'forum_title': article['title'],
                            'sheet_row': position})
    return entries


if __name__ == '__main__':
    with urllib.request.urlopen(CSV_URL, timeout=30) as response:
        text = response.read().decode('utf-8-sig')
    entries = parse_sheet(text)
    snapshot = {'server': 'murrieta', 'source_url': SOURCE_URL,
                'imported_at': datetime.now(timezone.utc).isoformat(),
                'legend': DESTINATIONS, 'articles': entries}
    SOURCE_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Imported {len(entries)} articles; {sum(bool(row["minutes"]) for row in entries)} with detention times.')
