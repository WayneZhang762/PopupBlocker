"""设置页：引擎模式、启动、托盘、记录保留、权限。"""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config import APP_NAME, DATA_DIR, LOG_DIR, VERSION, is_admin, settings
from ...core import autostart
from ..widgets import ACCENT, DANGER, TEXT_DIM, TEXT_MUTED, WARN, Card, HLine, PageHeader


def _section(title: str, desc: str = "") -> Card:
    card = Card(padding=16)
    head = QVBoxLayout()
    head.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet("font-weight:600; font-size:14px;")
    head.addWidget(t)
    if desc:
        d = QLabel(desc)
        d.setObjectName("Muted")
        d.setWordWrap(True)
        head.addWidget(d)
    card.body().addLayout(head)
    return card


class SettingsPage(QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Content")
        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(12)
        root.addWidget(PageHeader("设置", "改完立即生效，不需要重启"))

        # 引擎
        card = _section("拦截引擎", "决定命中规则后是真动手，还是只记一笔")
        form = QFormLayout()
        form.setSpacing(10)
        self.mode_box = QComboBox()
        self.mode_box.addItem("实际拦截（推荐）", "block")
        self.mode_box.addItem("观察模式（只记录）", "observe")
        self.mode_box.currentIndexChanged.connect(self._on_mode)
        form.addRow("运行模式", self.mode_box)

        self.cb_smart = QCheckBox("智能拦截：允许启发式判定直接隐藏可疑弹窗")
        self.cb_smart.toggled.connect(self._on_smart)
        form.addRow("", self.cb_smart)
        card.body().addLayout(form)

        warn = QLabel("智能拦截不看规则、只看窗口特征，误伤概率比规则高。建议先用观察模式跑几天，再决定要不要开。")
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color:{WARN};")
        card.body().addWidget(warn)
        root.addWidget(card)

        # 启动与托盘
        card2 = _section("启动与托盘")
        form2 = QFormLayout()
        form2.setSpacing(10)
        self.cb_autostart = QCheckBox("开机自动启动（写入当前用户的启动项）")
        self.cb_autostart.toggled.connect(self._on_autostart)
        form2.addRow("", self.cb_autostart)
        self.cb_startmin = QCheckBox("启动时直接最小化到托盘")
        self.cb_startmin.toggled.connect(lambda v: self._set("start_minimized", v))
        form2.addRow("", self.cb_startmin)
        self.cb_tray = QCheckBox("点击关闭按钮时最小化到托盘，而不是退出")
        self.cb_tray.toggled.connect(lambda v: self._set("minimize_to_tray", v))
        form2.addRow("", self.cb_tray)
        card2.body().addLayout(form2)
        root.addWidget(card2)

        # 记录
        card3 = _section("记录与提示")
        form3 = QFormLayout()
        form3.setSpacing(10)
        self.cb_notify = QCheckBox("拦截时在右下角弹一条气泡提示")
        self.cb_notify.toggled.connect(lambda v: self._set("notify_on_block", v))
        form3.addRow("", self.cb_notify)
        self.spin_days = QSpinBox()
        self.spin_days.setRange(1, 365)
        self.spin_days.setSuffix(" 天")
        self.spin_days.valueChanged.connect(self._on_days)
        form3.addRow("记录保留", self.spin_days)
        card3.body().addLayout(form3)
        root.addWidget(card3)

        # 系统
        card4 = _section("系统与排查")
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_dir = QPushButton("打开数据目录")
        btn_dir.setObjectName("Ghost")
        btn_dir.clicked.connect(lambda: os.startfile(str(DATA_DIR)))
        row.addWidget(btn_dir)

        btn_log = QPushButton("打开日志")
        btn_log.setObjectName("Ghost")
        btn_log.clicked.connect(lambda: os.startfile(str(LOG_DIR)))
        row.addWidget(btn_log)

        self.btn_admin = QPushButton("以管理员身份重启")
        self.btn_admin.clicked.connect(self._restart_admin)
        if is_admin():
            self.btn_admin.setText("已是管理员权限")
            self.btn_admin.setEnabled(False)
        row.addWidget(self.btn_admin)
        row.addStretch(1)
        card4.body().addLayout(row)

        perm = QLabel(
            "普通权限即可拦截绝大多数软件弹窗。少数以管理员运行的软件（如安全卫士），"
            "需要以管理员身份重启本程序才能关掉它们的窗口。"
        )
        perm.setObjectName("Muted")
        perm.setWordWrap(True)
        card4.body().addWidget(perm)
        root.addWidget(card4)

        root.addStretch(1)

        about = QLabel(
            f"{APP_NAME} v{VERSION}  ·  进程外窗口钩子 + 规则判定，不注入、不驱动、不结束进程"
        )
        about.setObjectName("Muted")
        about.setAlignment(Qt.AlignCenter)
        root.addWidget(about)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ---------------- 交互 ----------------

    def _set(self, key: str, value) -> None:
        settings.set(key, value)

    def _on_mode(self, _index: int) -> None:
        mode = self.mode_box.currentData()
        if mode:
            self.engine.set_mode(mode)

    def _on_smart(self, checked: bool) -> None:
        settings.set("smart_block", checked)
        self.engine.reload_config()

    def _on_autostart(self, checked: bool) -> None:
        if not autostart.sync(checked):
            QMessageBox.warning(self, "设置失败", "写入开机启动项失败，可能被杀毒软件拦截。")
            self.cb_autostart.blockSignals(True)
            self.cb_autostart.setChecked(not checked)
            self.cb_autostart.blockSignals(False)
            return
        settings.set("autostart", checked)

    def _on_days(self, value: int) -> None:
        settings.set("retention_days", value)
        try:
            self.engine.stats.purge(value)
        except Exception:
            pass

    def _restart_admin(self) -> None:
        if is_admin():
            QMessageBox.information(self, "权限", "当前已是管理员权限。")
            return
        try:
            if getattr(sys, "frozen", False):
                exe = sys.executable
                params = ""
            else:
                exe = sys.executable
                params = f'"{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "main.py")}"'
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
            if ret > 32:
                QMessageBox.information(self, "已请求提权", "新的管理员实例正在启动，本窗口可以关闭了。")
                self.engine.stop()
                os._exit(0)
            else:
                QMessageBox.warning(self, "提权失败", "用户取消了 UAC 授权。")
        except Exception as exc:
            QMessageBox.warning(self, "提权失败", str(exc))

    # ---------------- 刷新 ----------------

    def refresh(self) -> None:
        mode = settings.get("engine_mode")
        idx = self.mode_box.findData(mode)
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentIndex(max(0, idx))
        self.mode_box.blockSignals(False)

        for cb, key in (
            (self.cb_smart, "smart_block"),
            (self.cb_startmin, "start_minimized"),
            (self.cb_tray, "minimize_to_tray"),
            (self.cb_notify, "notify_on_block"),
        ):
            cb.blockSignals(True)
            cb.setChecked(bool(settings.get(key)))
            cb.blockSignals(False)

        self.cb_autostart.blockSignals(True)
        self.cb_autostart.setChecked(autostart.is_enabled())
        self.cb_autostart.blockSignals(False)

        self.spin_days.blockSignals(True)
        self.spin_days.setValue(int(settings.get("retention_days") or 30))
        self.spin_days.blockSignals(False)
