import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QLabel

from rules_data import load_rules, split_rule_punishment
from main import CarleoneWindow


class RulePunishmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_split_keeps_notes_and_examples(self):
        text = '1.1 Запрещено | Деморган от 30 минут\nПримечание: условие\nПример: действие'
        body, sanction = split_rule_punishment(text)
        self.assertEqual(body, '1.1 Запрещено\nПримечание: условие\nПример: действие')
        self.assertEqual(sanction, 'Деморган от 30 минут')
        self.assertEqual(split_rule_punishment(body, sanction), (body, sanction))

    def test_inline_note_is_not_moved_to_sanction(self):
        body, sanction = split_rule_punishment('1.1 Запрещено |-10 баллов Примечание: исключение')
        self.assertEqual(body, '1.1 Запрещено\nПримечание: исключение')
        self.assertEqual(sanction, '-10 баллов')

    def test_nonpunishment_pipes_are_untouched(self):
        for text in ('Ammunation | Поезда', 'Форт Занкудо | SASPA', 'Цена | 2.500.000$',
                     '"/try взломал замок | Неудачно."', 'Условие | Разрешается штурм'):
            self.assertEqual(split_rule_punishment(text), (text, ''))

    def test_multiple_sanctions_retain_their_conditions(self):
        body, sanction = split_rule_punishment('1.1 Первое действие | Деморган 30 минут\nВторое действие | Warn')
        self.assertEqual(body, '1.1 Первое действие\nВторое действие')
        self.assertIn('1.1 Первое действие\nДеморган 30 минут', sanction)
        self.assertIn('Второе действие\nWarn', sanction)

    def test_loaded_rule_card_has_copyable_punishment_and_raw_text(self):
        rule = next(r for r in load_rules('murrieta') if r['number'] == '6.1.1' and r['topic_id'] == '3237321')
        self.assertIn('|', rule['source_text'])
        self.assertNotIn('|', rule['description'])
        self.assertEqual(rule['punishment'], 'Предупреждение/Деморган от 30 минут')
        w = CarleoneWindow()
        card = w.create_article_card(rule)
        try:
            label = card.findChild(QLabel, 'criminal_punishment')
            self.assertIsNotNone(label)
            self.assertEqual(label.text(), rule['punishment'])
            self.assertIn('Пример:', card.findChild(QLabel, 'description').text())
        finally:
            card.deleteLater()
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
