"""测试弹窗生成器：造几种典型广告弹窗，用来验证拦截是否生效。

它是一个独立进程，所以不会被主程序的"自身进程白名单"放过。
"""
from __future__ import annotations

import random
import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ADS = [
    ("限时优惠 立即领取", "恭喜获得 8 折优惠券\n点击立即使用"),
    ("今日推荐 热点资讯", "3 条你可能感兴趣的内容"),
    ("福利活动 抽奖进行中", "100% 中奖，先到先得"),
    ("游戏中心 新服开启", "注册即送豪华礼包"),
    ("广告 · 猜你喜欢", "根据你的浏览记录推荐"),
]


class FakePopup(QWidget):
    """模拟一个典型的右下角广告弹窗。"""

    def __init__(self, title: str, body: str, *, stubborn: bool = False,
                 with_close_button: bool = False, tool: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(title)
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if tool:
            flags |= Qt.Tool
        flags |= Qt.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(280, 170)
        self._stubborn = stubborn
        self._body = body

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        t = QLabel(title)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        t.setFont(f)
        t.setStyleSheet("color:#1a1a1a;")
        lay.addWidget(t)

        b = QLabel(body)
        b.setStyleSheet("color:#444;")
        b.setWordWrap(True)
        lay.addWidget(b)
        lay.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        if with_close_button:
            btn = QPushButton("关闭")
            btn.setObjectName("FakeClose")
            btn.clicked.connect(self.close)
            row.addWidget(btn)
        else:
            fake = QLabel("点击查看详情 →")
            fake.setStyleSheet("color:#0a66ff;")
            row.addWidget(fake)
        lay.addLayout(row)

        # 放到屏幕右下角
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - random.randint(10, 90)
        y = screen.bottom() - self.height() - random.randint(40, 160)
        self.move(QPoint(x, y))

        if stubborn:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._respawn)
            self._timer.start(2500)

    def _respawn(self) -> None:
        self.show()
        self.raise_()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.fillRect(0, 0, self.width(), 4, QColor("#ff5a5f"))
        p.setPen(QColor("#e3e3e3"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class Panel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("测试弹窗生成器 - 静窗")
        self.resize(430, 330)
        self._popups: list[FakePopup] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(9)

        tip = QLabel(
            "点下面的按钮造一个假弹窗。\n"
            "如果静窗开着拦截，这个窗口应该会立刻消失或一闪就没。\n"
            "如果静窗是观察模式，它会留在屏幕上，并在概览页记一笔。"
        )
        tip.setWordWrap(True)
        lay.addWidget(tip)

        buttons = [
            ("普通广告小窗（带广告词）", lambda: self.spawn(stubborn=False)),
            ("顽固弹窗（被关掉会反复重开）", lambda: self.spawn(stubborn=True)),
            ("带「关闭」按钮的对话框", lambda: self.spawn(with_close_button=True)),
            ("无标题小窗", lambda: self.spawn(untitled=True)),
            ("一次弹 5 个", self.spawn_many),
        ]
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(34)
            btn.clicked.connect(handler)
            lay.addWidget(btn)

        lay.addStretch(1)
        self.status = QLabel("等你的弹窗")
        self.status.setStyleSheet("color:#777;")
        lay.addWidget(self.status)

    def spawn(self, *, stubborn: bool = False, with_close_button: bool = False,
              untitled: bool = False) -> None:
        title, body = random.choice(ADS)
        if untitled:
            title = ""
            body = "无标题弹窗，只能靠窗口特征识别"
        popup = FakePopup(title, body, stubborn=stubborn, with_close_button=with_close_button)
        if stubborn:
            self._popups.append(popup)  # 保住引用，否则被 GC
        popup.show()
        self.status.setText(f"已弹出：{title or '（无标题）'}")

    def spawn_many(self) -> None:
        for i in range(5):
            QTimer.singleShot(i * 450, self.spawn)


def main() -> int:
    app = QApplication(sys.argv)
    panel = Panel()
    panel.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
