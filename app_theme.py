"""Shared black and yellow palette for CARLEONE HELPER."""

APP_STYLE = """

QMainWindow { background: transparent; }
QWidget#root { background-color: rgba(19, 19, 19, 242); border: 1px solid #333334; border-radius: 18px; }
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #ededee; }
QLabel { background: transparent; }
QLabel#brand { color: #77797d; font-size: 10px; letter-spacing: 2px; font-weight: 600; }
QFrame#sidebar { background: #191919; border: 1px solid #272729; border-radius: 13px; }
QLabel#monogram { background: #f5ce66; color: #191714; border-radius: 10px; font-size: 24px; font-weight: 800; }
QLabel#sidebarBrand { color: #f3f1eb; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
QLabel#eyebrow { color: #6e7075; font-size: 9px; letter-spacing: 1px; font-weight: 600; padding: 0 4px; }
QLabel#pageHeading { color: #f6f4ef; font-size: 29px; font-weight: 600; letter-spacing: -1px; }
QLabel#pageSubtitle { color: #81838a; font-size: 12px; padding-top: 3px; }
QLabel#resultBadge { color: #b2ada0; background: #25231e; border: 1px solid #39352a; border-radius: 8px; padding: 7px 12px; font-size: 11px; }
QPushButton, QToolButton { color: #93959b; background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 8px 12px; }
QPushButton:hover, QToolButton:hover { background: #262628; color: #f4f4f5; }
QPushButton:disabled, QToolButton:disabled { color: #55565b; }
QPushButton#navItem { text-align: left; padding: 8px 12px; color: #a5a5aa; font-size: 13px; font-weight: 500; }
QPushButton#navItem:checked { color: #f5ce66; background: #302a1e; border: 1px solid #4b4027; font-weight: 600; }
QWidget#sidebarContent, QScrollArea#sidebarScroll { background: transparent; border: none; }
QPushButton[sidebarItem="true"] { text-align: left; padding: 7px 12px; color: #a5a5aa; font-size: 12px; }
QPushButton[sidebarItem="true"]:checked { background: #292720; color: #f5ce66; }
QPushButton#sidebarAccount { text-align: left; color: #c9c5b9; background: #242321; border: 1px solid #37332b; padding: 9px; font-size: 11px; }
QPushButton#discord_community { text-align: left; color: #96928a; font-size: 10px; padding: 8px 2px; }
QToolButton#utilityButton { background: #222224; border: 1px solid #303033; padding: 6px; }
QToolButton#utilityButton:hover { background: #303033; border-color: #55514a; }
QPushButton#noteAdd, QPushButton#noteSave { background: #202022; border: 1px solid #343437; color: #b8b9bf; padding: 8px 14px; font-size: 12px; }
QPushButton#noteSave { background: #30291b; border-color: #51432a; color: #e8ce92; }
QPushButton#noteAdd:hover, QPushButton#noteSave:hover { background: #34302a; color: #f4e3b9; }
QLineEdit, QComboBox { background: #1b1b1d; border: 1px solid #323235; border-radius: 10px; padding: 10px 14px; color: #dedee2; selection-background-color: #5b5032; }
QLineEdit#workspaceSearch { background: #202022; border: 1px solid #37373a; border-radius: 11px; font-size: 14px; padding: 12px 10px; }
QLineEdit:focus { border-color: #aa9257; }
QComboBox { min-width: 155px; padding: 9px 14px; }
QFrame#sidebar QComboBox { min-width: 0px; font-size: 12px; background: #202022; border: 1px solid #343435; }
QComboBox::drop-down { border: none; width: 24px; }
QScrollArea { border: none; background: transparent; }
QWidget#results { background: transparent; }
QFrame#article_card { background-color: #171717; border: 1px solid #2b2b2d; border-radius: 12px; }
QFrame#article_card:hover { background: #1b1b1c; border-color: #514a39; }
QLabel#article_number { color: #e3c575; background: #2b271d; border: none; border-radius: 5px; padding: 4px 8px; font-size: 11px; font-weight: 600; }
QLabel#articleCategory { color: #73757c; font-size: 10px; }
QLabel#article_title { color: #e9e9ec; font-size: 16px; font-weight: 600; }
QPushButton#article_toggle, QPushButton#article_toggle:checked { background: transparent; border: none; padding: 2px 0; text-align: left; }
QLabel#article_expand_hint { color: #696b72; font-size: 18px; }

QPushButton#suspect_add { color: #88898e; background: transparent; border: 1px solid #353537; padding: 4px 8px; font-size: 10px; border-radius: 5px; }
QPushButton#suspect_add:checked { color: #f5ce66; background: #302a1e; border-color: #665736; }
QPushButton#favorite_add { color: #76787e; background: transparent; padding: 0; border: none; }
QPushButton#favorite_add:checked { color: #f5ce66; background: #302a1e; }
QLabel#criminal_punishment { color: #e28b8e; background: #261e20; border: none; border-left: 2px solid #99565c; border-radius: 5px; padding: 8px 11px; font-size: 12px; }
QLabel#admin_punishment { color: #e3c575; background: #28241b; border: none; border-left: 2px solid #9d8547; border-radius: 5px; padding: 8px 11px; font-size: 12px; }
QLabel#description { color: #b2b3b9; background: #202022; border: 1px solid #303034; border-radius: 8px; padding: 13px; font-size: 13px; }
QLabel#article_full_title { color: #d4d4da; font-size: 14px; }
QPushButton#category_tab { color: #85868d; padding: 8px 12px; border-radius: 7px; font-size: 12px; }
QPushButton#category_tab:checked { background: #2b281f; color: #f5ce66; border: 1px solid #4b422b; font-weight: 600; }
QPushButton#category_tab[compact="true"] { padding: 7px 10px; font-size: 11px; }
QLabel#status { color: #66686f; font-size: 10px; }
QPushButton#primaryAction { background: #f5ce66; color: #1c1912; padding: 10px 16px; border: 1px solid #f5ce66; font-weight: 600; }
QPushButton#primaryAction:hover { background: #ffdc7c; }
QPlainTextEdit#aiQuestion, QTextBrowser#aiAnswer { background: #19191b; border: 1px solid #343437; border-radius: 10px; color: #dedee4; padding: 14px; font-size: 14px; }
QPlainTextEdit#aiQuestion:focus { border-color: #aa9257; }
QLabel#aiQuota { color: #dbc581; font-size: 11px; }
QLabel#aiStatus { color: #91929b; font-size: 11px; }
QPushButton#load_more { color: #bdab7c; padding: 2px 9px; font-size: 10px; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }
QScrollBar::handle:vertical { background: #45433c; border-radius: 2px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #262626; color: #eeeeee; border: 1px solid #66562a; padding: 6px; }
"""

DIALOG_STYLE = """
QDialog { background: transparent; color: #eeeeee; }
QFrame#dialogShell { background: #131313; border: 1px solid #303030; border-radius: 16px; }
QWidget { color: #dedede; }
QLabel { background: transparent; border: none; }
QLabel#dialogBrand { color: #f5ce66; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#dialogHeading { color: #ffffff; font-size: 29px; font-weight: 600; }
QLabel#dialogHint { color: #949494; font-size: 12px; }
QLabel#accountStatus { color: #dccb91; background: #211e14; border: 1px solid #453c22; border-radius: 8px; padding: 12px; }
QPushButton { color: #dedede; background: #1d1d1d; border: 1px solid #303030; border-radius: 8px; padding: 10px 16px; font-weight: 500; }
QPushButton:hover { background: #292929; border-color: #756631; }
QPushButton:pressed { background: #171717; }
QPushButton:disabled { color: #777777; background: #171717; border-color: #2a2a2a; }
QPushButton#primaryAction { background: #f5ce66; color: #131313; border: 1px solid #ffe09c; padding: 12px; font-weight: 600; }
QPushButton#primaryAction:hover { background: #ffe17d; }
QPushButton#primaryAction:disabled { background: #4b4120; color: #aa9b68; border-color: #65562a; }
QPushButton#quietAction { background: transparent; border: none; color: #a5a5a5; padding: 6px 10px; }
QPushButton#quietAction:hover { color: #ffe292; background: #262626; }
QPushButton#chromeClose, QPushButton#chromeMinimize { background: transparent; border: none; border-radius: 6px; padding: 0; color: #949494; font-size: 20px; }
QPushButton#chromeClose:hover { background: #4b2b36; color: #ffb8be; }
QPushButton#chromeMinimize:hover { background: #262626; color: white; }
QLineEdit { background: #171717; color: #f4f4f4; border: 1px solid #303030; border-radius: 8px; padding: 11px 12px; selection-background-color: #75632d; }
QLineEdit:focus { border: 1px solid #f5ce66; background: #1d1c17; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: #1a1a1a; color: #949494; border: none; padding: 10px 15px; margin-right: 4px; border-radius: 7px; }
QTabBar::tab:selected { background: #f5ce66; color: #131313; }
QTabBar::tab:hover { color: #ffe292; }
QTabBar::tab:selected:hover { color: #131313; }
QTabBar::tab:disabled { color: #666666; background: #171717; }
QCheckBox { color: #dedede; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; background: #171717; border: 1px solid #454545; border-radius: 4px; }
QCheckBox::indicator:checked { background: #f5ce66; border: 3px solid #ffe89c; }
QComboBox { color: #eeeeee; background: #171717; border: 1px solid #303030; border-radius: 8px; padding: 9px 12px; }
QComboBox::drop-down { border: none; width: 24px; }
QSlider::groove:horizontal { height: 5px; background: #303030; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #f5ce66; border-radius: 2px; }
QSlider::handle:horizontal { width: 15px; margin: -5px 0; background: #ffe292; border: 1px solid #f5ce66; border-radius: 7px; }
"""


DIALOG_STYLE += """
QFrame#profileCard { background: #1c1c1d; border: 1px solid #343230; border-radius: 12px; }
QLabel#profileAvatar { color: #f5ce66; background: #332d1e; border-radius: 12px; font-size: 26px; font-weight: 700; }
QLabel#profileName { color: #f2f1ec; font-size: 20px; font-weight: 600; }
QLabel#profileVerified { color: #a2bb9f; font-size: 11px; }
"""
