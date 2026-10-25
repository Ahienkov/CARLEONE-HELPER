"""Local spreadsheet supplements; forum sanctions remain untouched."""
import json
from pathlib import Path

from i18n import tr


SOURCE_PATH = Path(__file__).with_name('penalties_source.json')
DESTINATIONS = {'🟩': 'КПЗ', '🟨': 'СИЗО', '🟥': 'ФТ'}


def load_penalties():
    if not SOURCE_PATH.exists():
        return {}, ''
    source = json.loads(SOURCE_PATH.read_text(encoding='utf-8'))
    index = {(source['server'], row['code'], row['number']): row for row in source['articles']}
    return index, source['source_url']


PENALTIES, SOURCE_URL = load_penalties()


def penalty_supplement(article, server):
    """Match server, code, exact number and the reviewed forum title/type."""
    if article.get('kind') == 'rule':
        return ''
    code = article.get('code', 'УАК')
    row = PENALTIES.get((server, code, article['number']))
    if not row or not row['minutes'] or row['forum_title'] != article['title']:
        return ''
    if code == 'УАК' and row['marker'] != article.get('marker'):
        return ''
    return tr('({minutes} мин, {destination})', minutes=row['minutes'], destination=row['destination'])


def punishment_text(article, server):
    original = article['punishment']
    supplement = penalty_supplement(article, server)
    return f'{original}\n{supplement}' if supplement else original
