"""Local per-server income and expense journal, outside application updates."""
import json
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import QSettings, Qt, QDate
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDoubleSpinBox, QFrame, QHeaderView, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
from dark_combo import DarkComboBox
from i18n import tr


class EarningsStore:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings('CARLEONE', 'HELPER')

    def load(self, server):
        try:
            entries = json.loads(self.settings.value(f'earnings/v1/{server}', '[]', type=str))
            if not isinstance(entries, list):
                raise ValueError()
            identities = set()
            for entry in entries:
                if (not isinstance(entry, dict) or entry.get('kind') not in ('income', 'expense')
                        or type(entry.get('amount')) is not int or not 0 < entry['amount'] <= 10**12
                        or not isinstance(entry.get('description'), str)
                        or not isinstance(entry.get('id'), str) or not entry['id'] or entry['id'] in identities):
                    raise ValueError()
                datetime.fromisoformat(entry['date'])
                identities.add(entry['id'])
            return entries
        except (ValueError, TypeError, KeyError):
            raise ValueError(tr('Не удалось прочитать записи. Сохранённые данные не изменены.')) from None

    def save(self, server, entries):
        self.settings.setValue(f'earnings/v1/{server}', json.dumps(entries, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError(tr('Не удалось сохранить записи на этом компьютере.'))

    def add(self, server, kind, amount, description):
        if kind not in ('income', 'expense') or type(amount) is not int or not 0 < amount <= 10**12:
            raise ValueError(tr('Введите сумму больше нуля.'))
        entry = dict(id=uuid.uuid4().hex, kind=kind, amount=amount, description=description.strip(),
                     date=datetime.now(timezone.utc).isoformat())
        self.save(server, [*self.load(server), entry])
        return entry

    def remove(self, server, identity):
        entries = self.load(server)
        self.save(server, [entry for entry in entries if entry['id'] != identity])


def money(amount):
    return f'{amount:,}'.replace(',', ' ') + ' $'


def resale_cash_entries(deals):
    """Purchases/costs and sales affect cash on their own transaction dates."""
    for deal in deals:
        yield {'kind': 'expense', 'amount': deal['purchase'] + deal['costs'], 'date': deal['date']}
        if deal['sale'] is not None:
            yield {'kind': 'income', 'amount': deal['sale'], 'date': deal['sold_at']}


class EarningsPanel(QWidget):
    def __init__(self, store, parent=None, view=None):
        super().__init__(parent)
        self.store, self.server = store, None
        self.setStyleSheet('''
            QDoubleSpinBox, QDateEdit { background: #14181e; color: #e5e7eb;
                border: 1px solid #56616c; border-radius: 8px; padding: 6px; }
            QLineEdit { padding: 7px 10px; font-size: 15px; }
            QComboBox { padding: 6px 10px; }
            QCalendarWidget QWidget { background: #1b2229; color: #d9dcdf; }
            QCalendarWidget QAbstractItemView { background: #14181e; color: #d9dcdf;
                selection-background-color: #344c61; }
        ''')
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(6)
        self.summary_bar = QFrame()
        self.summary_bar.setObjectName('overall_summary')
        self.summary_bar.setStyleSheet('QFrame#overall_summary { background: #1b2229; border-radius: 8px; }')
        summary = QHBoxLayout(self.summary_bar)
        summary.setContentsMargins(10, 8, 10, 8)
        summary_title = QLabel(tr('Общий итог'))
        summary_title.setStyleSheet('font-weight: bold;')
        summary.addWidget(summary_title)
        self.total_income, self.total_expense, self.total_balance = QLabel(), QLabel(), QLabel()
        for label in (self.total_income, self.total_expense, self.total_balance):
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            summary.addWidget(label, 1)
        self.root_layout.addWidget(self.summary_bar)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet('''
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: #171d23; color: #a0a8b1; padding: 6px 16px;
                border: 1px solid #34404c; border-radius: 6px; margin-right: 6px; }
            QTabBar::tab:selected { background: #344c61; color: #f1f4f7; }
        ''')
        self.income_tab = QWidget()
        self.tabs.addTab(self.income_tab, tr('Доходы'))
        self.root_layout.addWidget(self.tabs, 1)
        layout = QVBoxLayout(self.income_tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)
        title = QLabel(tr('Учёт доходов и расходов'))
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(title)
        totals = QHBoxLayout()
        self.income, self.expense, self.balance = QLabel(), QLabel(), QLabel()
        for label in (self.income, self.expense, self.balance):
            label.setStyleSheet('padding: 8px; background: #1b2229; border-radius: 8px;')
            totals.addWidget(label, 1)
        layout.addLayout(totals)
        periods = QHBoxLayout()
        self.period = DarkComboBox()
        for label, value in (('За всё время', 'all'), ('Сегодня', 'today'), ('За 7 дней', 'week'),
                             ('За 30 дней', 'month30'), ('Текущий месяц', 'month'), ('Выбрать даты', 'custom')):
            self.period.addItem(tr(label), value)
        self.period.setAccessibleName(tr('Период'))
        self.date_from = QDateEdit(QDate.currentDate().addDays(1 - QDate.currentDate().day()))
        self.date_to = QDateEdit(QDate.currentDate())
        for field, label in ((self.date_from, 'Дата начала'), (self.date_to, 'Дата окончания')):
            field.setCalendarPopup(True)
            field.setDisplayFormat('dd.MM.yyyy')
            field.setAccessibleName(tr(label))
        saved = view or {}
        index = self.period.findData(saved.get('period', 'all'))
        self.period.setCurrentIndex(max(0, index))
        for field, key in ((self.date_from, 'from'), (self.date_to, 'to')):
            date = QDate.fromString(saved.get(key, ''), Qt.DateFormat.ISODate)
            if date.isValid():
                field.setDate(date)
        periods.addWidget(self.period)
        periods.addWidget(self.date_from)
        periods.addWidget(self.date_to)
        periods.setContentsMargins(0, 1, 0, 0)
        self.period_bar = QWidget()
        self.period_bar.setLayout(periods)
        self.tabs.setCornerWidget(self.period_bar, Qt.Corner.TopRightCorner)
        row_height = max(self.tabs.tabBar().sizeHint().height(), self.period.sizeHint().height(),
                         self.date_from.sizeHint().height(), self.date_to.sizeHint().height())
        self.tabs.tabBar().setFixedHeight(row_height)
        self.period_bar.setFixedHeight(row_height + 1)
        for field in (self.period, self.date_from, self.date_to):
            field.setFixedHeight(row_height)
        custom = self.period.currentData() == 'custom'
        self.date_from.setVisible(custom)
        self.date_to.setVisible(custom)
        form = QHBoxLayout()
        self.kind = DarkComboBox()
        self.kind.addItem(tr('Доход'), 'income')
        self.kind.addItem(tr('Расход'), 'expense')
        self.kind.setAccessibleName(tr('Тип операции'))
        self.amount = QDoubleSpinBox()
        self.amount.setDecimals(0)
        self.amount.setRange(0, 10**12)
        self.amount.setSuffix(' $')
        self.amount.setGroupSeparatorShown(True)
        self.amount.setAccessibleName(tr('Сумма'))
        self.description = QLineEdit()
        self.description.setPlaceholderText(tr('Комментарий (необязательно)'))
        self.description.setMaxLength(500)
        self.add_button = QPushButton(tr('Добавить'))
        self.add_button.clicked.connect(self.add_entry)
        form.addWidget(self.kind)
        form.addWidget(self.amount)
        form.addWidget(self.description, 1)
        form.addWidget(self.add_button)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #efaaa1;')
        self.error.hide()
        layout.addWidget(self.error)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr('Дата'), tr('Тип операции'), tr('Комментарий'), tr('Сумма')])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet('''
            QTableWidget { background: #14181e; alternate-background-color: #1b2229;
                gridline-color: #34404c; border: 1px solid #56616c; border-radius: 8px; }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background: #344c61; }
            QHeaderView::section { background: #242c32; color: #d9dcdf; padding: 10px;
                border: none; border-bottom: 1px solid #56616c; }
            QDoubleSpinBox { background: #14181e; padding: 8px; }
        ''')
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        hint = QLabel(tr('Записи сохраняются только на этом компьютере, отдельно для каждого сервера.'))
        hint.setWordWrap(True)
        hint.setStyleSheet('font-size: 12px; color: #a0a8b1;')
        bottom.addWidget(hint, 1)
        self.remove_button = QPushButton(tr('Удалить запись'))
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.remove_entry)
        self.table.itemSelectionChanged.connect(lambda: self.remove_button.setEnabled(self.table.currentRow() >= 0))
        bottom.addWidget(self.remove_button)
        layout.addLayout(bottom)
        from reselling import ResellingPanel, ResellingStore
        self.reselling = ResellingPanel(ResellingStore(store.settings), self.filter_entries)
        self.reselling.changed.connect(self.update_overall_summary)
        self.tabs.addTab(self.reselling, tr('Перекупство'))
        self.tabs.setCurrentIndex(1 if saved.get('tab') == 'reselling' else 0)
        self.period.currentIndexChanged.connect(self.change_period)
        self.date_from.dateChanged.connect(self.refresh)
        self.date_to.dateChanged.connect(self.refresh)

    def export_view(self):
        return {'period': self.period.currentData(),
                'tab': 'reselling' if self.tabs.currentIndex() == 1 else 'income',
                'from': self.date_from.date().toString(Qt.DateFormat.ISODate),
                'to': self.date_to.date().toString(Qt.DateFormat.ISODate)}

    def change_period(self):
        custom = self.period.currentData() == 'custom'
        self.date_from.setVisible(custom)
        self.date_to.setVisible(custom)
        self.refresh()

    def filter_entries(self, entries):
        period = self.period.currentData()
        if period == 'all':
            return entries
        end = QDate.currentDate()
        start = {'today': end, 'week': end.addDays(-6), 'month30': end.addDays(-29),
                 'month': end.addDays(1 - end.day())}.get(period, self.date_from.date())
        if period == 'custom':
            end = self.date_to.date()
        if start > end:
            raise ValueError(tr('Дата начала должна быть не позже даты окончания.'))
        result = []
        for entry in entries:
            date = datetime.fromisoformat(entry['date']).astimezone().date()
            if start.toPython() <= date <= end.toPython():
                result.append(entry)
        return result

    def set_server(self, server):
        if self.server != server:
            self.server = server
            self.reselling.set_server(server)
            self.refresh()

    def refresh(self, *_args):
        self.update_overall_summary()
        self.reselling.refresh()
        try:
            entries = self.filter_entries(self.store.load(self.server))
        except (OSError, ValueError) as error:
            self.show_error(error)
            self.table.setRowCount(0)
            self.income.setText(tr('Доходы: {amount}', amount='—'))
            self.expense.setText(tr('Расходы: {amount}', amount='—'))
            self.balance.setText(tr('Баланс: {amount}', amount='—'))
            self.add_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return
        self.add_button.setEnabled(True)
        self.error.hide()
        incoming = sum(e['amount'] for e in entries if e['kind'] == 'income')
        outgoing = sum(e['amount'] for e in entries if e['kind'] == 'expense')
        self.income.setText(tr('Доходы: {amount}', amount=money(incoming)))
        self.expense.setText(tr('Расходы: {amount}', amount=money(outgoing)))
        self.balance.setText(tr('Баланс: {amount}', amount=money(incoming - outgoing)))
        self.table.setRowCount(0)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(reversed(entries)):
            values = (datetime.fromisoformat(entry['date']).astimezone().strftime('%d.%m.%Y %H:%M'),
                      tr('Доход' if entry['kind'] == 'income' else 'Расход'), entry['description'],
                      ('+' if entry['kind'] == 'income' else '−') + money(entry['amount']))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entry['id'])
                self.table.setItem(row, column, item)
        self.remove_button.setEnabled(False)

    def update_overall_summary(self):
        if self.server is None:
            return
        try:
            entries = self.filter_entries([*self.store.load(self.server),
                                          *resale_cash_entries(self.reselling.store.load(self.server))])
        except (OSError, ValueError) as error:
            self.total_income.setText(tr('Доходы: {amount}', amount='—'))
            self.total_expense.setText(tr('Расходы: {amount}', amount='—'))
            self.total_balance.setText(tr('Баланс: {amount}', amount='—'))
            self.summary_bar.setToolTip(str(error))
            return
        incoming = sum(entry['amount'] for entry in entries if entry['kind'] == 'income')
        outgoing = sum(entry['amount'] for entry in entries if entry['kind'] == 'expense')
        self.total_income.setText(tr('Доходы: {amount}', amount=money(incoming)))
        self.total_expense.setText(tr('Расходы: {amount}', amount=money(outgoing)))
        self.total_balance.setText(tr('Баланс: {amount}', amount=money(incoming - outgoing)))
        self.summary_bar.setToolTip(tr('Обе вкладки, выбранный сервер и период. Покупки, расходы и продажи учитываются по датам операций.'))

    def show_error(self, error):
        self.error.setText(str(error))
        self.error.show()

    def add_entry(self):
        try:
            self.store.add(self.server, self.kind.currentData(), int(self.amount.value()), self.description.text())
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.amount.setValue(0)
        self.description.clear()
        self.refresh()

    def remove_entry(self):
        row = self.table.currentRow()
        if row < 0:
            return
        identity = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            self.store.remove(self.server, identity)
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.refresh()
