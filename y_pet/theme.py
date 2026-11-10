from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QLabel


CHAT_STYLE = """
QLabel { color: #a9bcf2; }
QLabel#channel { color: #93f7ff; font-size: 18px; font-weight: 700; }
QLabel#status { color: #d6b7ff; }
QTextBrowser, QLineEdit {
    background-color: #0c1530;
    color: #eaf2ff;
    border: 1px solid #38578a;
    border-left: 3px solid #55b8df;
    padding: 7px;
    selection-background-color: #6946ab;
}
QLineEdit { placeholder-text-color: #92a5cf; }
QLineEdit:focus, QTextBrowser:focus { border-color: #72e9ff; }
QPushButton {
    background-color: #25346e;
    color: #eefaff;
    border: 1px solid #79eaff;
    border-bottom: 3px solid #a883ff;
    padding: 7px 15px;
    font-weight: 600;
}
QPushButton:hover, QPushButton:focus { background-color: #35478e; }
QPushButton:pressed { background-color: #503c94; }
QPushButton:disabled { color: #8b99c3; border-color: #506390; }
"""


def paint_neon_frame(widget):
    painter = QPainter(widget)
    w, h = widget.width() - 1, widget.height() - 1
    painter.fillRect(widget.rect(), QColor("#080e22"))
    outline = QPolygon([
        QPoint(1, 9), QPoint(5, 9), QPoint(5, 5), QPoint(9, 5), QPoint(9, 1),
        QPoint(w - 9, 1), QPoint(w - 9, 5), QPoint(w - 5, 5),
        QPoint(w - 5, 9), QPoint(w - 1, 9), QPoint(w - 1, h - 9),
        QPoint(w - 5, h - 9), QPoint(w - 5, h - 5), QPoint(w - 9, h - 5),
        QPoint(w - 9, h - 1), QPoint(9, h - 1), QPoint(9, h - 5),
        QPoint(5, h - 5), QPoint(5, h - 9), QPoint(1, h - 9),
    ])
    fill = QLinearGradient(0, 0, w, h)
    fill.setColorAt(0, QColor("#172e56"))
    fill.setColorAt(1, QColor("#20193f"))
    edge = QLinearGradient(0, 0, w, h)
    edge.setColorAt(0, QColor("#69edff"))
    edge.setColorAt(0.53, QColor("#5986e8"))
    edge.setColorAt(1, QColor("#d792ff"))
    painter.setBrush(fill)
    painter.setPen(QPen(edge, 2))
    painter.drawPolygon(outline)
    for x, color in enumerate(("#79edff", "#827fff", "#f29fe8")):
        painter.fillRect(14 + x * 7, 6, 4, 4, QColor(color))
    painter.fillRect(w - 36, h - 7, 23, 3, QColor("#b280ff"))


class ReplyBubble(QLabel):
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setFixedWidth(270)
        self.setMargin(15)
        self.setStyleSheet("color: #edf4ff;")

    def paintEvent(self, event):
        paint_neon_frame(self)
        super().paintEvent(event)
