import sys
import re
import json
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


from codex_data import load_articles
from road_data import load_road_articles
from procedure_data import load_procedure_articles
from labor_data import load_labor_articles
from rules_data import load_rules, split_rule_punishment
from extra_laws_data import EXTRA_LAWS, load_extra_laws
from window_hotkey import application_hotkey
from forum_updates import application_updates
from app_settings import SettingsStore, SettingsDialog, validate_preferences
from i18n import tr, LocalizedLabel
from penalty_data import punishment_text, penalty_supplement, SOURCE_URL as PENALTY_SOURCE_URL
from suspect_selection import SuspectStore, article_key
from dark_combo import DarkComboBox

ARTICLES = (
    load_articles() + load_road_articles()
    + load_procedure_articles() + load_labor_articles() + load_extra_laws()
)

SERVER_DATA = {
    name.lower(): {'name': name, 'laws': [], 'rules': [], 'in_development': True}
    for name in ('Downtown', 'Eclipse', 'Rockford', 'Redwood', 'Murrieta', 'Chiliad', 'Mirror', 'Blaine')
}
SERVER_DATA['murrieta'] = {'name': 'Murrieta', 'laws': ARTICLES, 'rules': load_rules('murrieta')}
RULE_CATEGORIES = ('Все', 'Общие правила', 'Госорганизации', 'Криминальные организации', 'Неофициальные организации')
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
QFrame#article_card:hover {
    border-color: #a1bdd8;
}
QPushButton#suspect_filter, QPushButton#suspect_add {
    font-size: 13px;
    padding: 6px 10px;
    border-radius: 8px;
}
QPushButton#suspect_add:checked {
    background-color: #2b4154;
    border-color: #7197b9;
    color: #d5e8fa;
}
QPushButton#load_more {
    font-size: 12px;
    padding: 2px 9px;
    border-radius: 7px;
    color: #aab8c6;
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
        self.setToolTip(tr("Нажми, чтобы скопировать этот блок"))

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

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("Нажми, чтобы скопировать статью"))

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
    def __init__(self, server_data=None, selection_settings=None):
        super().__init__()
        self.settings_store = SettingsStore()
        self.suspect_store = SuspectStore(selection_settings)
        self.suspect_selections = self.suspect_store.load()
        self.preferences = self.settings_store.load()
        QApplication.instance().setApplicationDisplayName('GTA 5 RP HELPER')
        QApplication.instance().setProperty('ui_language', self.preferences['language'])
        flags = Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if self.preferences['always_on_top']:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
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
        self.suspect_filter_modes = {'laws': False, 'rules': False}
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

        self.setWindowTitle(tr("GTA 5 RP HELPER — помощник GTA 5 RP"))
        self.resize(1100, 740)
        self.setMinimumSize(920, 500)
        self.setStyleSheet(self.preference_stylesheet())

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
        title = QLabel("GTA 5 RP HELPER")
        title.setObjectName("brand")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_layout.addWidget(title)
        self.hotkey_hint = LocalizedLabel("F4 — показать / скрыть")
        self.hotkey_hint.setObjectName("status")
        self.hotkey_hint.setWordWrap(True)
        hint_policy = self.hotkey_hint.sizePolicy()
        hint_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.hotkey_hint.setSizePolicy(hint_policy)
        self.hotkey_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        title_layout.addWidget(self.hotkey_hint, stretch=1)
        header_layout.addWidget(self.drag_region, stretch=1)
        header_layout.addSpacing(11)
        for name, standard_icon, callback in (
            ("Свернуть окно", QStyle.StandardPixmap.SP_TitleBarMinButton, self.showMinimized),
            ("Развернуть / восстановить", QStyle.StandardPixmap.SP_TitleBarMaxButton, self.toggle_maximized),
            ("Закрыть", QStyle.StandardPixmap.SP_TitleBarCloseButton, self.close),
        ):
            button = QToolButton()
            button.setCursor(Qt.CursorShape.ArrowCursor)
            button.setIcon(self.style().standardIcon(standard_icon))
            button.setFixedSize(32, 28)
            button.setStyleSheet("padding: 0px;")
            button.setProperty('ui_text', name)
            button.setToolTip(tr(name))
            button.setAccessibleName(tr(name))
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
        self.search.setPlaceholderText(tr("Поиск по законам"))
        self.search.setClearButtonEnabled(True)
        top_row.addWidget(self.search, stretch=1)

        mode_frame = QFrame()
        mode_frame.setObjectName("mode_switch")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(3, 3, 3, 3)
        mode_layout.setSpacing(3)

        laws_button = QPushButton(tr("Законы"))
        laws_button.setCheckable(True)
        laws_button.setChecked(True)

        rules_button = QPushButton(tr("Правила"))
        rules_button.setCheckable(True)

        mode_layout.addWidget(laws_button)
        mode_layout.addWidget(rules_button)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(laws_button, 0)
        self.mode_group.addButton(rules_button, 1)
        self.mode_group.idClicked.connect(self.change_mode)

        top_row.addWidget(mode_frame)
        self.suspect_button = QPushButton()
        self.suspect_button.setObjectName('suspect_filter')
        self.suspect_button.setCheckable(True)
        self.suspect_button.clicked.connect(self.toggle_suspect_filter)
        self.clear_suspect_button = QToolButton()
        self.clear_suspect_button.setText('×')
        self.clear_suspect_button.setFixedSize(26, 28)
        self.clear_suspect_button.setStyleSheet('padding: 0px; font-size: 20px;')
        self.clear_suspect_button.clicked.connect(self.clear_suspect_selection)
        self.clear_suspect_button.hide()
        self.settings_button = QToolButton()
        self.settings_button.setText('⚙')
        self.settings_button.setFixedSize(38, 38)
        self.settings_button.setStyleSheet('font-size: 24px; padding: 0px;')
        self.settings_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.settings_button.setToolTip(tr('Настройки'))
        self.settings_button.setAccessibleName(tr('Настройки приложения'))
        self.settings_button.clicked.connect(self.open_settings)
        top_row.addWidget(self.settings_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(top_row)

        suspect_row = QHBoxLayout()
        suspect_row.setSpacing(6)
        suspect_row.addWidget(self.suspect_button)
        suspect_row.addWidget(self.clear_suspect_button)
        suspect_row.addStretch()
        main_layout.addLayout(suspect_row)

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
            button = QPushButton(tr(name))
            button.setProperty('category', name)
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
        self.expand_categories_button.setAccessibleName(tr("Развернуть остальные разделы законов"))
        self.expand_categories_button.toggled.connect(self.toggle_extra_categories)
        filter_row.addWidget(self.expand_categories_button, alignment=Qt.AlignmentFlag.AlignTop)
        filter_row.addStretch()

        self.server = DarkComboBox()
        for server_id, data in self.server_data.items():
            self.server.addItem(data["name"], server_id)
        default_server = self.server.findData('murrieta')
        if default_server >= 0:
            self.server.setCurrentIndex(default_server)
        filter_row.addWidget(self.server, alignment=Qt.AlignmentFlag.AlignTop)

        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_button.setFixedSize(30, 38)
        self.refresh_button.setStyleSheet("padding: 0px;")
        self.refresh_button.setToolTip(tr("Применить изменения интерфейса и локальных данных"))
        self.refresh_button.setAccessibleName(tr("Обновить приложение"))
        self.refresh_button.clicked.connect(self.refresh_application)
        filter_row.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(filter_row)
        main_layout.addWidget(self.extra_categories)
        self.refresh_category_visibility()

        self.topic = DarkComboBox()
        self.topic.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.topic.setMinimumContentsLength(20)
        self.topic.setToolTip(tr("Тема правил"))
        self.topic.addItem(tr("Все темы"), "")
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

        self.load_more_button = QPushButton(tr("Показать ещё"))
        self.load_more_button.setObjectName("load_more")
        self.load_more_button.setFixedHeight(24)
        self.load_more_button.clicked.connect(self.load_more_results)
        self.load_more_button.hide()

        # Нижняя строка.
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.left_resize_grip = QSizeGrip(self)
        self.left_resize_grip.setFixedSize(16, 16)
        footer.addWidget(self.left_resize_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        self.status = LocalizedLabel()
        self.status.setObjectName("status")
        footer.addWidget(self.status)
        footer.addWidget(self.load_more_button)
        footer.addStretch()

        self.forum_status = LocalizedLabel("Форум: ожидание")
        self.forum_status.setStyleSheet("padding: 0px 6px; font-size: 12px;")
        self.forum_status.setAccessibleName(tr("Состояние проверки форума"))
        footer.addWidget(self.forum_status)

        self.note = QLabel()
        self.note.setObjectName("status")
        footer.addWidget(self.note)
        self.resize_grip = QSizeGrip(self)
        self.resize_grip.setFixedSize(16, 16)
        footer.addWidget(self.resize_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(2)
        bottom_layout.addLayout(footer)
        version = json.loads(Path(__file__).with_name('version.json').read_text(encoding='utf-8-sig'))['version']
        QApplication.instance().setApplicationVersion(version)
        self.author = LocalizedLabel(f'Автор: Lucifer Mentality · Версия {version}')
        self.author.setObjectName('author')
        self.author.setStyleSheet('color: #8d98a3; font-size: 11px;')
        self.author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(self.author)
        main_layout.addLayout(bottom_layout)

        self.search.textChanged.connect(self.schedule_search)
        self.server.currentIndexChanged.connect(self.change_server)
        self.topic.currentIndexChanged.connect(self.update_search)
        self.scroll.verticalScrollBar().valueChanged.connect(self.schedule_load_more)
        self.update_search()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_top_drag_region()
        self.apply_results_width()
        application_hotkey().attach(self, self.preferences['hotkey'])
        application_updates().attach(self)

    def preference_stylesheet(self):
        alpha = round(255 * self.preferences['background_opacity'] / 100)
        return STYLE.replace('rgba(18, 22, 25, 242)', f'rgba(18, 22, 25, {alpha})')

    def open_settings(self):
        existing = getattr(self, 'settings_dialog', None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self.settings_dialog = SettingsDialog(self.preferences, self.apply_preferences, self)
        self.settings_dialog.open()

    def apply_preferences(self, values):
        values = validate_preferences(values)
        manager = application_hotkey()
        old_key = self.preferences['hotkey']
        if values['hotkey'] != old_key and not manager.try_change(self, values['hotkey']):
            raise ValueError(tr('Клавиша {key} занята другой программой. Выберите другую.', key=values['hotkey']))
        try:
            self.settings_store.save(values)
        except Exception:
            manager.attach(self, old_key)
            raise
        language_changed = self.preferences['language'] != values['language']
        self.preferences = values
        QApplication.instance().setProperty('ui_language', values['language'])
        self.setStyleSheet(self.preference_stylesheet())
        is_visible = self.isVisible()
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != values['always_on_top']:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, values['always_on_top'])
            if is_visible:
                self.show()
        manager.attach(self, values['hotkey'])
        self._category_layout_signature = None
        self.reflow_categories()
        if language_changed:
            self.retranslate_ui()

    def retranslate_ui(self):
        category, topic = self.category, self.topic.currentData()
        self.setWindowTitle(tr('GTA 5 RP HELPER — помощник GTA 5 RP'))
        for button in self.title_bar.findChildren(QToolButton):
            source = button.property('ui_text')
            if source:
                button.setToolTip(tr(source))
                button.setAccessibleName(tr(source))
        self.mode_group.button(0).setText(tr('Законы'))
        self.mode_group.button(1).setText(tr('Правила'))
        self.search.setPlaceholderText(tr('Поиск по правилам' if self.mode == 'rules' else 'Поиск по законам'))
        self.settings_button.setToolTip(tr('Настройки'))
        self.settings_button.setAccessibleName(tr('Настройки приложения'))
        self.refresh_button.setToolTip(tr('Применить изменения интерфейса и локальных данных'))
        self.refresh_button.setAccessibleName(tr('Обновить приложение'))
        self.topic.setToolTip(tr('Тема правил'))
        self.forum_status.setAccessibleName(tr('Состояние проверки форума'))
        self.rebuild_categories()
        for button in self.category_group.buttons():
            if button.property('category') == category:
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
        self.hotkey_hint.retranslate()
        self.forum_status.retranslate()
        self.author.retranslate()

    def selected_suspect_keys(self):
        keys = self.suspect_selections.get(self.server.currentData(), set())
        return {key for key in keys if key[0].startswith('Правило:') == (self.mode == 'rules')}

    def update_suspect_controls(self):
        selected = self.selected_suspect_keys()
        count = sum(article_key(article) in selected for article in self.current_records())
        is_rules = self.mode == 'rules'
        name = 'Нарушения игрока ({count})' if is_rules else 'Нарушения подозреваемого ({count})'
        self.suspect_button.setText(tr(name, count=count))
        self.suspect_button.setAccessibleName(tr(name, count=count))
        self.suspect_button.setToolTip(tr('Показать выбранные нарушения игрока' if is_rules else 'Показать выбранные статьи подозреваемого'))
        self.clear_suspect_button.setVisible(self.suspect_button.isChecked() and bool(selected))
        clear_name = tr('Очистить нарушения игрока' if is_rules else 'Очистить нарушения подозреваемого')
        self.clear_suspect_button.setToolTip(clear_name)
        self.clear_suspect_button.setAccessibleName(clear_name)
        for button in self.scroll.widget().findChildren(QPushButton, 'suspect_add'):
            key = button.property('article_code'), button.property('article_number')
            checked = key in selected
            button.setChecked(checked)
            button.setText(tr('✓ В списке' if checked else '+ В нарушения'))
            source = ('Убрать правило из нарушений' if checked else 'Добавить правило в нарушения') if is_rules else ('Убрать статью из нарушений' if checked else 'Добавить статью в нарушения')
            button.setToolTip(tr(source))

    def save_suspect_selection(self, keys):
        other_mode = self.suspect_selections.get(self.server.currentData(), set()) - self.selected_suspect_keys()
        selections = {**self.suspect_selections, self.server.currentData(): other_mode | keys}
        try:
            self.suspect_store.save(selections)
        except OSError as error:
            QMessageBox.warning(self, tr('Не удалось сохранить список нарушений.'), tr(str(error)))
            self.update_suspect_controls()
            return False
        self.suspect_selections = selections
        return True

    def toggle_suspect_article(self, key):
        selected = set(self.selected_suspect_keys())
        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)
        if not self.save_suspect_selection(selected):
            return
        if self.suspect_button.isChecked():
            position = self.scroll.verticalScrollBar().value()
            self.update_search()
            self.scroll.verticalScrollBar().setValue(position)
        else:
            self.update_suspect_controls()

    def toggle_suspect_filter(self, checked):
        self.suspect_filter_modes[self.mode] = checked
        if checked:
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.rebuild_categories()
        self.update_search()

    def clear_suspect_selection(self):
        if self.save_suspect_selection(set()):
            self.update_search()

    def apply_forum_update(self, catalog):
        # A checker started before live reload may still return unsplit rule text.
        rules = []
        for rule in catalog['rules']:
            description, punishment = split_rule_punishment(rule['description'], rule.get('punishment', ''))
            rules.append({**rule, 'source_text': rule.get('source_text', rule['description']),
                          'description': description, 'punishment': punishment})
        catalog = {**catalog, 'rules': rules}
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
        self.left_resize_grip.setVisible(not self.isMaximized())

    def toggle_from_hotkey(self, foreground=None):
        active = self.isActiveWindow() if foreground is None else foreground
        if self.isVisible() and not self.isMinimized() and active:
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
                card = self.create_article_card(article)
                self.results_layout.addWidget(card)
                # Include new cards in height calculations before Qt's deferred
                # child-show events; otherwise a formerly empty list collapses.
                card.show()
            self.rendered_count = end
        finally:
            self.results_layout.setEnabled(True)
            results.setUpdatesEnabled(True)
            self._loading_results = False
        self.update_result_status()
        self.apply_results_width()

    def update_result_status(self):
        count = len(self.filtered_articles)
        noun = tr("правил" if self.mode == "rules" else "статей")
        self.status.setText(tr('Найдено {noun}: {count} · Показано: {shown}', noun=noun, count=count, shown=self.rendered_count))
        remaining = count - self.rendered_count
        self.load_more_button.setVisible(remaining > 0)
        self.load_more_button.setText(tr('Показать ещё {count}', count=min(remaining, RESULT_BATCH_SIZE)))

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
                arrow_width = self.expand_categories_button.fontMetrics().horizontalAdvance(tr("Свернуть")) + 48
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
        self.expand_categories_button.setText(tr("Свернуть" if expanded else "Ещё"))
        selected_extra = self.category if self.category in overflow else ""
        tooltip = tr("Свернуть разделы" if expanded else "Развернуть остальные разделы")
        if selected_extra:
            tooltip += tr(' · Выбран раздел: {category}', category=tr(selected_extra))
        self.expand_categories_button.setToolTip(tooltip)
        self.expand_categories_button.setAccessibleName(tooltip)
        if is_laws and not expanded and selected_extra:
            self.expand_categories_button.setText(tr('Ещё: {category}', category=tr(selected_extra)))

    def rebuild_categories(self):
        self._category_layout_signature = None
        for button in self.category_group.buttons():
            self.category_group.removeButton(button)
            self.category_layout.removeWidget(button)
            self.extra_category_layout.removeWidget(button)
            button.hide()
            button.deleteLater()
        if self.mode == 'laws':
            names = LAW_CATEGORIES
        elif self.server_data.get(self.server.currentData(), {}).get('in_development'):
            names = RULE_CATEGORIES
        else:
            names = ('Все', *dict.fromkeys(a['category'] for a in self.current_records()))
        self.category = "Все"
        for index, name in enumerate(names):
            label = {"Криминальные организации": "Криминальные",
                     "Неофициальные организации": "Неофициальные"}.get(name, name)
            button = QPushButton(tr(label))
            button.setObjectName("category_tab")
            button.setProperty("compact", self.mode == "rules")
            button.setProperty("category", name)
            button.setToolTip(tr(name))
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
        self.topic.addItem(tr("Все темы"), "")
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
        self.suspect_filter_modes[self.mode] = self.suspect_button.isChecked()
        self.mode = mode
        self.suspect_button.setChecked(self.suspect_filter_modes[mode])
        self.search.setPlaceholderText(tr("Поиск по правилам" if self.mode == "rules" else "Поиск по законам"))
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
        display_number = article['number']
        if display_number.startswith('Справка'):
            display_number = tr('Справка') + display_number[len('Справка'):]
        article_number = (
            f"{chapter_number} · {display_number}"
            if chapter_number else display_number
        )
        number = CopyLabel(
            f"{tr(article.get('code', 'УАК'))} {article_number}",
            "article_number",
            lambda: self.status.setText("✓ Номер статьи скопирован"),
        )
        number.setWordWrap(False)

        heading = tr('Статья {number} — {title}', number=article['number'], title=article['title'])
        if article.get("kind") == "rule":
            heading = tr('{category} · Пункт {number} — {title}', category=tr(article['category']), number=article['number'], title=article['title'])
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
        if not article['number'].startswith('Справка'):
            add_button = QPushButton()
            add_button.setObjectName('suspect_add')
            add_button.setCheckable(True)
            key = article_key(article)
            add_button.setProperty('article_code', key[0])
            add_button.setProperty('article_number', key[1])
            selected = key in self.selected_suspect_keys()
            add_button.setChecked(selected)
            add_button.setText(tr('✓ В списке' if selected else '+ В нарушения'))
            if article.get('kind') == 'rule':
                add_button.setToolTip(tr('Убрать правило из нарушений' if selected else 'Добавить правило в нарушения'))
            else:
                add_button.setToolTip(tr('Убрать статью из нарушений' if selected else 'Добавить статью в нарушения'))
            add_button.clicked.connect(lambda _checked=False, key=key: self.toggle_suspect_article(key))
            heading_row.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(heading_row)

        description = CopyLabel(
            article["description"],
            "description",
            lambda: self.status.setText("✓ Описание скопировано"),
        )
        card_layout.addWidget(description)

        punishment_style = (
            "criminal_punishment"
            if article["category"] == "Уголовный" or article.get('kind') == 'rule'
            else "admin_punishment"
        )

        if article["punishment"]:
            punishment = CopyLabel(
                punishment_text(article, self.server.currentData()),
                punishment_style,
                lambda: self.status.setText("✓ Наказание скопировано"),
            )
            if penalty_supplement(article, self.server.currentData()):
                punishment.setToolTip(tr('Нажми, чтобы скопировать этот блок') + '\n' + PENALTY_SOURCE_URL)
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
            if self.suspect_button.isChecked() and article_key(article) not in self.selected_suspect_keys():
                continue
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
            message = tr("Ничего не найдено. Измени запрос или выбери «Все».")
            if self.suspect_button.isChecked() and not self.selected_suspect_keys():
                message = tr('Список нарушений пуст. Добавь правила кнопкой «+ В нарушения» в разделе правил.' if self.mode == 'rules' else 'Список нарушений пуст. Добавь статьи кнопкой «+ В нарушения» в разделе законов.')
            if not records:
                section = tr("Правила" if self.mode == "rules" else "Законы")
                message = tr('{section} для сервера {server} ещё не добавлены.', section=section, server=self.server.currentText())
                if self.server_data.get(self.server.currentData(), {}).get('in_development'):
                    message = tr('В разработке')
            empty = make_label(
                message,
                "description",
            )
            self.results_layout.addWidget(empty)
            empty.show()

        self.update_result_status()
        self.update_suspect_controls()
        section = tr("Правила сервера" if self.mode == "rules" else "Кодексы")
        self.note.setText(f"{self.server.currentText()} · {section}")
        self.scroll.verticalScrollBar().setValue(0)
        self.apply_results_width()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = CarleoneWindow()
    window.show()

    sys.exit(app.exec())
