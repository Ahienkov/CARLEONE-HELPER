import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QDoubleSpinBox
from PySide6.QtTest import QTest
from earnings import EarningsStore
from reselling import ResellingStore, profit
from main import CarleoneWindow
from app_refresh import reload_application


class ResellingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'user.ini')
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.store = ResellingStore(self.settings)
        self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.close()
            self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.directory.cleanup()

    def test_profit_counts_costs_and_unsold_items_have_no_realized_profit(self):
        stock = self.store.add('murrieta', 'Автомобиль', 100000, 5000)
        self.assertIsNone(profit(stock))
        self.store.sell('murrieta', stock['id'], 125000)
        sold = self.store.load('murrieta')[0]
        self.assertEqual(profit(sold), 20000)
        self.assertTrue(sold['sold_at'])
        with self.assertRaises(ValueError):
            self.store.sell('murrieta', stock['id'], 150000)
        loss = self.store.add('murrieta', 'Предмет', 1000, 100, 800)
        self.assertEqual(profit(loss), -300)

    def test_deals_persist_separately_from_old_income_and_other_servers(self):
        income = EarningsStore(self.settings)
        original = income.add('murrieta', 'income', 5000, 'Зарплата')
        self.store.add('murrieta', 'Предмет', 1000, 50, 1500)
        reopened = ResellingStore(QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(profit(reopened.load('murrieta')[0]), 450)
        self.assertEqual(reopened.load('eclipse'), [])
        self.assertEqual(income.load('murrieta'), [original])

    def test_tabs_preserve_income_and_allow_sale_and_deletion(self):
        EarningsStore(self.settings).add('murrieta', 'income', 500, '')
        self.window = CarleoneWindow(initial_mode='earnings', earnings_settings=self.settings)
        workspace = self.window.earnings_panel
        self.assertEqual(workspace.tabs.tabText(0), 'Доходы')
        self.assertEqual(workspace.tabs.tabText(1), 'Перекупство')
        self.assertEqual(workspace.table.rowCount(), 1)
        workspace.tabs.setCurrentIndex(1)
        panel = workspace.reselling
        panel.item.setText('Мотоцикл')
        panel.purchase.setValue(10000)
        panel.costs.setValue(500)
        panel.add_button.click()
        self.assertEqual(panel.table.rowCount(), 1)
        self.assertIn('10 500', panel.in_stock.text())
        panel.table.selectRow(0)
        self.assertTrue(panel.sell_button.isEnabled())
        with patch('reselling.QInputDialog.getDouble', return_value=(15000, True)):
            panel.sell_button.click()
        self.assertIn('4 500', panel.profit.text())
        panel.table.selectRow(0)
        self.assertFalse(panel.sell_button.isEnabled())
        panel.remove_button.click()
        self.assertEqual(panel.table.rowCount(), 0)
        self.assertEqual(workspace.table.rowCount(), 1)

    def test_selected_tab_and_history_survive_environment_switch_and_refresh(self):
        self.store.add('murrieta', 'Предмет', 100, 0, 200)
        self.window = CarleoneWindow(initial_mode='earnings', earnings_settings=self.settings)
        self.window.earnings_panel.tabs.setCurrentIndex(1)
        self.window.mode_selector.setCurrentIndex(0)
        self.window.mode_selector.setCurrentIndex(2)
        self.assertEqual(self.window.earnings_panel.tabs.currentIndex(), 1)
        replacement = reload_application(self.window)
        self.assertIsNotNone(replacement)
        self.window = replacement
        self.assertEqual(replacement.earnings_panel.tabs.currentIndex(), 1)
        self.assertEqual(replacement.earnings_panel.reselling.table.rowCount(), 1)

    def test_invalid_entries_and_corrupt_storage_do_not_overwrite_history(self):
        for item, purchase, costs, sale in (('', 10, 0, None), ('Item', 0, 0, None),
                                            ('Item', 10, -1, None), ('Item', 10, 0, 0)):
            with self.assertRaises(ValueError):
                self.store.add('murrieta', item, purchase, costs, sale)
        raw = '[{"id":"old"}]'
        self.settings.setValue('earnings/reselling/v1/murrieta', raw)
        with self.assertRaises(ValueError):
            self.store.add('murrieta', 'Item', 10)
        self.assertEqual(self.settings.value('earnings/reselling/v1/murrieta'), raw)

    def test_sale_can_be_entered_in_table_with_enter_and_persists(self):
        self.store.add('murrieta', 'Предмет', 1000, 100)
        self.window = CarleoneWindow(initial_mode='earnings', earnings_settings=self.settings)
        self.window.earnings_panel.tabs.setCurrentIndex(1)
        panel = self.window.earnings_panel.reselling
        self.window.show()
        self.app.processEvents()
        cell = panel.table.item(0, 4)
        self.assertTrue(cell.flags() & Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(panel.table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable)
        panel.table.editItem(cell)
        editor = panel.table.findChild(QDoubleSpinBox)
        self.assertIsNotNone(editor)
        editor.setValue(1500)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.app.processEvents()
        reopened = ResellingStore(QSettings(self.path, QSettings.Format.IniFormat))
        self.assertEqual(reopened.load('murrieta')[0]['sale'], 1500)
        self.assertEqual(panel.table.item(0, 6).text(), 'Продано')
        self.assertIn('400', panel.table.item(0, 5).text())
        self.assertIn('400', panel.profit.text())

    def test_editing_existing_sale_preserves_date_and_invalid_zero_preserves_price(self):
        original = self.store.add('murrieta', 'Предмет', 1000, 100, 1500)
        self.window = CarleoneWindow(initial_mode='earnings', earnings_settings=self.settings)
        panel = self.window.earnings_panel.reselling
        panel.table.item(0, 4).setData(Qt.ItemDataRole.EditRole, 1800)
        saved = self.store.load('murrieta')[0]
        self.assertEqual(saved['sale'], 1800)
        self.assertEqual(saved['sold_at'], original['sold_at'])
        panel.table.item(0, 4).setData(Qt.ItemDataRole.EditRole, 0)
        self.assertEqual(self.store.load('murrieta')[0]['sale'], 1800)
        self.assertIn('1 800', panel.table.item(0, 4).text())
        self.assertTrue(panel.error.text())
