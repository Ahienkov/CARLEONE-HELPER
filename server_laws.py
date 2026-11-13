"""Read a single server's laws lazily, without network access or cross-server fallback."""
import json
import re
from collections import Counter
from pathlib import Path

ARTICLE = re.compile(r'^\s*[🟩🟨🟥]?\s*Статья\s+(\d+(?:\.\d+)*)(?:\.(?!\d))?\s*(.*)$', re.I)
BARE = re.compile(r'^\s*[🟩🟨🟥]?\s*(\d+\.\d+(?:\.\d+)*)(?:\.(?!\d))?\s*(.*)$')
HEADING = re.compile(r'^(?:Глава\s+([IVXLCDM\d]+)|§\s*([IVXLCDM\d]+)|Раздел\s+[IVXLCDM\d]+)\b', re.I)
SANCTION = re.compile(r'наказыва|лишени[еяю]\s+свободы|(?:^|[-–—⁃]\s*)штраф\s+(?:от|до|в размере)|^[-–—⁃]\s*(?:от|до)\s*\d', re.I)


def law_category(title):
    title = title.casefold()
    if any(word in title for word in ('изменени', 'реестр изменений')):
        return 'История изменений', 'История'
    for word, group, code in (
        ('уголовно', 'Уголовный', 'УАК'), ('уголовный', 'Уголовный', 'УК'),
        ('административн', 'Административный', 'АК'), ('процессуальн', 'Процессуальный', 'ПК'),
        ('дорожн', 'Дорожный', 'ДК'), ('трудов', 'Трудовой', 'ТК'),
        ('этическ', 'Этический', 'ЭК'), ('гражданск', 'Гражданский', 'ГК'),
        ('воздушн', 'Воздушный', 'ВК'), ('избирательн', 'Избирательный', 'ИК'),
        ('конституция', 'Конституция', 'КС'), ('оруж', 'Оборот оружия', 'Оружие'),
        ('адвокат', 'Адвок. Деятельность', 'Адвокатура'),
    ):
        if word in title:
            return group, code
    if any(word in title for word in ('рыбол', 'охот', 'биологическ', 'природн', 'животн')):
        return 'Охота и рыбалка', 'Природа'
    if any(word in title for word in ('судебн', 'юстиц', 'прокур', 'ордер', 'правовых акт')):
        return 'Правосудие', 'Закон'
    if any(word in title for word in ('government', 'правительств', 'федеральн', 'federal', 'полицейск', 'police', 'sheriff', 'secret service', 'секретной служб', 'пенитенциар', 'prison', 'тюрем', 'national guard', 'гварди', 'medical', 'медицинск', 'здравоохр', 'weazel', 'средствах массовой', 'средства массовой', 'средств массовой', 'сенат', 'конгресс')):
        return 'Госорганизации', 'Закон'
    return 'Прочие законы', 'Закон'


def parse_law(document, server_id):
    text = document['text']
    group, code = law_category(document['title'])
    if group == 'История изменений':
        # Historical amendments contain superseded articles. Never index them as
        # independent current articles or split the "Было / Стало" pairs.
        return [_record(document, server_id, 'Справка', text, '', '', group, code, 'history')]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    use_bare = code == 'УАК' or not any(ARTICLE.match(line) for line in lines)
    records, current = [], None
    chapter = chapter_number = ''
    section = ''
    in_comments = False
    occurrences = Counter()
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            if line.casefold().startswith('раздел'):
                section = line
            else:
                chapter, chapter_number = line, heading[1] or heading[2] or ''
            current = None
            in_comments = 'комментар' in line.casefold()
        if re.match(r'^Комментарий законодателя|^Комментарии к|^Комментарий\s+[IVXLCDM]+\.', line, re.I):
            current = None
            in_comments = True
        match = None if in_comments else (ARTICLE.match(line) or (BARE.match(line) if use_bare else None))
        if match:
            number, _body = match.groups()
            occurrences[(chapter, number)] += 1
            category = group
            if code == 'УАК':
                if re.search(r'\[[АA]\]', line) or 'административн' in section.casefold():
                    category = 'Административный'
                elif re.search(r'\[У\]', line):
                    category = 'Уголовный'
                elif 'особенн' not in section.casefold() and int(number.split('.')[0]) < 6:
                    category = 'Общая часть'
            identity = f'{chapter}|{number}|{occurrences[(chapter, number)]}'
            current = _record(document, server_id, number, line, chapter, chapter_number, category, code, identity)
            records.append(current)
        elif current is None:
            identity = f'reference-{len(records)}'
            current = _record(document, server_id, 'Справка', line, chapter, chapter_number, group, code, identity)
            records.append(current)
        else:
            current['description'] += '\n' + line
            current['source_text'] += '\n' + line
    for record in records:
        if record['number'] != 'Справка':
            body = ARTICLE.sub(lambda m: m[2], record['description'], count=1)
            if body == record['description'] and use_bare:
                body = BARE.sub(lambda m: m[2], body, count=1)
            title = next((line for line in body.splitlines() if line.strip()), f"Статья {record['number']}")
            record['title'] = title[:160]
            record['short_title'] = f"{document['title']} · {title}"
            record['punishment'] = '\n'.join(line for line in body.splitlines() if SANCTION.search(line))
    if '\n'.join(r['source_text'] for r in records) != '\n'.join(lines):
        raise ValueError('Parser lost law text')
    return records


def _record(document, server_id, number, text, chapter, chapter_number, category, code, identity):
    return dict(server_id=server_id, document_id=document['document_id'], record_id=identity,
                topic_id=document['document_id'], topic_title=document['title'],
                number=number, title=document['title'], category=category, code=code,
                description=text, source_text=text, punishment='', keywords=document['title'],
                chapter=chapter, chapter_number=chapter_number, comments=[],
                source_url=document['source_url'], checked_at=document['checked_at'])


def load_server_laws(server_id, source_path=None):
    from server_registry import SERVER_NAMES
    if server_id not in SERVER_NAMES:
        return []
    path = Path(source_path) if source_path else Path(__file__).with_name('laws') / f'{server_id}_sources.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('server_id') != server_id:
        raise ValueError('Исходник законов принадлежит другому серверу.')
    records = []
    seen = set()
    for document in data['documents']:
        if not document['text'].strip() or document['document_id'] in seen:
            raise ValueError('Пустой или повторный закон.')
        seen.add(document['document_id'])
        records.extend(parse_law(document, server_id))
    return records
