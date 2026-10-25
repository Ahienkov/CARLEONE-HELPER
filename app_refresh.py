"""Reload local application sources in the same process, keeping the current view."""
import importlib
import runpy
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox


DATA_MODULES = (
    "road_data", "codex_data", "procedure_data", "labor_data", "rules_data", "extra_laws_data",
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
        }
        importlib.invalidate_caches()
        for name in DATA_MODULES:
            importlib.reload(importlib.import_module(name))
        # A fresh namespace avoids replacing functions used by the existing window
        # until the new version has loaded and constructed successfully.
        namespace = runpy.run_path(str(Path(__file__).with_name("main.py")), run_name="carleone_live")
        replacement = namespace["CarleoneWindow"]()
        replacement.restoreGeometry(state["geometry"])
        index = replacement.server.findData(state["server"])
        if index >= 0:
            replacement.server.blockSignals(True)
            replacement.server.setCurrentIndex(index)
            replacement.server.blockSignals(False)
        replacement.mode = state["mode"]
        replacement.mode_group.button(1 if state["mode"] == "rules" else 0).setChecked(True)
        replacement.search.setPlaceholderText("Поиск по правилам" if state["mode"] == "rules" else "Поиск по законам")
        replacement.law_categories_expanded = state["expanded"]
        replacement.rules_categories_expanded = state["rules_expanded"]
        replacement.expand_categories_button.blockSignals(True)
        replacement.expand_categories_button.setChecked(state["expanded"])
        replacement.expand_categories_button.blockSignals(False)
        replacement.rebuild_categories()
        for button in replacement.category_group.buttons():
            if (button.property("category") or button.text()) == state["category"]:
                button.setChecked(True)
                replacement.category = state["category"]
                break
        replacement.rebuild_topics()
        index = replacement.topic.findData(state["topic"])
        if index >= 0:
            replacement.topic.blockSignals(True)
            replacement.topic.setCurrentIndex(index)
            replacement.topic.blockSignals(False)
        replacement.search.blockSignals(True)
        replacement.search.setText(state["query"])
        replacement.search.blockSignals(False)
        replacement.refresh_category_visibility()
        replacement.update_search()
        replacement.status.setText(replacement.status.text() + " · Обновлено")
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
        QMessageBox.warning(window, "Не удалось обновить", f"Не удалось применить изменения:\n{error}")
        return None
