"""图标绘制：不依赖外部图片文件，全部用 QPainter 现画。

好处是打包时不用带 ico/png，且托盘图标能按状态实时变色。
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .widgets import ACCENT, DANGER, SUCCESS, WARN

STATE_COLORS = {
    "block": SUCCESS,
    "observe": WARN,
    "paused": "#6b7280",
}


def _draw(size: int, bg: str, badge: bool = False, flat: bool = False) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)

    # 底板：圆角方块 + 竖向渐变，暗色托盘里也醒目
    body = QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.92)
    grad = QLinearGradient(QPointF(0, 0), QPointF(0, s))
    base = QColor(bg)
    grad.setColorAt(0.0, base.lighter(115))
    grad.setColorAt(1.0, base.darker(115))
    path = QPainterPath()
    path.addRoundedRect(body, s * 0.24, s * 0.24)
    if flat:
        p.fillPath(path, base)
    else:
        p.fillPath(path, grad)

    # 中间画一个"窗口"轮廓 + 斜杠 = 被拦下的弹窗
    w = s * 0.52
    h = s * 0.40
    x = (s - w) / 2
    y = (s - h) / 2 - s * 0.02
    pen = QPen(QColor(255, 255, 255, 235))
    pen.setWidthF(max(1.2, s * 0.075))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    win = QRectF(x, y, w, h)
    p.drawRoundedRect(win, s * 0.08, s * 0.08)
    # 标题栏
    p.drawLine(QPointF(x, y + h * 0.3), QPointF(x + w, y + h * 0.3))
    # 斜杠
    p.drawLine(QPointF(x - s * 0.02, y + h + s * 0.08),
               QPointF(x + w + s * 0.02, y - s * 0.05))

    if badge:
        r = s * 0.22
        p.setPen(QPen(QColor("#12141a"), max(1.0, s * 0.04)))
        p.setBrush(QColor(DANGER))
        p.drawEllipse(QRectF(s - r - s * 0.02, s * 0.02, r, r))

    p.end()
    return pm


def tray_icon(state: str = "block", has_events: bool = False) -> QIcon:
    color = STATE_COLORS.get(state, ACCENT)
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(_draw(size, color, badge=has_events and state == "block"))
    return icon


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_draw(size, ACCENT))
    return icon


def write_ico(path: str, size: int = 256) -> bool:
    """给 PyInstaller 生成 .ico（多尺寸写进一个文件由 Qt 处理）。"""
    img: QImage = _draw(size, ACCENT).toImage()
    return bool(img.save(path, "ICO"))
