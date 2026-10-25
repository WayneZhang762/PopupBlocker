"""通用控件与暗色主题。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------- 配色

BG = "#17191d"
SIDEBAR = "#121417"
CARD = "#1f2228"
CARD_HOVER = "#252a31"
BORDER = "#2c313a"
TEXT = "#e8eaed"
TEXT_DIM = "#8b939e"
TEXT_MUTED = "#5f6771"
ACCENT = "#4c8dff"
SUCCESS = "#3fb950"
WARN = "#d29922"
DANGER = "#f85149"


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QWidget#Content {{ background: {BG}; }}

QLabel#AppTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#AppSub {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#PageTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#PageDesc {{ color: {TEXT_DIM}; font-size: 12px; }}
QLabel#Dim {{ color: {TEXT_DIM}; }}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 12px; }}

QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#Card:hover {{ background: {CARD_HOVER}; }}
QFrame#StatusBar {{ background: {SIDEBAR}; border-bottom: 1px solid {BORDER}; }}
QFrame#HLine {{ background: {BORDER}; max-height: 1px; border: none; }}

QPushButton {{
    background: #2a2f37;
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: #333944; }}
QPushButton:pressed {{ background: #262b33; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; background: #22262c; }}
QPushButton#Primary {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: #ffffff; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: #5f9bff; }}
QPushButton#Danger {{ background: transparent; border: 1px solid #5a2b2b; color: {DANGER}; }}
QPushButton#Danger:hover {{ background: #2e1c1c; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {BORDER}; color: {TEXT_DIM}; }}
QPushButton#Ghost:hover {{ color: {TEXT}; border-color: #3d444f; }}

QPushButton#Nav {{
    background: transparent; border: none; border-radius: 8px;
    padding: 10px 12px; text-align: left; color: {TEXT_DIM};
}}
QPushButton#Nav:hover {{ background: #1c1f24; color: {TEXT}; }}
QPushButton#Nav:checked {{ background: #21262e; color: {TEXT}; font-weight: 600; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background: #15181c; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 9px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: #1b1e23; border: 1px solid {BORDER}; selection-background-color: #2b3a52;
}}
QComboBox QAbstractItemView::item {{ padding: 6px; }}

QTableWidget {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 9px;
    gridline-color: #262b33; selection-background-color: #26303f;
    selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QHeaderView::section {{
    background: #1a1d22; color: {TEXT_DIM}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: #1a1d22; border: none; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; top: -1px; background: {CARD}; }}
QTabBar::tab {{
    background: transparent; color: {TEXT_DIM}; padding: 8px 18px; margin-right: 4px;
    border: 1px solid transparent; border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{ background: {CARD}; color: {TEXT}; border-color: {BORDER}; border-bottom-color: {CARD}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #414852; background: #15181c;
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: none; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333944; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #414a57; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #333944; border-radius: 5px; min-width: 30px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QWidget#Content {{ background: transparent; }}

QMenu {{
    background: #1b1e23; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: #2a3140; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}

QMessageBox {{ background: {BG}; }}
QToolTip {{
    background: #22262d; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 5px 8px;
}}
"""


# ---------------------------------------------------------------- 控件

def add_shadow(widget: QWidget, blur: int = 24, dy: int = 6, alpha: int = 90) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, padding: int = 16) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(10)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, w: QWidget) -> None:
        self._layout.addWidget(w)


class MetricCard(Card):
    def __init__(self, title: str, value: str = "0", hint: str = "", parent=None) -> None:
        super().__init__(parent, padding=14)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("Dim")
        self.value_label = QLabel(value)
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        self.value_label.setFont(f)
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("Muted")
        self._layout.addWidget(self.title_label)
        self._layout.addWidget(self.value_label)
        self._layout.addWidget(self.hint_label)
        self._layout.addStretch(1)
        self.setMinimumHeight(88)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)


class StatusDot(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = QColor(TEXT_MUTED)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(1, 1, 8, 8)
        p.end()


class BarChart(QWidget):
    """7 日拦截量柱状图，纯自绘，不引入 QtCharts。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if not self._data:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(rect, Qt.AlignCenter, "暂无数据")
            p.end()
            return

        pad_l, pad_r, pad_t, pad_b = 8, 8, 18, 26
        w = rect.width() - pad_l - pad_r
        h = rect.height() - pad_t - pad_b
        n = len(self._data)
        gap = 10
        bar_w = max(6, (w - gap * (n - 1)) / n)
        peak = max((v for _, v in self._data), default=0) or 1

        font = p.font()
        font.setPointSize(8)
        p.setFont(font)

        for i, (day, value) in enumerate(self._data):
            x = pad_l + i * (bar_w + gap)
            bh = 0 if peak == 0 else max(2, value / peak * (h - 16))
            top = pad_t + (h - bh)
            path = QPainterPath()
            radius = min(5.0, bar_w / 2)
            path.addRoundedRect(QRectF(x, top, bar_w, max(bh, 2)), radius, radius)
            color = QColor(ACCENT if value else "#2e343d")
            if i == n - 1 and value:
                color = QColor("#79a9ff")
            p.fillPath(path, color)

            p.setPen(QColor(TEXT_DIM))
            label = day[5:]  # MM-DD
            p.drawText(QRectF(x - 8, rect.height() - pad_b + 4, bar_w + 16, 18),
                       Qt.AlignCenter, label)
            if value:
                p.setPen(QColor(TEXT))
                p.drawText(QRectF(x - 8, top - 17, bar_w + 16, 14), Qt.AlignCenter, str(value))
        p.end()


class HLine(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HLine")
        self.setFixedHeight(1)


class PageHeader(QWidget):
    def __init__(self, title: str, desc: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("PageDesc")
            lay.addWidget(d)


class ToggleSwitch(QWidget):
    """自绘开关，比 QCheckBox 更像"总闸"。"""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._anim = 0.0
        self.setFixedSize(52, 28)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        if self._checked == bool(value):
            return
        self._checked = bool(value)
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        bg = QColor(SUCCESS if self._checked else "#3a4048")
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        knob = 22.0
        x = r.width() - knob - 3 if self._checked else 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, knob, knob))
        p.end()


def stat_label(text: str, object_name: str = "Muted") -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(object_name)
    return lb


def hbox(*widgets, spacing: int = 8, margins: tuple = (0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w)
    return lay
