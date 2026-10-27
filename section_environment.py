"""Independent section state; only the active section keeps a parsed database."""
from dataclasses import asdict, dataclass, field


def load_section(server_id, mode):
    if mode in ('earnings', 'notepad'):
        return []
    if server_id != 'murrieta':
        return []
    if mode == 'rules':
        from rules_data import load_rules
        return load_rules(server_id)
    from codex_data import load_articles
    from road_data import load_road_articles
    from procedure_data import load_procedure_articles
    from labor_data import load_labor_articles
    from extra_laws_data import load_extra_laws
    return (load_articles() + load_road_articles() + load_procedure_articles()
            + load_labor_articles() + load_extra_laws())


@dataclass
class SectionState:
    server: str = 'murrieta'
    query: str = ''
    category: str = 'Все'
    topic: str = ''
    rendered: int = 30
    scroll: int = 0
    extras: dict = field(default_factory=dict)


class SectionEnvironment:
    def __init__(self, mode, state=None):
        self.mode = mode
        self.state = SectionState(**(state or {}))
        self.unload()

    def unload(self):
        self.server = None
        self.records = None
        self.index = None
        self.law_search = None

    def load(self, server, catalog, searchable_text):
        if self.server == server and self.records is not None:
            return
        records = catalog.get(self.mode)
        if records is None:
            records = load_section(server, self.mode)
        self.set_records(server, records, searchable_text)

    def set_records(self, server, records, searchable_text):
        # Build first so a parse/index error doesn't leave a half-loaded section.
        index = [(article, searchable_text(article)) for article in records]
        from law_search import LawSearchIndex
        law_search = LawSearchIndex(index) if self.mode == 'laws' else None
        self.server, self.records, self.index = server, records, index
        self.law_search = law_search

    def export_state(self):
        return asdict(self.state)
