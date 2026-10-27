"""Local word similarity for laws; numbers and short abbreviations stay literal."""
import re


WORDS = re.compile(r'[^\W\d_]+|\d+(?:\.\d+)*', re.UNICODE)
# Conservative inflection removal, not semantic matching or a legal interpretation.
ENDINGS = tuple(sorted((
    'иями', 'ями', 'ами', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими',
    'иях', 'ах', 'ях', 'иям', 'ям', 'ам', 'ием', 'ией', 'ия', 'ие', 'ии',
    'ий', 'ый', 'ой', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие', 'ую', 'юю',
    'ов', 'ев', 'ей', 'ом', 'ем', 'ым', 'им', 'ых', 'их', 'ы', 'и', 'а', 'я', 'у', 'ю', 'е', 'о',
), key=len, reverse=True))

# Retrieval hints only. Keep distinct offences (theft, robbery, vehicle theft)
# in separate groups rather than treating them as equivalent legal concepts.
SYNONYMS = (
    ('кража', ('украл', 'украли', 'украсть', 'воровство', 'стащил', 'стащили', 'своровал', 'своровали')),
    (('ограбление', 'грабеж'), ('ограбил', 'ограбили', 'ограбить', 'грабитель')),
    ('угон', ('угнал', 'угнали', 'угнать', 'угонщик')),
    ('оружие', ('ствол', 'пушка', 'огнестрел', 'пистолет')),
    ('боеприпасы', ('патроны', 'патрон', 'боезапас')),
    (('наркотики', 'наркотический'), ('наркота', 'наркотик', 'наркосредства')),
    ('автомобиль', ('машина', 'тачка', 'авто', 'автомашина')),
    ('мотоцикл', ('мотик', 'байк')),
    (('полиция', 'полицейский'), ('коп', 'копы', 'полицейские')),
    ('побои', ('избил', 'избили', 'избиение', 'побил', 'побили', 'побить')),
    ('убийство', ('убил', 'убили', 'убить')),
    ('похищение', ('похитил', 'похитили', 'похитить', 'киднеппинг')),
    ('мошенничество', ('мошенник', 'мошенники', 'скам', 'скамер', 'скаммер')),
    ('вымогательство', ('вымогал', 'вымогали', 'вымогать', 'рэкет', 'рэкетир')),
    ('взятка', ('взяткодатель', 'взяточник', 'взяточничество')),
    ('подделка', ('подделал', 'подделали', 'поддельный', 'фальшивый', 'фальшивка')),
    ('оскорбление', ('оскорбил', 'оскорбили', 'оскорбить', 'обозвал')),
    ('неповиновение', ('неподчинение', 'ослушался', 'ослушались')),
    ('проникновение', ('проник', 'проникли', 'вторжение')),
)


def normalize(text):
    return text.casefold().replace('ё', 'е')


def stem(word):
    if not re.fullmatch('[а-я]+', word):
        return word
    for ending in ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[:-len(ending)]
    return word


SYNONYM_LOOKUP = {}
for _targets, _aliases in SYNONYMS:
    _targets = (_targets,) if isinstance(_targets, str) else _targets
    for _alias in (*_targets, *_aliases):
        SYNONYM_LOOKUP.setdefault(stem(normalize(_alias)), set()).update(map(normalize, _targets))


def within_edits(left, right, limit):
    """Bounded Damerau-Levenshtein (adjacent transposition costs one edit)."""
    if abs(len(left) - len(right)) > limit:
        return False
    previous = list(range(len(right) + 1))
    before_previous = None
    for i, char in enumerate(left, 1):
        current = [i] + [limit + 1] * len(right)
        for j in range(max(1, i - limit), min(len(right), i + limit) + 1):
            current[j] = min(current[j - 1] + 1, previous[j] + 1,
                             previous[j - 1] + (char != right[j - 1]))
            if (i > 1 and j > 1 and char == right[j - 2]
                    and left[i - 2] == right[j - 1]):
                current[j] = min(current[j], before_previous[j - 2] + 1)
        if min(current) > limit:
            return False
        before_previous, previous = previous, current
    return previous[-1] <= limit


class LawSearchIndex:
    def __init__(self, index):
        self.documents = [(id(article), text) for article, text in index]
        self.words = {}
        for article_id, text in self.documents:
            for word in set(WORDS.findall(text)):
                if word.isalpha() and len(word) >= 4:
                    self.words.setdefault(word, set()).add(article_id)
        self.stems = {word: stem(word) for word in self.words}

    def word_costs(self, term):
        exact = {article_id for article_id, text in self.documents if term in text}
        costs = dict.fromkeys(exact, 0)
        if term.isalpha() and len(term) >= 4:
            root = stem(term)
            limit = 2 if len(term) >= 8 else 1
            for word, ids in self.words.items():
                if ids <= exact:
                    continue
                if root == self.stems[word]:
                    cost = 1
                elif within_edits(term, word, limit):
                    cost = 2
                else:
                    continue
                for article_id in ids:
                    costs[article_id] = min(costs.get(article_id, cost), cost)
        return costs

    def scores(self, query):
        """All query words must match; exact matches precede retrieval hints."""
        terms = set(WORDS.findall(normalize(query)))
        scores = {article_id: 0 for article_id, _ in self.documents}
        for term in sorted(terms):
            costs = self.word_costs(term)
            for alternative in SYNONYM_LOOKUP.get(stem(term), ()):
                if alternative == term:
                    continue
                for article_id, cost in self.word_costs(alternative).items():
                    costs[article_id] = min(costs.get(article_id, cost + 3), cost + 3)
            scores = {article_id: score + costs[article_id]
                      for article_id, score in scores.items() if article_id in costs}
            if not scores:
                break
        return scores
