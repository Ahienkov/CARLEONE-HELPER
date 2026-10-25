import sys
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


from codex_data import load_articles
from road_data import load_road_articles
from procedure_data import load_procedure_articles
from labor_data import load_labor_articles
from rules_data import load_rules
from extra_laws_data import EXTRA_LAWS, load_extra_laws
from window_hotkey import application_hotkey
from forum_updates import application_updates

ARTICLES = (
    load_articles() + load_road_articles()
    + load_procedure_articles() + load_labor_articles() + load_extra_laws()
)

SERVER_DATA = {
    "murrieta": {
        "name": "Murrieta", "laws": ARTICLES, "rules": load_rules("murrieta"),
    },
}
LAW_CATEGORIES = (
    "Все", "Уголовный", "Административный", "Дорожный", "Процессуальный", "Трудовой",
    *(law["category"] for law in EXTRA_LAWS),
)
RESULT_BATCH_SIZE = 30
SEARCH_DELAY_MS = 150
CATEGORY_COLUMNS = 3
RESIZE_SETTLE_MS = 80


def searchable_article_text(article):
    return normalize(
        f"{article.get('code', 'УАК')} {article['number']} {article['title']} "
        f"{article['description']} {article['punishment']} "
        f"{article.get('chapter', '')} {article['keywords']}"
    )


STYLE = """
QMainWindow {
    background: transparent;
}
QWidget#root {
    background-color: rgba(18, 22, 25, 242);
    border: 1px solid rgba(130, 150, 170, 90);
    border-radius: 20px;
}
QWidget {
    font-family: "Segoe UI";
    font-size: 15px;
    color: #d9dcdf;
}
QLabel {
    background: transparent;
}
QLineEdit {
    background-color: #14181e;
    border: 1px solid #56616c;
    border-radius: 10px;
    padding: 13px 16px;
    color: #e5e7eb;
    font-size: 18px;
    selection-background-color: #455c75;
}
QLineEdit:focus {
    border-color: #91a8c1;
}
QLabel#brand {
    font-size: 19px;
    font-weight: bold;
    padding: 0px 12px;
    color: #f1f3f5;
}
QPushButton, QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    color: #a0a8b1;
    padding: 10px 14px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #242c32;
    color: #ffffff;
}
QPushButton:checked, QToolButton:checked {
    background-color: #555f69;
    color: #ffffff;
    font-weight: bold;
}
QPushButton:disabled, QToolButton:disabled {
    color: #555d65;
}
QPushButton#category_tab[compact="true"] {
    font-size: 13px;
    padding: 7px 10px;
    border-radius: 8px;
}
QFrame#mode_switch {
    border: 1px solid #56616c;
    border-radius: 10px;
}
QComboBox {
    background-color: #161b20;
    border: 1px solid #56616c;
    border-radius: 9px;
    padding: 9px 14px;
    min-width: 155px;
}
QComboBox QAbstractItemView {
    background-color: #1b2229;
    color: #e0e4e8;
    selection-background-color: #555f69;
    border: 1px solid #56616c;
    border-radius: 10px;
    padding: 4px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    border-top-right-radius: 9px;
    border-bottom-right-radius: 9px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QWidget#results {
    background: transparent;
}
QFrame#article_card {
    background-color: #1b2229;
    border: 1px solid #64717e;
    border-radius: 16px;
}
QLabel#article_number {
    border: 1px solid #56616c;
    border-radius: 7px;
    color: #aab4bd;
    padding: 5px 9px;
    font-size: 13px;
    font-weight: bold;
}
QLabel#article_title {
    color: #e0e2e5;
    font-size: 17px;
    font-weight: bold;
}
QLabel#description {
    background-color: rgba(160, 170, 180, 25);
    color: #c5cdd5;
    border: 1px solid rgba(160, 170, 180, 55);
    border-radius: 10px;
    padding: 14px;
    font-size: 15px;
}
QLabel#criminal_punishment {
    background-color: #211c20;
    color: #ff6565;
    border: 1px solid #b34045;
    border-radius: 10px;
    padding: 13px;
}
QLabel#admin_punishment {
    background-color: #252019;
    color: #efb16a;
    border: 1px solid #a77942;
    border-radius: 10px;
    padding: 13px;
}
QLabel#status {
    color: #8d98a3;
    font-size: 13px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #46515b;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


def normalize(text):
    return text.casefold().replace("ё", "е")


def article_search_priority(article, number):
    """Keep direct number matches ahead of references in other articles."""
    if number is None:
        return 0
    if article["number"] == number:
        return 0
    if article["number"].startswith(number + "."):
        return 1
    return 2


def make_label(text, object_name):
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )
    return label

class CopyLabel(QLabel):
    def __init__(self, text, object_name, on_copied):
        super().__init__(text)
        self.on_copied = on_copied
        self.press_position = None

        self.setObjectName(object_name)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Нажми, чтобы скопировать этот блок")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.position().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.press_position is not None:
                position = event.position().toPoint()
                distance = (
                    position - self.press_position
                ).manhattanLength()

                if (
                    self.rect().contains(position)
                    and distance < QApplication.startDragDistance()
                ):
                    QApplication.clipboard().setText(self.text())
                    self.on_copied()

            self.press_position = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class ClickableCard(QFrame):
    def __init__(self, text_to_copy, on_copied):
        super().__init__()
        self.text_to_copy = text_to_copy
        self.on_copied = on_copied
        self.press_position = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Нажми, чтобы скопировать статью")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.position().toPoint()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.press_position is not None
        ):
            position = event.position().toPoint()
            distance = (
                position - self.press_position
            ).manhattanLength()

            if (
                self.rect().contains(position)
                and distance < QApplication.startDragDistance()
            ):
                QApplication.clipboard().setText(self.text_to_copy)
                self.on_copied()

        self.press_position = None
        super().mouseReleaseEvent(event)


class WindowTitleBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().toggle_maximized()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class CarleoneWindow(QMainWindow):
    def __init__(self, server_data=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Carleone.Helper")
        icon = QIcon(str(Path(__file__).with_name("assets") / "app-icon.ico"))
        self.setWindowIcon(icon)

        self.category = "Все"
        self.law_categories_expanded = False
        self.rules_categories_expanded = False
        self._overflow_categories = []
        self._category_layout_signature = None
        self.mode = "laws"
        self.server_data = SERVER_DATA if server_data is None else server_data
        self.search_index = {
            (server_id, mode): [(article, searchable_article_text(article)) for article in data.get(mode, [])]
            for server_id, data in self.server_data.items() for mode in ("laws", "rules")
        }
        self.filtered_articles = []
        self.rendered_count = 0
        self._loading_results = False
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DELAY_MS)
        self.search_timer.timeout.connect(self.update_search)
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True)
        self.load_timer.timeout.connect(self.load_more_if_needed)
        self.results_width_timer = QTimer(self)
        self.results_width_timer.setSingleShot(True)
        self.results_width_timer.setInterval(RESIZE_SETTLE_MS)
        self.results_width_timer.timeout.connect(self.apply_results_width)

        self.setWindowTitle("CARLEONE HELPER — помощник GTA 5 RP")
        self.resize(1100, 740)
        self.setMinimumSize(920, 500)
        self.setStyleSheet(STYLE)

        root = QWidget()
        root.setObjectName("root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(20, 20, 20, 14)
        main_layout.setSpacing(16)

        self.title_bar = QWidget()
        self.title_bar.setCursor(Qt.CursorShape.ArrowCursor)
        header_layout = QHBoxLayout(self.title_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.drag_region = WindowTitleBar()
        self.drag_region.setCursor(Qt.CursorShape.SizeAllCursor)
        title_layout = QHBoxLayout(self.drag_region)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_layout.addWidget(icon_label)
        title = QLabel("CARLEONE HELPER")
        title.setObjectName("brand")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_layout.addWidget(title)
        self.hotkey_hint = QLabel("F4 — показать / скрыть")
        self.hotkey_hint.setObjectName("status")
        self.hotkey_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_layout.addWidget(self.hotkey_hint)
        title_layout.addStretch()
        header_layout.addWidget(self.drag_region, stretch=1)
        header_layout.addSpacing(11)
        for name, standard_icon, callback in (
            ("Свернуть", QStyle.StandardPixmap.SP_TitleBarMinButton, self.showMinimized),
            ("Развернуть / восстановить", QStyle.StandardPixmap.SP_TitleBarMaxButton, self.toggle_maximized),
            ("Закрыть", QStyle.StandardPixmap.SP_TitleBarCloseButton, self.close),
        ):
            button = QToolButton()
            button.setCursor(Qt.CursorShape.ArrowCursor)
            button.setIcon(self.style().standardIcon(standard_icon))
            button.setFixedSize(32, 28)
            button.setStyleSheet("padding: 0px;")
            button.setToolTip(name)
            button.setAccessibleName(name)
            button.clicked.connect(callback)
            header_layout.addWidget(button)
        main_layout.addWidget(self.title_bar)
        self.top_drag_region = WindowTitleBar(root)
        self.top_drag_region.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_region.installEventFilter(self)

        # Верхняя строка: поиск, название и разделы.
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по законам")
        self.search.setClearButtonEnabled(True)
        top_row.addWidget(self.search, stretch=1)

        mode_frame = QFrame()
        mode_frame.setObjectName("mode_switch")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(3, 3, 3, 3)
        mode_layout.setSpacing(3)

        laws_button = QPushButton("Законы")
        laws_button.setCheckable(True)
        laws_button.setChecked(True)

        rules_button = QPushButton("Правила")
        rules_button.setCheckable(True)

        mode_layout.addWidget(laws_button)
        mode_layout.addWidget(rules_button)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(laws_button, 0)
        self.mode_group.addButton(rules_button, 1)
        self.mode_group.idClicked.connect(self.change_mode)

        top_row.addWidget(mode_frame)
        main_layout.addLayout(top_row)

        # Категории и сервер.
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)

        self.category_layout = QGridLayout()
        self.category_layout.setSpacing(8)
        filter_row.addLayout(self.category_layout)
        self.extra_categories = QWidget()
        self.extra_category_layout = QGridLayout(self.extra_categories)
        self.extra_category_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_category_layout.setSpacing(8)
        for index, name in enumerate(LAW_CATEGORIES):
            button = QPushButton(name)
            button.setObjectName("category_tab")
            button.setCheckable(True)

            if name == "Все":
                button.setChecked(True)

            self.category_group.addButton(button)
            if index < 4:
                self.category_layout.addWidget(button, 0, index)
            else:
                self.extra_category_layout.addWidget(button, (index - 4) // CATEGORY_COLUMNS, (index - 4) % CATEGORY_COLUMNS)

        self.category_group.buttonClicked.connect(
            self.change_category
        )

        self.expand_categories_button = QToolButton()
        self.expand_categories_button.setCheckable(True)
        self.expand_categories_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.expand_categories_button.setAccessibleName("Развернуть остальные разделы законов")
        self.expand_categories_button.toggled.connect(self.toggle_extra_categories)
        filter_row.addWidget(self.expand_categories_button, alignment=Qt.AlignmentFlag.AlignTop)
        filter_row.addStretch()

        self.server = QComboBox()
        for server_id, data in self.server_data.items():
            self.server.addItem(data["name"], server_id)
        filter_row.addWidget(self.server, alignment=Qt.AlignmentFlag.AlignTop)

        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_button.setFixedSize(30, 38)
        self.refresh_button.setStyleSheet("padding: 0px;")
        self.refresh_button.setToolTip("Применить изменения интерфейса и локальных данных")
        self.refresh_button.setAccessibleName("Обновить приложение")
        self.refresh_button.clicked.connect(self.refresh_application)
        filter_row.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(filter_row)
        main_layout.addWidget(self.extra_categories)
        self.refresh_category_visibility()

        self.topic = QComboBox()
        self.topic.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.topic.setMinimumContentsLength(20)
        self.topic.setToolTip("Тема правил")
        self.topic.addItem("Все темы", "")
        self.topic.hide()
        main_layout.addWidget(self.topic)

        # Прокручиваемый список статей.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        results = QWidget()
        results.setObjectName("results")

        self.results_layout = QVBoxLayout(results)
        self.results_layout.setContentsMargins(0, 0, 10, 0)
        self.results_layout.setSpacing(14)
        self.results_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.scroll.setWidget(results)
        self.scroll.viewport().setAutoFillBackground(False)
        results.setAutoFillBackground(False)
        results.setFixedWidth(self.scroll.viewport().width())
        self.scroll.viewport().installEventFilter(self)
        main_layout.addWidget(self.scroll, stretch=1)

        self.load_more_button = QPushButton("Показать ещё")
        self.load_more_button.clicked.connect(self.load_more_results)
        self.load_more_button.hide()
        main_layout.addWidget(self.load_more_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Нижняя строка.
        footer = QHBoxLayout()

        self.status = QLabel()
        self.status.setObjectName("status")
        footer.addWidget(self.status)
        footer.addStretch()

        self.forum_status = QLabel("Форум: ожидание")
        self.forum_status.setStyleSheet("padding: 0px 6px; font-size: 12px;")
        self.forum_status.setAccessibleName("Состояние проверки форума")
        footer.addWidget(self.forum_status)

        self.note = QLabel()
        self.note.setObjectName("status")
        footer.addWidget(self.note)
        self.resize_grip = QSizeGrip(self)
        self.resize_grip.setFixedSize(16, 16)
        footer.addWidget(self.resize_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(footer)

        self.search.textChanged.connect(self.schedule_search)
        self.server.currentIndexChanged.connect(self.change_server)
        self.topic.currentIndexChanged.connect(self.update_search)
        self.scroll.verticalScrollBar().valueChanged.connect(self.schedule_load_more)
        self.update_search()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_top_drag_region()
        self.apply_results_width()
        application_hotkey().attach(self)
        application_updates().attach(self)

    def apply_forum_update(self, catalog):
        category, topic = self.category, self.topic.currentData()
        self.server_data["murrieta"] = catalog
        for mode in ("laws", "rules"):
            self.search_index[("murrieta", mode)] = [
                (article, searchable_article_text(article)) for article in catalog[mode]
            ]
        if self.server.currentData() != "murrieta":
            return
        self.rebuild_categories()
        for button in self.category_group.buttons():
            if (button.property("category") or button.text()) == category:
                button.setChecked(True)
                self.category = category
                break
        self.rebuild_topics()
        index = self.topic.findData(topic)
        if index >= 0:
            self.topic.blockSignals(True)
            self.topic.setCurrentIndex(index)
            self.topic.blockSignals(False)
        self.reflow_categories()
        self.update_search()

    def closeEvent(self, event):
        application_hotkey().detach(self)
        self.search_timer.stop()
        self.load_timer.stop()
        self.results_width_timer.stop()
        super().closeEvent(event)

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.resize_grip.setVisible(not self.isMaximized())

    def toggle_from_hotkey(self):
        if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
            self.hide()
            return
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def schedule_search(self, _text):
        self.load_timer.stop()
        self.search_timer.start()

    def refresh_application(self):
        import importlib
        import app_refresh
        replacement = importlib.reload(app_refresh).reload_application(self)
        if replacement is not None:
            application_updates().check_now()

    def schedule_load_more(self, _value):
        if not self._loading_results and not self.search_timer.isActive() and not self.results_width_timer.isActive():
            self.load_timer.start(0)

    def load_more_if_needed(self):
        if self.results_width_timer.isActive():
            return
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() > 0 and bar.value() >= bar.maximum() - 100:
            self.load_more_results()

    def load_more_results(self):
        if self._loading_results or self.search_timer.isActive():
            return
        end = min(self.rendered_count + RESULT_BATCH_SIZE, len(self.filtered_articles))
        if end == self.rendered_count:
            return
        self._loading_results = True
        results = self.scroll.widget()
        results.setUpdatesEnabled(False)
        self.results_layout.setEnabled(False)
        try:
            for article in self.filtered_articles[self.rendered_count:end]:
                self.results_layout.addWidget(self.create_article_card(article))
            self.rendered_count = end
        finally:
            self.results_layout.setEnabled(True)
            results.setUpdatesEnabled(True)
            self._loading_results = False
        self.update_result_status()
        self.apply_results_width()

    def update_result_status(self):
        count = len(self.filtered_articles)
        noun = "правил" if self.mode == "rules" else "статей"
        self.status.setText(f"Найдено {noun}: {count} · Показано: {self.rendered_count}")
        remaining = count - self.rendered_count
        self.load_more_button.setVisible(remaining > 0)
        self.load_more_button.setText(f"Показать ещё {min(remaining, RESULT_BATCH_SIZE)}")

    def current_records(self):
        data = self.server_data.get(self.server.currentData(), {})
        return data.get(self.mode, [])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "server") and event.size().width() != event.oldSize().width():
            self.reflow_categories()

    def eventFilter(self, watched, event):
        if watched is self.drag_region and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self.update_top_drag_region()
        if event.type() == QEvent.Type.Resize and hasattr(self, "scroll") and watched is self.scroll.viewport():
            if self.isVisible():
                self.load_timer.stop()
                self.results_width_timer.start()
            else:
                self.apply_results_width(event.size().width())
        return super().eventFilter(watched, event)

    def update_top_drag_region(self):
        position = self.drag_region.mapTo(self.centralWidget(), self.drag_region.rect().topLeft())
        self.top_drag_region.setGeometry(position.x(), 0, self.drag_region.width(), position.y())
        self.top_drag_region.raise_()

    def apply_results_width(self, width=None):
        self.results_width_timer.stop()
        viewport = self.scroll.viewport()
        width = viewport.width() if width is None else width
        if width > 0 and self.scroll.widget().width() != width:
            self.scroll.widget().setFixedWidth(width)
        results = self.scroll.widget()
        height = self.results_layout.totalHeightForWidth(width)
        if height < 0:
            height = self.results_layout.sizeHint().height()
        results.resize(width, max(viewport.height(), height))
        if self.isVisible() and not self.search_timer.isActive():
            self.load_timer.start(0)

    def reflow_categories(self):
        buttons = self.category_group.buttons()
        available = self.width() - max(self.server.sizeHint().width(), 185) - self.refresh_button.width() - 68
        if self.mode == "rules":
            widths = [button.sizeHint().width() for button in buttons]
            if sum(widths) + max(0, len(buttons) - 1) * 8 <= available:
                primary, extra = buttons, []
            else:
                arrow_width = self.expand_categories_button.fontMetrics().horizontalAdvance("Свернуть") + 48
                used, visible_count = 0, 0
                for width in widths:
                    needed = width + (8 if visible_count else 0)
                    if visible_count and used + needed > available - arrow_width:
                        break
                    used += needed
                    visible_count += 1
                primary, extra = buttons[:visible_count], buttons[visible_count:]
            columns = max(1, len(primary))
        else:
            primary, extra = buttons[:4], buttons[4:]
            available -= self.expand_categories_button.sizeHint().width() + 8
            columns = 4
        self._overflow_categories = [button.property("category") or button.text() for button in extra]
        while self.mode == "laws" and columns > 1:
            widths = [max((button.sizeHint().width() for i, button in enumerate(primary)
                           if i % columns == column), default=0) for column in range(columns)]
            if sum(widths) + (columns - 1) * 8 <= available:
                break
            columns -= 1
        signature = (self.mode, tuple(id(button) for button in buttons), columns, len(primary))
        if signature == self._category_layout_signature:
            return
        self._category_layout_signature = signature
        for button in buttons:
            self.category_layout.removeWidget(button)
            self.extra_category_layout.removeWidget(button)
        for index, button in enumerate(primary):
            self.category_layout.addWidget(button, index // columns, index % columns)
            button.show()
        for index, button in enumerate(extra):
            self.extra_category_layout.addWidget(button, index // CATEGORY_COLUMNS, index % CATEGORY_COLUMNS)
            button.show()
        self.refresh_category_visibility()

    def toggle_extra_categories(self, expanded):
        if self.mode == "laws":
            self.law_categories_expanded = expanded
        else:
            self.rules_categories_expanded = expanded
        self.refresh_category_visibility()
        self.reflow_categories()

    def refresh_category_visibility(self):
        is_laws = self.mode == "laws"
        overflow = LAW_CATEGORIES[4:] if is_laws else self._overflow_categories
        expanded = bool(overflow) and (self.law_categories_expanded if is_laws else self.rules_categories_expanded)
        self.extra_categories.setVisible(expanded)
        self.expand_categories_button.setVisible(bool(overflow))
        self.expand_categories_button.blockSignals(True)
        self.expand_categories_button.setChecked(expanded)
        self.expand_categories_button.blockSignals(False)
        self.expand_categories_button.setArrowType(Qt.ArrowType.UpArrow if expanded else Qt.ArrowType.DownArrow)
        self.expand_categories_button.setText("Свернуть" if expanded else "Ещё")
        selected_extra = self.category if self.category in overflow else ""
        tooltip = "Свернуть разделы" if expanded else "Развернуть остальные разделы"
        if selected_extra:
            tooltip += f" · Выбран раздел: {selected_extra}"
        self.expand_categories_button.setToolTip(tooltip)
        self.expand_categories_button.setAccessibleName(tooltip)
        if is_laws and not expanded and selected_extra:
            self.expand_categories_button.setText(f"Ещё: {selected_extra}")

    def rebuild_categories(self):
        self._category_layout_signature = None
        for button in self.category_group.buttons():
            self.category_group.removeButton(button)
            self.category_layout.removeWidget(button)
            self.extra_category_layout.removeWidget(button)
            button.hide()
            button.deleteLater()
        names = LAW_CATEGORIES if self.mode == "laws" else (
            "Все", *dict.fromkeys(a["category"] for a in self.current_records())
        )
        self.category = "Все"
        for index, name in enumerate(names):
            label = {"Криминальные организации": "Криминальные",
                     "Неофициальные организации": "Неофициальные"}.get(name, name)
            button = QPushButton(label)
            button.setObjectName("category_tab")
            button.setProperty("compact", self.mode == "rules")
            button.setProperty("category", name)
            button.setToolTip(name)
            button.setCheckable(True)
            button.setChecked(name == "Все")
            self.category_group.addButton(button)
            if self.mode == "laws" and index >= 4:
                self.extra_category_layout.addWidget(button, (index - 4) // CATEGORY_COLUMNS, (index - 4) % CATEGORY_COLUMNS)
            else:
                self.category_layout.addWidget(button, index // CATEGORY_COLUMNS, index % CATEGORY_COLUMNS)
        self.rebuild_topics()
        self.refresh_category_visibility()
        self.reflow_categories()

    def rebuild_topics(self):
        self.topic.blockSignals(True)
        self.topic.clear()
        self.topic.addItem("Все темы", "")
        topics = {}
        if self.mode == "rules":
            for rule in self.current_records():
                if self.category == "Все" or rule["category"] == self.category:
                    topics[rule.get("topic_id", rule["title"])] = rule["title"]
        for topic_id, title in topics.items():
            self.topic.addItem(title, topic_id)
        self.topic.setVisible(self.mode == "rules")
        self.topic.blockSignals(False)

    def change_mode(self, mode_id):
        mode = "rules" if mode_id == 1 else "laws"
        if mode == self.mode:
            return
        self.mode = mode
        self.search.setPlaceholderText("Поиск по правилам" if self.mode == "rules" else "Поиск по законам")
        self.rebuild_categories()
        self.update_search()

    def change_server(self, _index):
        self.rebuild_categories()
        self.update_search()

    def change_category(self, button):
        self.category = button.property("category") or button.text()
        self.refresh_category_visibility()
        self.rebuild_topics()
        self.update_search()
    
    def create_article_card(self, article):
        card = QFrame()
        card.setObjectName("article_card")
        card.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(13)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(14)

        chapter_number = article.get("chapter_number", "")
        article_number = (
            f"{chapter_number} · {article['number']}"
            if chapter_number else article["number"]
        )
        number = CopyLabel(
            f"{article.get('code', 'УАК')} {article_number}",
            "article_number",
            lambda: self.status.setText("✓ Номер статьи скопирован"),
        )
        number.setWordWrap(False)

        heading = f"Статья {article['number']} — {article['title']}"
        if article.get("kind") == "rule":
            heading = f"{article['category']} · Пункт {article['number']} — {article['title']}"
        if chapter_number:
            heading = f"{article['chapter']}\n{heading}"
        if article['number'].startswith("Справка"):
            heading = article['title']
        title = CopyLabel(
            heading,
            "article_title",
            lambda: self.status.setText("✓ Заголовок скопирован"),
        )

        heading_row.addWidget(
            number,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        heading_row.addWidget(title, stretch=1)
        card_layout.addLayout(heading_row)

        description = CopyLabel(
            article["description"],
            "description",
            lambda: self.status.setText("✓ Описание скопировано"),
        )
        card_layout.addWidget(description)

        punishment_style = (
            "criminal_punishment"
            if article["category"] == "Уголовный"
            else "admin_punishment"
        )

        if article["punishment"]:
            punishment = CopyLabel(
                article["punishment"],
                punishment_style,
                lambda: self.status.setText("✓ Наказание скопировано"),
            )
            card_layout.addWidget(punishment)

        return card

    def update_search(self, _text=None):
        self.search_timer.stop()
        self.load_timer.stop()

        words = normalize(self.search.text()).split()
        number_match = re.search(r"(?<!\w)\d+(?:\.\d+)*(?!\w)", self.search.text())
        number = number_match[0] if number_match else None
        matches = []

        records = self.current_records()
        for article, searchable_text in self.search_index.get((self.server.currentData(), self.mode), []):
            if (self.mode == "rules" and self.topic.currentData()
                    and article.get("topic_id", article["title"]) != self.topic.currentData()):
                continue
            if (
                self.category != "Все"
                and article["category"] != self.category
            ):
                continue

            if not all(word in searchable_text for word in words):
                continue

            matches.append(article)

        matches.sort(key=lambda article: (
            article_search_priority(article, number),
            self.mode == "rules" and article["number"].startswith("Справка"),
        ))
        self._loading_results = True
        results = self.scroll.widget()
        results.setUpdatesEnabled(False)
        self.results_layout.setEnabled(False)
        try:
            while self.results_layout.count():
                widget = self.results_layout.takeAt(0).widget()
                if widget is not None:
                    widget.hide()
                    widget.deleteLater()
            self.filtered_articles = matches
            self.rendered_count = 0
            self.scroll.verticalScrollBar().setValue(0)
        finally:
            self.results_layout.setEnabled(True)
            results.setUpdatesEnabled(True)
            self._loading_results = False
        self.load_more_results()
        count = len(matches)

        if count == 0:
            message = "Ничего не найдено. Измени запрос или выбери «Все»."
            if not records:
                section = "Правила" if self.mode == "rules" else "Законы"
                message = f"{section} для сервера {self.server.currentText()} ещё не добавлены."
            empty = make_label(
                message,
                "description",
            )
            self.results_layout.addWidget(empty)

        self.update_result_status()
        section = "Правила сервера" if self.mode == "rules" else "Кодексы"
        self.note.setText(f"{self.server.currentText()} · {section}")
        self.scroll.verticalScrollBar().setValue(0)
        self.apply_results_width()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = CarleoneWindow()
    window.show()

    sys.exit(app.exec())
