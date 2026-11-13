"""Workspace composition: navigation rail, page heading and compact utilities."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                              QScrollArea, QWidget, QLayout, QSizePolicy)
from ui_icons import line_icon
from i18n import tr

PAGES = {
    'ai': ('ИИ-поиск', 'Опишите ситуацию — найдём статьи выбранного сервера и объясним их.'),
    'laws': ('Законы и кодексы', 'От ситуации к нужной статье — за несколько секунд.'),
    'rules': ('Правила сервера', 'Всё, что нужно знать для уверенной игры.'),
    'earnings': ('Ваши финансы', 'Доходы, расходы и сделки в одном пространстве.'),
    'notepad': ('Личные заметки', 'Сохраните важное, чтобы вернуться к нему позже.'),
}


def install_workspace(w, top_row, filter_row, bottom_layout):
    sidebar = QFrame()
    sidebar.setObjectName('sidebar')
    sidebar.setFixedWidth(218)
    sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    outer = QVBoxLayout(sidebar)
    outer.setContentsMargins(0, 0, 0, 0)
    sidebar_scroll = QScrollArea()
    sidebar_scroll.setObjectName('sidebarScroll')
    sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
    sidebar_scroll.setWidgetResizable(True)
    sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    sidebar_content = QWidget()
    sidebar_content.setObjectName('sidebarContent')
    side = QVBoxLayout(sidebar_content)
    side.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    sidebar_scroll.setWidget(sidebar_content)
    outer.addWidget(sidebar_scroll)
    w.sidebar_scroll = sidebar_scroll
    w.sidebar_content = sidebar_content
    w.side_layout = side
    side.setContentsMargins(12, 18, 12, 16)
    side.setSpacing(7)
    logo_row = QHBoxLayout()
    logo = QLabel('C')
    logo.setObjectName('monogram')
    logo.setFixedSize(34, 34)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo_row.addWidget(logo)
    brand = QLabel('CARLEONE\nHELPER')
    brand.setObjectName('sidebarBrand')
    logo_row.addWidget(brand)
    logo_row.addStretch()
    side.addLayout(logo_row)
    side.addSpacing(24)
    caption = QLabel('РАБОЧЕЕ ПРОСТРАНСТВО')
    w.nav_caption = caption
    caption.setObjectName('eyebrow')
    side.addWidget(caption)
    side.addSpacing(5)
    w.nav_buttons = {}
    w.nav_captions = {}
    w.workspace_labels = [(w.nav_caption, "РАБОЧЕЕ ПРОСТРАНСТВО")]
    for index, (mode, caption) in enumerate((('laws', 'Законы'), ('rules', 'Правила'), ('earnings', 'Финансы'), ('notepad', 'Заметки'), ('ai', 'ИИ-поиск'))):
        button = QPushButton(tr(caption))
        button.setObjectName('navItem')
        button.setCheckable(True)
        button.setFixedHeight(44)
        button.setIcon(line_icon(mode))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        def navigate(_checked=False, index=index):
            w.mode_selector.setCurrentIndex(index)
            sync_workspace(w)
        button.clicked.connect(navigate)
        w.nav_buttons[mode] = button
        w.nav_captions[mode] = caption
        side.addWidget(button)
    side.addSpacing(20)
    w.collection_caption = QLabel('БЫСТРЫЙ ДОСТУП')
    w.collection_caption.setObjectName('eyebrow')
    side.addWidget(w.collection_caption)
    w.workspace_labels.append((w.collection_caption, "БЫСТРЫЙ ДОСТУП"))
    for button, icon in [(w.favorites_button, 'favorite'), (w.suspect_button, 'suspect')]:
        w.suspect_row_widget.layout().removeWidget(button)
        button.setIcon(line_icon(icon))
        button.setProperty('sidebarItem', True)
        button.setFixedHeight(40)
        side.addWidget(button)
    w.suspect_row_widget.layout().removeWidget(w.clear_suspect_button)
    side.addWidget(w.clear_suspect_button, alignment=Qt.AlignmentFlag.AlignRight)
    w.suspect_row_widget.hide()
    side.addStretch(1)
    w.server_caption = QLabel('ТЕКУЩИЙ СЕРВЕР')
    w.server_caption.setObjectName('eyebrow')
    side.addWidget(w.server_caption)
    w.workspace_labels.append((w.server_caption, "ТЕКУЩИЙ СЕРВЕР"))
    filter_row.removeWidget(w.server)
    w.server.setMinimumWidth(0)
    w.server.setFixedWidth(182)
    side.addWidget(w.server)
    side.addSpacing(12)
    utilities = QHBoxLayout()
    utilities.setSpacing(5)
    for button, icon, caption in [(w.settings_button, 'settings', 'Настройки'), (w.refresh_button, 'refresh', 'Обновить')]:
        top_row.removeWidget(button)
        filter_row.removeWidget(button)
        button.setMinimumSize(0, 0)
        button.setMaximumSize(16777215, 16777215)
        button.setObjectName('utilityButton')
        button.setStyleSheet('')
        button.setIcon(line_icon(icon))
        button.setFixedHeight(34)
        utilities.addWidget(button)
    side.addLayout(utilities)
    if hasattr(w, 'account_button'):
        bottom_layout.removeWidget(w.account_button)
        w.account_button.setObjectName('sidebarAccount')
        side.addWidget(w.account_button)
    bottom_layout.removeWidget(w.discord_button)
    w.discord_button.setText(tr('Сообщество и поддержка ↗'))
    w.workspace_labels.append((w.discord_button, 'Сообщество и поддержка ↗'))
    w.discord_button.setStyleSheet('')
    side.addWidget(w.discord_button)
    bottom_layout.removeWidget(w.author)
    w.author.setWordWrap(True)
    w.author.setAlignment(Qt.AlignmentFlag.AlignLeft)
    side.addWidget(w.author)
    w.workspace_layout.insertWidget(0, sidebar)
    w.sidebar = sidebar
    # Keep the selector as the single source of section switching for saved state.
    top_row.removeWidget(w.mode_selector)
    w.mode_selector.hide()
    w.earnings_top_spacer.hide()
    w.search.setObjectName('workspaceSearch')
    w.search.addAction(line_icon('search'), w.search.ActionPosition.LeadingPosition)
    w.search.setFixedHeight(50)
    w.search_shortcut = QShortcut('Ctrl+K', w)
    w.search_shortcut.activated.connect(lambda: (w.search.setFocus(), w.search.selectAll()))
    hero = QHBoxLayout()
    hero.setContentsMargins(0, 0, 0, 10)
    title_column = QVBoxLayout()
    title_column.setSpacing(5)
    eyebrow = QLabel('ВАШ ИГРОВОЙ АССИСТЕНТ')
    eyebrow.setObjectName('eyebrow')
    w.page_heading = QLabel()
    w.page_heading.setObjectName('pageHeading')
    w.page_subtitle = QLabel()
    w.page_subtitle.setObjectName('pageSubtitle')
    w.workspace_labels.append((eyebrow, 'ВАШ ИГРОВОЙ АССИСТЕНТ'))
    title_column.addWidget(eyebrow)
    title_column.addWidget(w.page_heading)
    title_column.addWidget(w.page_subtitle)
    hero.addLayout(title_column, 1)
    w.result_badge = QLabel()
    w.result_badge.setObjectName('resultBadge')
    hero.addWidget(w.result_badge, alignment=Qt.AlignmentFlag.AlignTop)
    w.main_layout.insertLayout(0, hero)
    sync_workspace(w)


def sync_workspace(w):
    if not hasattr(w, 'nav_buttons'):
        return
    for label, source in w.workspace_labels:
        label.setText(tr(source))
    for mode, button in w.nav_buttons.items():
        button.setChecked(mode == w.mode)
        button.setText(tr(w.nav_captions[mode]))
    title, subtitle = PAGES[w.mode]
    w.page_heading.setText(tr(title))
    w.page_subtitle.setText(tr(subtitle))
    documents = w.mode in ('laws', 'rules')
    w.nav_caption.show()
    w.collection_caption.setVisible(documents)
    w.author.show()
    w.favorites_button.setVisible(documents)
    w.suspect_button.setVisible(documents)
    w.server_caption.setVisible(w.mode != 'notepad')
    w.result_badge.setVisible(documents)
