"""主窗口：左侧导航 + 顶部状态条 + 五个页面。"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_NAME, VERSION, is_admin, settings
from .pages.lists_page import ListsPage
from .pages.overview import OverviewPage
from .pages.records import RecordsPage
from .pages.rules_page import RulesPage
from .pages.settings_page import SettingsPage
from .widgets import ACCENT, BORDER, SIDEBAR, SUCCESS, TEXT_DIM, WARN, StatusDot
from .icons import app_icon

log = logging.getLogger(__name__)

NAV_ITEMS = [
    ("overview", "概览"),
    ("records", "拦截记录"),
    ("rules", "规则管理"),
    ("lists", "黑白名单"),
    ("settings", "设置"),
]


class MainWindow(QMainWindow):
    closedToTray = Signal()

    def __init__(self, engine) -> None:
        super().__init__()
        self.engine = engine
        self._force_quit = False
        self.setWindowTitle(f"{APP_NAME}  {VERSION}")
        self.setWindowIcon(app_icon())
        self.resize(1020, 720)
        self.setMinimumSize(920, 680)

        root = QWidget()
        root.setObjectName("Content")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_statusbar())

        self.stack = QStackedWidget()
        content_wrap = QWidget()
        wrap_layout = QVBoxLayout(content_wrap)
        wrap_layout.setContentsMargins(22, 18, 22, 18)
        wrap_layout.addWidget(self.stack)
        right_layout.addWidget(content_wrap, 1)
        outer.addWidget(right, 1)

        self.pages = {
            "overview": OverviewPage(engine, self),
            "records": RecordsPage(engine, self),
            "rules": RulesPage(engine, self),
            "lists": ListsPage(engine, self),
            "settings": SettingsPage(engine, self),
        }
        for key, _ in NAV_ITEMS:
            self.stack.addWidget(self.pages[key])

        engine.stateChanged.connect(self._on_state_changed)
        engine.statsChanged.connect(self._on_stats_changed)
        engine.windowEvent.connect(self._on_window_event)

        self._select("overview")
        self._on_state_changed(engine.state)
        self._on_stats_changed()

    # ---------------- 侧边栏 ----------------

    def _build_sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(178)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(4)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        title.setContentsMargins(8, 0, 0, 0)
        sub = QLabel("Windows 弹窗拦截")
        sub.setObjectName("AppSub")
        sub.setContentsMargins(8, 0, 0, 0)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(16)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._select(k))
            self.nav_group.addButton(btn)
            lay.addWidget(btn)
            self._nav_buttons[key] = btn

        lay.addStretch(1)

        tip = QLabel("关闭窗口＝最小化到托盘")
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        tip.setContentsMargins(8, 0, 8, 6)
        lay.addWidget(tip)

        ver = QLabel(f"v{VERSION}" + ("  ·  管理员" if is_admin() else "  ·  普通权限"))
        ver.setObjectName("Muted")
        ver.setContentsMargins(8, 0, 0, 0)
        lay.addWidget(ver)
        return bar

    def _build_statusbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(46)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(22, 0, 18, 0)
        lay.setSpacing(8)

        self.dot = StatusDot()
        self.state_label = QLabel("初始化…")
        f = QFont()
        f.setBold(True)
        self.state_label.setFont(f)
        lay.addWidget(self.dot)
        lay.addWidget(self.state_label)
        lay.addSpacing(12)

        self.today_label = QLabel("今日拦截 0 次")
        self.today_label.setObjectName("Dim")
        lay.addWidget(self.today_label)
        lay.addStretch(1)

        self.quick_btn = QPushButton("暂停拦截")
        self.quick_btn.setObjectName("Ghost")
        self.quick_btn.setCursor(Qt.PointingHandCursor)
        self.quick_btn.clicked.connect(self._toggle_pause)
        lay.addWidget(self.quick_btn)
        return bar

    # ---------------- 交互 ----------------

    def _select(self, key: str) -> None:
        mapping = {k: i for i, (k, _) in enumerate(NAV_ITEMS)}
        self.stack.setCurrentIndex(mapping[key])
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        page = self.pages.get(key)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()

    def _toggle_pause(self) -> None:
        paused = self.engine.state != "paused"
        self.engine.set_paused(paused)

    def _on_state_changed(self, state: str) -> None:
        text = {"block": "拦截中", "observe": "观察模式", "paused": "已暂停"}.get(state, state)
        color = {"block": SUCCESS, "observe": WARN, "paused": "#6b7280"}.get(state, TEXT_DIM)
        self.state_label.setText(text)
        self.dot.set_color(color)
        self.quick_btn.setText("恢复拦截" if state == "paused" else "暂停拦截")
        page = self.pages.get("overview")
        if page is not None:
            page.sync_state(state)
        self.refresh_tray()

    def _on_stats_changed(self) -> None:
        try:
            today = self.engine.stats.count_today()
        except Exception:
            today = 0
        self.today_label.setText(f"今日拦截 {today} 次")
        self.refresh_tray()

    def _on_window_event(self, record: dict) -> None:
        page = self.pages.get("overview")
        if page is not None and self.stack.currentIndex() == 0:
            page.append_recent(record)

    def refresh_tray(self) -> None:
        win = self.window()
        callback = getattr(self, "tray_refresh", None)
        if callable(callback):
            callback()

    # ---------------- 关窗行为 ----------------

    def closeEvent(self, event) -> None:
        if self._force_quit or not settings.get("minimize_to_tray"):
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.closedToTray.emit()

    def ask_quit(self) -> None:
        self._force_quit = True
        self.close()
