"""Per-user resale inventory and completed deals, independent of income entries."""
import json
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import QSettings, Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QHeaderView,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QStyledItemDelegate, QVBoxLayout, QWidget)
from earnings import EarningsStore, money
from i18n import tr


class ResellingStore(EarningsStore):
    def load(self, server):
        try:
            entries = json.loads(self.settings.value(f'earnings/reselling/v1/{server}', '[]', type=str))
            if not isinstance(entries, list):
                raise ValueError()
            seen = set()
            for entry in entries:
                if (not isinstance(entry, dict) or not isinstance(entry.get('id'), str)
                        or not entry['id'] or entry['id'] in seen or not isinstance(entry.get('item'), str)
                        or not entry['item'].strip() or type(entry.get('purchase')) is not int
                        or not 0 < entry['purchase'] <= 10**12 or type(entry.get('costs')) is not int
                        or not 0 <= entry['costs'] <= 10**12
                        or 'sale' not in entry
                        or (entry.get('sale') is not None and (type(entry['sale']) is not int
                                                              or not 0 < entry['sale'] <= 10**12))):
                    raise ValueError()
                datetime.fromisoformat(entry['date'])
                if entry.get('sale') is not None:
                    datetime.fromisoformat(entry['sold_at'])
                seen.add(entry['id'])
            return entries
        except (ValueError, TypeError, KeyError):
            raise ValueError(tr('Не удалось прочитать сделки. Сохранённые данные не изменены.')) from None

    def save(self, server, entries):
        self.settings.setValue(f'earnings/reselling/v1/{server}', json.dumps(entries, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError(tr('Не удалось сохранить записи на этом компьютере.'))

    def add(self, server, item, purchase, costs=0, sale=None):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(tr('Введите название товара.'))
        if (type(purchase) is not int or not 0 < purchase <= 10**12 or type(costs) is not int
                or not 0 <= costs <= 10**12 or (sale is not None and (type(sale) is not int or not 0 < sale <= 10**12))):
            raise ValueError(tr('Укажите цену покупки больше нуля и корректные расходы.'))
        now = datetime.now(timezone.utc).isoformat()
        entry = dict(id=uuid.uuid4().hex, item=item.strip(), purchase=purchase, costs=costs,
                     sale=sale, date=now, sold_at=now if sale is not None else None)
        self.save(server, [*self.load(server), entry])
        return entry

    def sell(self, server, identity, sale):
        self._save_sale(server, identity, sale, only_unsold=True)

    def set_sale_price(self, server, identity, sale):
        self._save_sale(server, identity, sale, only_unsold=False)

    def _save_sale(self, server, identity, sale, only_unsold):
        if type(sale) is not int or not 0 < sale <= 10**12:
            raise ValueError(tr('Введите сумму больше нуля.'))
        entries = self.load(server)
        entry = next((entry for entry in entries if entry['id'] == identity), None)
        if entry is None or (only_unsold and entry['sale'] is not None):
            raise ValueError(tr('Сделка не найдена или товар уже продан.'))
        entry.update(sale=sale, sold_at=entry.get('sold_at') or datetime.now(timezone.utc).isoformat())
        self.save(server, entries)


def profit(entry):
    return None if entry['sale'] is None else entry['sale'] - entry['purchase'] - entry['costs']


class SalePriceDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setDecimals(0)
        editor.setRange(0, 10**12)
        editor.setSuffix(' $')
        editor.setGroupSeparatorShown(True)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        editor.setValue(index.data(Qt.ItemDataRole.UserRole) or 0)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, int(editor.value()), Qt.ItemDataRole.EditRole)


class ResellingPanel(QWidget):
    changed = Signal()

    def __init__(self, store, filter_entries, parent=None):
        super().__init__(parent)
        self.store, self.server, self.filter_entries = store, None, filter_entries
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)
        title = QLabel(tr('Учёт покупок, продаж и прибыли'))
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(title)
        totals = QHBoxLayout()
        self.in_stock, self.revenue, self.profit = QLabel(), QLabel(), QLabel()
        for label in (self.in_stock, self.revenue, self.profit):
            label.setStyleSheet('padding: 8px; background: #1b2229; border-radius: 8px;')
            totals.addWidget(label, 1)
        layout.addLayout(totals)
        form = QHBoxLayout()
        self.item = QLineEdit()
        self.item.setMaxLength(300)
        self.item.setPlaceholderText(tr('Название товара'))
        item_column = QVBoxLayout()
        item_column.addWidget(QLabel(tr('Товар')))
        item_column.addWidget(self.item)
        form.addLayout(item_column, 2)
        for name, label in (('purchase', 'Покупка'), ('costs', 'Доп. расходы'), ('sale', 'Продажа')):
            field = QDoubleSpinBox()
            field.setDecimals(0)
            field.setRange(0, 10**12)
            field.setSuffix(' $')
            field.setGroupSeparatorShown(True)
            field.setAccessibleName(tr(label))
            setattr(self, name, field)
            column = QVBoxLayout()
            column.addWidget(QLabel(tr(label)))
            column.addWidget(field)
            form.addLayout(column, 1)
        self.add_button = QPushButton(tr('Добавить'))
        self.add_button.clicked.connect(self.add_entry)
        form.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(form)
        hint = QLabel(tr('Продажа 0 — товар ещё не продан. Прибыль = продажа − покупка − дополнительные расходы.'))
        hint.setWordWrap(True)
        hint.setStyleSheet('font-size: 12px; color: #a0a8b1;')
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #efaaa1;')
        self.error.hide()
        layout.addWidget(self.error)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([tr(s) for s in ('Дата покупки', 'Товар', 'Покупка', 'Доп. расходы', 'Продажа', 'Прибыль', 'Статус')])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                   QAbstractItemView.EditTrigger.EditKeyPressed |
                                   QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.table.setItemDelegateForColumn(4, SalePriceDelegate(self.table))
        self.table.itemChanged.connect(self.commit_sale_edit)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet('''QTableWidget { background: #14181e; gridline-color: #34404c;
            border: 1px solid #56616c; border-radius: 8px; }
            QTableWidget::item:selected { background: #344c61; }
            QHeaderView::section { background: #242c32; color: #d9dcdf; padding: 8px; border: none; }''')
        layout.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        note = QLabel(tr('Период — по дате покупки. Сделки сохраняются отдельно от вкладки «Доходы».'))
        note.setWordWrap(True)
        note.setStyleSheet('font-size: 12px; color: #a0a8b1;')
        bottom.addWidget(note, 1)
        self.sell_button = QPushButton(tr('Отметить продажу'))
        self.sell_button.clicked.connect(self.sell_entry)
        self.remove_button = QPushButton(tr('Удалить запись'))
        self.remove_button.clicked.connect(self.remove_entry)
        for button in (self.sell_button, self.remove_button):
            button.setEnabled(False)
            bottom.addWidget(button)
        self.table.itemSelectionChanged.connect(self.update_selection)
        layout.addLayout(bottom)

    def set_server(self, server):
        self.server = server
        self.refresh()

    def show_error(self, error):
        self.error.setText(str(error))
        self.error.show()

    def refresh(self):
        if self.server is None:
            return
        try:
            entries = self.filter_entries(self.store.load(self.server))
        except (OSError, ValueError) as error:
            self.show_error(error)
            self.table.setRowCount(0)
            self.add_button.setEnabled(False)
            for label in (self.in_stock, self.revenue, self.profit):
                label.setText('—')
            self.update_selection()
            return
        self.error.hide()
        self.add_button.setEnabled(True)
        self.in_stock.setText(tr('В товаре: {amount}', amount=money(sum(e['purchase'] + e['costs'] for e in entries if e['sale'] is None))))
        self.revenue.setText(tr('Выручка: {amount}', amount=money(sum(e['sale'] for e in entries if e['sale'] is not None))))
        self.profit.setText(tr('Прибыль: {amount}', amount=money(sum(profit(e) for e in entries if e['sale'] is not None))))
        with QSignalBlocker(self.table):
            self.table.setRowCount(0)
            self.table.setRowCount(len(entries))
            for row, entry in enumerate(reversed(entries)):
                values = (datetime.fromisoformat(entry['date']).astimezone().strftime('%d.%m.%Y'), entry['item'],
                          money(entry['purchase']), money(entry['costs']), money(entry['sale']) if entry['sale'] is not None else '—',
                          money(profit(entry)) if profit(entry) is not None else '—', tr('Продано' if entry['sale'] is not None else 'Не продано'))
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    data = entry['id'] if column == 0 else entry['sale'] if column == 4 else entry['sale'] is None
                    cell.setData(Qt.ItemDataRole.UserRole, data)
                    if column != 4:
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    else:
                        cell.setToolTip(tr('Двойной щелчок — ввести или изменить цену продажи.'))
                    self.table.setItem(row, column, cell)
        self.update_selection()

    def commit_sale_edit(self, cell):
        if cell.column() != 4:
            return
        identity = self.table.item(cell.row(), 0).data(Qt.ItemDataRole.UserRole)
        try:
            amount = int(cell.data(Qt.ItemDataRole.EditRole))
            self.store.set_sale_price(self.server, identity, amount)
        except (OSError, TypeError, ValueError) as error:
            self.refresh()
            self.show_error(error)
            return
        self.refresh()
        self.changed.emit()

    def update_selection(self):
        row = self.table.currentRow()
        self.remove_button.setEnabled(row >= 0)
        self.sell_button.setEnabled(row >= 0 and bool(self.table.item(row, 6) and self.table.item(row, 6).data(Qt.ItemDataRole.UserRole)))

    def add_entry(self):
        try:
            self.store.add(self.server, self.item.text(), int(self.purchase.value()), int(self.costs.value()), int(self.sale.value()) or None)
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.item.clear()
        for field in (self.purchase, self.costs, self.sale):
            field.setValue(0)
        self.refresh()
        self.changed.emit()

    def sell_entry(self):
        row = self.table.currentRow()
        if row < 0:
            return
        identity = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        sale, accepted = QInputDialog.getDouble(self, tr('Отметить продажу'), tr('Цена продажи'), 1, 1, 10**12, 0)
        if accepted:
            try:
                self.store.sell(self.server, identity, int(sale))
            except (OSError, ValueError) as error:
                self.show_error(error)
                return
            self.refresh()
            self.changed.emit()

    def remove_entry(self):
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            self.store.remove(self.server, self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.refresh()
        self.changed.emit()
