"""系统托盘：图标状态、右键菜单、拦截气泡。"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..config import APP_NAME, VERSION, is_admin, settings
from ..core import autostart
from .icons import tray_icon


class Tray(QObject):
    def __init__(self, engine, window) -> None:
        super().__init__(window)
        self.engine = engine
        self.window = window
        self._recent: list[dict] = []

        self.icon = QSystemTrayIcon(self)
        self.icon.setToolTip(f"{APP_NAME} {VERSION}")
        self.icon.activated.connect(self._on_activated)

        self.menu = QMenu()
        self.status_action = QAction("状态：初始化", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()

        self.act_toggle = QAction("暂停拦截", self.menu)
        self.act_toggle.triggered.connect(self._toggle_pause)
        self.menu.addAction(self.act_toggle)

        self.act_open = QAction("打开主界面", self.menu)
        self.act_open.triggered.connect(self.open_window)
        self.menu.addAction(self.act_open)

        self.recent_menu = QMenu("最近拦截", self.menu)
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self.menu.addMenu(self.recent_menu)

        self.menu.addSeparator()

        self.act_autostart = QAction("开机自动启动", self.menu)
        self.act_autostart.setCheckable(True)
        self.act_autostart.toggled.connect(self._toggle_autostart)
        self.menu.addAction(self.act_autostart)

        self.menu.addSeparator()
        self.act_quit = QAction("退出", self.menu)
        self.act_quit.triggered.connect(self._quit)
        self.menu.addAction(self.act_quit)

        self.icon.setContextMenu(self.menu)
        self.icon.show()

        engine.stateChanged.connect(self.refresh)
        engine.statsChanged.connect(self.refresh)
        engine.windowEvent.connect(self.on_event)
        self.refresh(engine.state)

    # ---------------- 状态 ----------------

    def refresh(self, _state: str = "") -> None:
        state = self.engine.state
        try:
            today = self.engine.stats.count_today()
        except Exception:
            today = 0
        label = {"block": "拦截中", "observe": "观察模式", "paused": "已暂停"}.get(state, state)
        self.icon.setIcon(tray_icon(state, has_events=today > 0))
        self.icon.setToolTip(f"{APP_NAME} · {label} · 今日 {today} 次")
        self.status_action.setText(f"{label} · 今日拦截 {today} 次")
        self.act_toggle.setText("恢复拦截" if state == "paused" else "暂停拦截")
        self.act_autostart.blockSignals(True)
        self.act_autostart.setChecked(autostart.is_enabled())
        self.act_autostart.blockSignals(False)

    # ---------------- 菜单动作 ----------------

    def _toggle_pause(self) -> None:
        self.engine.set_paused(self.engine.state != "paused")

    def open_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _toggle_autostart(self, checked: bool) -> None:
        autostart.sync(checked)
        settings.set("autostart", checked)

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        try:
            rows = self.engine.stats.recent(6)
        except Exception:
            rows = []
        if not rows:
            act = QAction("暂无记录", self.recent_menu)
            act.setEnabled(False)
            self.recent_menu.addAction(act)
            return
        for r in rows:
            when = time.strftime("%H:%M", time.localtime(r["ts"]))
            title = (r.get("title") or r.get("class_name") or "")[:22]
            act = QAction(f"{when}  {r.get('process','')}  {title}", self.recent_menu)
            act.triggered.connect(self.open_window)
            self.recent_menu.addAction(act)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_window()

    def _quit(self) -> None:
        self.engine.stop()
        self.icon.hide()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    # ---------------- 通知 ----------------

    def on_event(self, record: dict) -> None:
        if not settings.get("notify_on_block"):
            return
        if record.get("mode") != "block" or record.get("result") != "success":
            return
        proc = record.get("process") or "未知进程"
        title = (record.get("title") or record.get("class_name") or "")[:24]
        self.icon.showMessage(
            f"{APP_NAME} 已拦截",
            f"{proc}\n{title}",
            QSystemTrayIcon.Information,
            2500,
        )
