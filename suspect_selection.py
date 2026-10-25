"""Per-server article selections, separate from the forum database."""
import json

from PySide6.QtCore import QSettings


def article_key(article):
    if article.get('kind') == 'rule':
        # Rule numbers repeat across topics, and sometimes within a topic.
        topic = article.get('topic_id', article.get('source_url', article['title']))
        identity = article['number'] + '|' + str(article.get('rule_id', article['number']))
        return 'Правило:' + str(topic), identity
    return article.get('code', 'УАК'), article['number']


class SuspectStore:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings('CARLEONE', 'HELPER')

    def load(self):
        try:
            value = json.loads(self.settings.value('suspect_articles', '{}', type=str))
            if not isinstance(value, dict):
                return {}
            return {server: {tuple(key) for key in keys
                             if isinstance(key, list) and len(key) == 2
                             and all(isinstance(part, str) for part in key)}
                    for server, keys in value.items() if isinstance(keys, list)}
        except (TypeError, ValueError):
            return {}

    def save(self, selections):
        value = {server: sorted(keys) for server, keys in selections.items()}
        self.settings.setValue('suspect_articles', json.dumps(value, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError('Не удалось сохранить список нарушений.')
