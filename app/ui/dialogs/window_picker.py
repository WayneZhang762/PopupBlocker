"""十字准星拾窗器：点哪个窗口，就把它填进规则/名单。

踩过的坑（别再改回去）：
1. 窗口标志不能用 Qt.Tool —— ToolWindow 不参与正常激活链，拿不到键盘焦点，
   表现就是"按 Esc 没反应"。这里用 Qt.Dialog + 无边框 + 置顶。
2. hide() 之后必须给 Windows 一点时间真正处理隐藏，否则 WindowFromPoint
   取到的还是遮罩自己，表现是"点了一下没反应"。
3. 悬停预览不要做 —— 遮罩盖在最上层，探到的永远是它自己，显示的是假信息。
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QApplication, QDialog

import win32gui

from ...core import window_probe
from ...core.keyhook import EscapeHook
from ..widgets import ACCENT, TEXT

# 取窗失败时的重试间隔（秒）：先短后长，等窗口管理器处理完隐藏
RETRY_DELAYS = (0.06, 0.14)


class _EscBridge(QObject):
    """钩子线程 -> GUI 线程的桥。跨线程 emit 会自动排队，不会碰坏控件。"""

    escaped = Signal()


class WindowPicker(QDialog):
    """全屏半透明遮罩，鼠标变准星，点一下就返回窗口特征。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)
        self.hwnd: int = 0
        self.feat: dict | None = None
        self._finished = False

        # 焦点不可靠时用全局 Esc 钩子兜底
        self._bridge = _EscBridge()
        self._bridge.escaped.connect(self._cancel, Qt.QueuedConnection)
        self._esc_hook = EscapeHook(self._bridge.escaped.emit)

        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())

    # ---------------- 焦点处理（Esc 能收到键的前提） ----------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)
        self.grabKeyboard()
        self._esc_hook.start()

    def hideEvent(self, event) -> None:
        self._esc_hook.stop()
        self.releaseKeyboard()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._esc_hook.stop()
        self.releaseKeyboard()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            event.accept()
            self._cancel()
            return
        super().keyPressEvent(event)

    def event(self, event) -> bool:
        # 双通道：个别情况下按键不会走到 keyPressEvent
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self._cancel()
            return True
        return super().event(event)

    def _cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.reject()

    # ---------------- 绘制 ----------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 14, 20, 170))
        p.setRenderHint(QPainter.Antialiasing)

        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(TEXT))
        p.drawText(self.rect().adjusted(0, -70, 0, -70), Qt.AlignCenter,
                   "点击要抓取的窗口")

        small = QFont()
        small.setPointSize(10)
        p.setFont(small)
        p.setPen(QColor("#a8b0bb"))
        p.drawText(self.rect().adjusted(0, 26, 0, 26), Qt.AlignCenter,
                   "右键或 Esc 取消")
        p.setPen(QColor("#7b8390"))
        p.drawText(self.rect().adjusted(0, 52, 0, 52), Qt.AlignCenter,
                   "会依次填入：进程名 · 窗口类名 · 标题")

        # 中心十字准星，一眼看出现在是拾取状态
        cx, cy = self.rect().center().x(), self.rect().center().y()
        p.setPen(QColor(ACCENT))
        p.drawLine(cx - 14, cy, cx - 4, cy)
        p.drawLine(cx + 4, cy, cx + 14, cy)
        p.drawLine(cx, cy - 14, cx, cy - 4)
        p.drawLine(cx, cy + 4, cx, cy + 14)
        p.end()

    # ---------------- 鼠标 ----------------

    def mouseReleaseEvent(self, event) -> None:
        if self._finished:
            return
        if event.button() == Qt.RightButton:
            self._cancel()
            return
        if event.button() != Qt.LeftButton:
            return

        pos = event.position().toPoint()
        self.hide()
        QApplication.processEvents()

        feat = self._grab(pos)
        if feat:
            self._finished = True
            self.feat = feat
            self.hwnd = feat.get("hwnd", 0)
            self.accept()
        else:
            self._cancel()

    def _grab(self, pos: QPoint) -> dict | None:
        """隐藏遮罩后取窗口：给系统一点时间，并排除自己进程。"""
        for delay in RETRY_DELAYS:
            time.sleep(delay)
            QApplication.processEvents()
            feat = self._probe_at(pos)
            if feat and feat.get("pid") != os.getpid():
                return feat
        return None

    def _probe_at(self, pos: QPoint) -> dict | None:
        try:
            hwnd = win32gui.WindowFromPoint((pos.x(), pos.y()))
            if not hwnd:
                return None
            root = win32gui.GetAncestor(hwnd, window_probe.GA_ROOT)
            if not root:
                return None
            return window_probe.probe(root)
        except Exception:
            return None


def pick_window(parent=None) -> dict | None:
    dlg = WindowPicker(parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.feat
    return None
