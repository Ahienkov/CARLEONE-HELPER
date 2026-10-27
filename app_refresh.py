"""Reload local application sources in the same process, keeping the current view."""
import importlib
import runpy
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from i18n import tr


DATA_MODULES = (
    "road_data", "codex_data", "procedure_data", "labor_data", "rules_data", "extra_laws_data",
    "i18n", "penalty_data", "suspect_selection", "dark_combo", "hotkey_config", "app_settings", "window_hotkey", "law_search", "section_environment", "earnings", "reselling", "notepad",
)


def reload_application(window):
    window.refresh_button.setEnabled(False)
    replacement = None
    try:
        state = {
            "server": window.server.currentData(), "mode": window.mode,
            "category": window.category, "topic": window.topic.currentData(),
            "query": window.search.text(), "expanded": window.law_categories_expanded,
            "rules_expanded": getattr(window, "rules_categories_expanded", False),
            "geometry": window.saveGeometry(), "maximized": window.isMaximized(),
            "suspect_filter": getattr(window, 'suspect_button', None) is not None and window.suspect_button.isChecked(),
            "suspect_filters": dict(getattr(window, 'suspect_filter_modes', {'laws': False, 'rules': False})),
            "sections": window.export_section_states() if hasattr(window, 'export_section_states') else None,
        }
        importlib.invalidate_caches()
        for name in DATA_MODULES:
            importlib.reload(importlib.import_module(name))
        # A fresh namespace avoids replacing functions used by the existing window
        # until the new version has loaded and constructed successfully.
        namespace = runpy.run_path(str(Path(__file__).with_name("main.py")), run_name="carleone_live")
        selection_settings = window.suspect_store.settings if hasattr(window, 'suspect_store') else None
        sections = state['sections'] or {state['mode']: {
            'server': state['server'], 'query': state['query'],
            'category': state['category'], 'topic': state['topic'] or '',
        }}
        replacement = namespace["CarleoneWindow"](selection_settings=selection_settings,
                                                 initial_mode=state['mode'], section_states=sections,
                                                 earnings_settings=getattr(window, 'earnings_settings', None),
                                                 notepad_settings=getattr(window, 'notepad_settings', None))
        replacement.restoreGeometry(state["geometry"])
        replacement.suspect_filter_modes = state['suspect_filters']
        replacement.suspect_button.setChecked(state['suspect_filter'])
        replacement.law_categories_expanded = state["expanded"]
        replacement.rules_categories_expanded = state["rules_expanded"]
        replacement.expand_categories_button.blockSignals(True)
        replacement.expand_categories_button.setChecked(state["expanded"])
        replacement.expand_categories_button.blockSignals(False)
        replacement.restore_section_state()
        replacement.status.setText(replacement.status.text() + " · " + tr("Обновлено"))
        if state["maximized"]:
            replacement.showMaximized()
        else:
            replacement.show()
        QApplication.instance().main_window = replacement
        window.search_timer.stop()
        window.load_timer.stop()
        window.close()
        window.deleteLater()
        return replacement
    except Exception as error:
        if replacement is not None:
            replacement.close()
            replacement.deleteLater()
        window.refresh_button.setEnabled(True)
        QMessageBox.warning(window, tr("Не удалось обновить"), tr('Не удалось применить изменения:\n{error}', error=error))
        return None
