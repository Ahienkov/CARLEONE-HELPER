import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, QDate, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app_refresh import reload_application
from earnings import EarningsStore
from main import CarleoneWindow
from dark_combo import DarkComboBox


class EarningsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'user.ini')
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.store = EarningsStore(self.settings)
        self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.close()
            self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.directory.cleanup()

    def open_window(self):
        self.window = CarleoneWindow(earnings_settings=self.settings)
        self.window.mode_selector.setCurrentIndex(2)
        return self.window.earnings_panel

    def test_history_persists_in_user_settings_and_is_separate_per_server(self):
        income = self.store.add('murrieta', 'income', 5000, 'Работа')
        self.store.add('murrieta', 'expense', 800, 'Топливо')
        other = EarningsStore(QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(len(other.load('murrieta')), 2)
        self.assertEqual(other.load('eclipse'), [])
        other.remove('murrieta', income['id'])
        self.assertEqual([e['amount'] for e in self.store.load('murrieta')], [800])

    def test_dropdown_and_separate_environment_preserve_history_on_return(self):
        panel = self.open_window()
        w = self.window
        self.assertIsInstance(w.mode_selector, DarkComboBox)
        self.assertEqual([w.mode_selector.itemData(i) for i in range(3)], ['laws', 'rules', 'earnings'])
        self.assertIsNone(w.environments['laws'].records)
        self.assertIsNone(w.environments['rules'].records)
        self.assertEqual(w.search_index, {})
        panel.amount.setValue(7500)
        panel.description.setText('Зарплата')
        panel.add_button.click()
        panel.kind.setCurrentIndex(1)
        panel.amount.setValue(1500)
        panel.add_button.click()
        self.assertEqual(panel.table.rowCount(), 2)
        self.assertIn('6 000', panel.balance.text())
        w.mode_selector.setCurrentIndex(0)
        self.assertIsNone(w.earnings_panel)
        w.mode_selector.setCurrentIndex(2)
        self.assertEqual(w.earnings_panel.table.rowCount(), 2)
        w.earnings_panel.table.selectRow(0)
        w.earnings_panel.remove_button.click()
        self.assertEqual(w.earnings_panel.table.rowCount(), 1)

    def test_date_filters_and_totals_include_older_days_and_months(self):
        now = datetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0)
        entries = [dict(id=str(days), kind=kind, amount=amount, description='',
                        date=(now - timedelta(days=days)).astimezone(timezone.utc).isoformat())
                   for days, kind, amount in ((0, 'income', 100), (4, 'expense', 20),
                                               (20, 'income', 300), (60, 'expense', 40))]
        self.store.save('murrieta', entries)
        panel = self.open_window()
        self.assertEqual(panel.table.rowCount(), 4)
        self.assertIn('340', panel.balance.text())
        panel.period.setCurrentIndex(panel.period.findData('week'))
        self.assertEqual(panel.table.rowCount(), 2)
        self.assertIn('80', panel.balance.text())
        panel.period.setCurrentIndex(panel.period.findData('month30'))
        self.assertEqual(panel.table.rowCount(), 3)
        self.assertIn('380', panel.balance.text())
        panel.period.setCurrentIndex(panel.period.findData('custom'))
        panel.date_from.setDate(QDate.currentDate().addDays(-70))
        panel.date_to.setDate(QDate.currentDate().addDays(-50))
        self.assertEqual(panel.table.rowCount(), 1)
        self.assertIn('-40', panel.balance.text())
        self.assertEqual(len(self.store.load('murrieta')), 4)

    def test_refresh_and_reopen_keep_history_and_filter_without_loading_laws(self):
        self.store.add('murrieta', 'income', 1500, '')
        panel = self.open_window()
        panel.period.setCurrentIndex(panel.period.findData('month'))
        replacement = reload_application(self.window)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.mode, 'earnings')
        self.assertEqual(replacement.earnings_panel.period.currentData(), 'month')
        self.assertEqual(replacement.earnings_panel.table.rowCount(), 1)
        self.assertIsNone(replacement.environments['laws'].records)
        replacement.close()
        replacement.deleteLater()
        self.window = CarleoneWindow(initial_mode='earnings', earnings_settings=QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(self.window.earnings_panel.table.rowCount(), 1)

    def test_invalid_amount_and_damaged_history_are_not_overwritten(self):
        with self.assertRaises(ValueError):
            self.store.add('murrieta', 'income', 0, '')
        raw = '{invalid history'
        self.settings.setValue('earnings/v1/murrieta', raw)
        panel = self.open_window()
        self.assertFalse(panel.add_button.isEnabled())
        with self.assertRaises(ValueError):
            self.store.add('murrieta', 'income', 10, '')
        self.assertEqual(self.settings.value('earnings/v1/murrieta'), raw)

    def test_overall_summary_updates_from_both_tabs_and_inline_sale_edits(self):
        self.store.add('murrieta', 'income', 1000, '')
        self.store.add('murrieta', 'expense', 200, '')
        workspace = self.open_window()
        trade = workspace.reselling
        trade.item.setText('Предмет')
        trade.purchase.setValue(500)
        trade.costs.setValue(50)
        trade.add_button.click()
        self.assertIn('1 000', workspace.total_income.text())
        self.assertIn('750', workspace.total_expense.text())
        self.assertIn('250', workspace.total_balance.text())
        from PySide6.QtCore import Qt
        trade.table.item(0, 4).setData(Qt.ItemDataRole.EditRole, 800)
        self.assertIn('1 800', workspace.total_income.text())
        self.assertIn('1 050', workspace.total_balance.text())
        trade.table.selectRow(0)
        trade.remove_button.click()
        self.assertIn('1 000', workspace.total_income.text())
        self.assertIn('200', workspace.total_expense.text())
        self.assertIn('800', workspace.total_balance.text())
        workspace.amount.setValue(100)
        workspace.kind.setCurrentIndex(1)
        workspace.add_button.click()
        self.assertIn('300', workspace.total_expense.text())
        self.assertIn('700', workspace.total_balance.text())

    def test_overall_period_uses_purchase_and_sale_dates_separately(self):
        from reselling import ResellingStore
        trade_store = ResellingStore(self.settings)
        deal = trade_store.add('murrieta', 'Старый товар', 1000, 100, 1500)
        deal['date'] = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        trade_store.save('murrieta', [deal])
        workspace = self.open_window()
        workspace.period.setCurrentIndex(workspace.period.findData('today'))
        self.assertIn('1 500', workspace.total_income.text())
        self.assertEqual(workspace.total_expense.text(), 'Расходы: 0 $')
        workspace.period.setCurrentIndex(workspace.period.findData('all'))
        self.assertIn('1 100', workspace.total_expense.text())
        self.assertIn('400', workspace.total_balance.text())
        self.window.server.setCurrentIndex(self.window.server.findData('eclipse'))
        self.assertEqual(workspace.total_income.text(), 'Доходы: 0 $')
        self.assertEqual(workspace.total_expense.text(), 'Расходы: 0 $')

    def test_overall_summary_does_not_show_partial_total_for_corrupt_deals(self):
        self.store.add('murrieta', 'income', 500, '')
        self.settings.setValue('earnings/reselling/v1/murrieta', '{invalid')
        workspace = self.open_window()
        self.assertIn('—', workspace.total_balance.text())
        self.assertIn('не изменены', workspace.summary_bar.toolTip())
