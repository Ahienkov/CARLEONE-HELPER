"""Presentation widgets that keep the existing ledger data and accessibility."""
from i18n import tr
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QTableWidget


class MetricLabel(QLabel):
    def __init__(self, color='#f5ce66', parent=None):
        super().__init__(parent)
        self.value_color = color
        self.setMinimumHeight(92)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#303031'), 1))
        p.setBrush(QColor('#1b1b1c'))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)
        caption, _, value = self.text().partition(':')
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(QColor('#85868d'))
        p.drawText(self.rect().adjusted(18, 14, -18, -54), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, caption)
        font.setPixelSize(25)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(self.value_color))
        p.drawText(self.rect().adjusted(18, 35, -18, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value.strip() or '—')
        p.end()


class LedgerTable(QTableWidget):
    empty_title = 'Пока нет операций'
    empty_description = 'Добавьте первую запись — здесь появится история ваших финансов.'

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount():
            return
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.viewport().width()/2, self.viewport().height()/2 - 26
        p.setPen(QPen(QColor('#514a38'), 1.5))
        p.setBrush(QColor('#24221d'))
        p.drawRoundedRect(QRectF(cx-23, cy-39, 46, 46), 13, 13)
        for y, width in [(cy-25, 18), (cy-17, 13), (cy-9, 16)]:
            p.drawLine(int(cx-9), int(y), int(cx-9+width), int(y))
        font = QFont(self.font())
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor('#ceccd0'))
        p.drawText(QRectF(10, cy+24, self.viewport().width()-20, 26), Qt.AlignmentFlag.AlignCenter, tr(self.empty_title))
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor('#73757d'))
        p.drawText(QRectF(20, cy+54, self.viewport().width()-40, 40), Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, tr(self.empty_description))
        p.end()
