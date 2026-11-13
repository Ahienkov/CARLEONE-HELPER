"""Small vector icons drawn with Qt; independent of Windows symbol fonts."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
import math


def line_icon(name, size=20):
    icon = QIcon()
    for color, mode, state in (('#929497', QIcon.Mode.Normal, QIcon.State.Off),
                                ('#f5ce66', QIcon.Mode.Normal, QIcon.State.On),
                                ('#f5f5f5', QIcon.Mode.Active, QIcon.State.Off)):
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(size / 24, size / 24)
        pen = QPen(QColor(color), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        if name == 'ai':
            p.drawPolygon(QPolygonF([QPointF(13,3),QPointF(15,9),QPointF(21,11),QPointF(15,13),QPointF(13,19),QPointF(11,13),QPointF(5,11),QPointF(11,9)]))
            p.drawLine(4,3,4,7)
            p.drawLine(2,5,6,5)
        elif name == 'laws':
            p.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
            p.drawLine(9, 3, 9, 21)
            p.drawLine(12, 8, 16, 8)
            p.drawLine(12, 12, 16, 12)
        elif name == 'rules':
            p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 6), QPointF(19, 15), QPointF(12, 21), QPointF(5, 15), QPointF(4, 6)]))
            p.drawLine(8, 11, 11, 14)
            p.drawLine(11, 14, 16, 9)
        elif name == 'earnings':
            p.drawLine(4, 20, 21, 20)
            for x, h in [(7, 6), (12, 11), (17, 16)]:
                p.drawRoundedRect(QRectF(x, 20-h, 2, h), .5, .5)
        elif name == 'notepad':
            p.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
            for y in [8, 12, 16]:
                p.drawLine(9, y, 15, y)
        elif name == 'settings':
            for y, x in [(6, 8), (12, 16), (18, 10)]:
                p.drawLine(4, y, x-2, y)
                p.drawLine(x+2, y, 20, y)
                p.drawEllipse(QPointF(x, y), 2, 2)
        elif name == 'refresh':
            p.drawArc(QRectF(5, 5, 14, 14), 40*16, 290*16)
            p.drawPolyline(QPolygonF([QPointF(18, 4), QPointF(19, 9), QPointF(14, 8)]))
        elif name == 'search':
            p.drawEllipse(QRectF(4, 4, 12, 12))
            p.drawLine(15, 15, 21, 21)
        elif name == 'close':
            p.drawLine(7, 7, 17, 17)
            p.drawLine(17, 7, 7, 17)
        elif name == 'minimize':
            p.drawLine(6, 15, 18, 15)
        elif name == 'maximize':
            p.drawRoundedRect(QRectF(6, 6, 12, 12), 1.5, 1.5)
        elif name == 'favorite':
            points = [QPointF(12+9*math.cos(-math.pi/2+i*math.pi/5)*(1 if i%2==0 else .44),
                             12+9*math.sin(-math.pi/2+i*math.pi/5)*(1 if i%2==0 else .44)) for i in range(10)]
            p.drawPolygon(QPolygonF(points))
        elif name == 'suspect':
            p.drawRoundedRect(QRectF(5, 4, 14, 17), 2, 2)
            for y in [9, 13, 17]:
                p.drawLine(9, y, 15, y)
        p.end()
        icon.addPixmap(pixmap, mode, state)
    return icon
