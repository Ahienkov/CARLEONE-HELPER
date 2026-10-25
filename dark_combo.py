"""Dark popup backgrounds, including the margins outside the list view."""
from PySide6.QtCore import QSize, Qt, QPoint, QRectF
from PySide6.QtGui import QColor, QPalette, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import QComboBox, QListView, QStyledItemDelegate, QStyle, QStyleOptionViewItem


class ComboItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        self.initStyleOption(option, index)
        return QSize(option.fontMetrics.horizontalAdvance(option.text) + 32,
                     max(36, option.fontMetrics.height() + 14))

    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#344c61' if selected else '#283743'))
            painter.drawRoundedRect(option.rect.adjusted(4, 2, -4, -2), 6, 6)
        painter.setFont(option.font)
        painter.setPen(QColor('#f1f4f7' if selected else '#d9e0e7'))
        text_rect = option.rect.adjusted(14, 0, -14, 0)
        text = option.fontMetrics.elidedText(option.text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        painter.restore()


class DarkComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QListView(self))
        self.setItemDelegate(ComboItemDelegate(self.view()))
        self.setMaxVisibleItems(12)
        self.view().setUniformItemSizes(True)
        self.view().setMouseTracking(True)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view().setStyleSheet('''
            QListView {
                background-color: #1b2229;
                color: #d9e0e7;
                border: 1px solid #56616c;
                border-radius: 9px;
                padding: 4px 0px;
                outline: none;
            }
        ''')
        popup = self.view().window()
        popup.setObjectName('combo_popup')
        palette = popup.palette()
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
            palette.setColor(role, QColor('#1b2229'))
        palette.setColor(QPalette.ColorRole.WindowText, QColor('#e0e4e8'))
        popup.setPalette(palette)
        popup.setAutoFillBackground(True)
        popup.setStyleSheet('QFrame#combo_popup { background-color: #1b2229; border: none; }')

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        if popup.layout() is not None:
            popup.layout().setContentsMargins(0, 0, 0, 0)
            popup.layout().setSpacing(0)
        popup.setFixedWidth(self.width())
        origin = self.mapToGlobal(QPoint(0, self.height() + 3))
        available = self.screen().availableGeometry()
        x = max(available.left(), min(origin.x(), available.right() - popup.width() + 1))
        y = origin.y()
        if y + popup.height() > available.bottom() + 1:
            y = self.mapToGlobal(QPoint(0, -popup.height() - 3)).y()
        popup.move(x, max(available.top(), y))
        # The native popup container otherwise paints a rectangular background
        # outside the list view's rounded border, and offsets the selected row.
        rounded = QPainterPath()
        rounded.addRoundedRect(QRectF(popup.rect()), 9, 9)
        popup.setMask(QRegion(rounded.toFillPolygon().toPolygon()))
