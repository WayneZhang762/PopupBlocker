"""概览页：总开关、核心指标、7 日趋势、最近拦截。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..widgets import (
    ACCENT,
    DANGER,
    SUCCESS,
    TEXT_DIM,
    TEXT_MUTED,
    WARN,
    BarChart,
    Card,
    MetricCard,
    PageHeader,
    ToggleSwitch,
)

ACTION_TEXT = {
    "hide": "隐藏窗口",
    "close": "关闭窗口",
    "click_close": "点关闭按钮",
    "allow": "放行",
}
RESULT_TEXT = {
    "success": "成功",
    "failed": "失败",
    "skipped": "跳过",
    "needs_elevation": "需管理员",
    "observed": "仅记录",
    "": "—",
}


class OverviewPage(QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._build()
        self.refresh()

    # ---------------- 布局 ----------------

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
        root.setContentsMargins(0, 0, 0, 4)
        root.setSpacing(12)

        root.addWidget(PageHeader("概览", "实时监测窗口创建，命中规则就出手"))

        # 总开关卡片
        switch_card = Card(padding=18)
        row = QHBoxLayout()
        row.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(4)
        self.switch_title = QLabel("拦截已关闭")
        self.switch_title.setStyleSheet("font-size:17px; font-weight:600;")
        self.switch_sub = QLabel("观察模式：只记录不拦截，确认规则没问题后再开")
        self.switch_sub.setObjectName("Dim")
        left.addWidget(self.switch_title)
        left.addWidget(self.switch_sub)
        row.addLayout(left, 1)
        self.switch = ToggleSwitch(False)
        self.switch.toggled.connect(self._on_switch)
        row.addWidget(self.switch, 0, Qt.AlignVCenter)
        switch_card.body().addLayout(row)
        root.addWidget(switch_card)

        # 指标卡
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.card_today = MetricCard("今日拦截", "0", "含所有命中动作")
        self.card_week = MetricCard("近 7 天", "0", "累计处理次数")
        self.card_total = MetricCard("累计", "0", "自首次运行起")
        self.card_top = MetricCard("命中最多", "—", "按规则/进程统计")
        for c in (self.card_today, self.card_week, self.card_total, self.card_top):
            metrics.addWidget(c, 1)
        root.addLayout(metrics)

        # 提示条
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            f"background:#2a2418; color:{WARN}; border:1px solid #4a3c1c;"
            "border-radius:8px; padding:9px 12px;"
        )
        self.hint.hide()
        root.addWidget(self.hint)

        # 趋势
        chart_card = Card(padding=14)
        head = QHBoxLayout()
        t = QLabel("近 7 天拦截趋势")
        t.setStyleSheet("font-weight:600;")
        head.addWidget(t)
        head.addStretch(1)
        self.chart_sub = QLabel("")
        self.chart_sub.setObjectName("Muted")
        head.addWidget(self.chart_sub)
        chart_card.body().addLayout(head)
        self.chart = BarChart()
        self.chart.setFixedHeight(96)
        chart_card.body().addWidget(self.chart)
        root.addWidget(chart_card)

        # 最近记录
        recent_card = Card(padding=14)
        rhead = QHBoxLayout()
        rt = QLabel("最近拦截")
        rt.setStyleSheet("font-weight:600;")
        rhead.addWidget(rt)
        rhead.addStretch(1)
        self.recent_count = QLabel("")
        self.recent_count.setObjectName("Muted")
        rhead.addWidget(self.recent_count)
        recent_card.body().addLayout(rhead)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["时间", "进程", "窗口标题", "动作", "结果"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.resizeSection(0, 84)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.resizeSection(1, 128)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.resizeSection(3, 96)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.resizeSection(4, 86)
        self.table.setMinimumHeight(132)
        recent_card.body().addWidget(self.table)
        root.addWidget(recent_card, 1)
        root.addStretch(0)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ---------------- 交互 ----------------

    def _on_switch(self, checked: bool) -> None:
        self.engine.set_mode("block" if checked else "observe")

    def sync_state(self, state: str) -> None:
        blocking = state == "block"
        if self.switch.isChecked() != blocking:
            self.switch.blockSignals(True)
            self.switch.setChecked(blocking)
            self.switch.blockSignals(False)

        if state == "block":
            self.switch_title.setText("拦截已开启")
            self.switch_sub.setText("命中规则的窗口会被隐藏或关闭，不结束任何进程")
        elif state == "paused":
            self.switch_title.setText("拦截已暂停")
            self.switch_sub.setText("临时休息一下，点顶部「恢复拦截」或关闭本页开关再开")
        else:
            self.switch_title.setText("拦截已关闭")
            self.switch_sub.setText("观察模式：只记录不拦截，确认规则没问题后再开")

    # ---------------- 数据刷新 ----------------

    def refresh(self) -> None:
        stats = self.engine.stats
        try:
            today = stats.count_today()
            week = stats.count(7)
            total = stats.total()
        except Exception:
            today = week = total = 0

        self.card_today.set_value(str(today))
        self.card_week.set_value(str(week))
        self.card_total.set_value(str(total))

        tops = []
        try:
            tops = stats.top_rules(1)
        except Exception:
            pass
        if tops and tops[0][1] > 0:
            self.card_top.set_value(str(tops[0][1]), tops[0][0][:12])

        try:
            data = stats.daily_counts(7)
        except Exception:
            data = []
        self.chart.set_data(data)
        week_sum = sum(v for _, v in data)
        self.chart_sub.setText(f"共 {week_sum} 次")

        try:
            rows = stats.recent(8)
        except Exception:
            rows = []
        self._fill_table(rows)
        self.recent_count.setText(f"最近 {len(rows)} 条" if rows else "暂无记录")
        self._update_hint()
        self.sync_state(self.engine.state)

    def _update_hint(self) -> None:
        if self.engine.state == "block":
            self.hint.hide()
            return
        try:
            items = self.engine.stats.suspicious(5)
        except Exception:
            items = []
        if not items:
            self.hint.hide()
            return
        names = "、".join(f"{r['process'] or '未知进程'}({r['c']}次)" for r in items[:3])
        total = sum(r["c"] for r in items)
        self.hint.setText(
            f"发现 {total} 个可疑弹窗只被记录、未被拦截：{names}。"
            "确认为广告后可开启拦截，或到「黑名单」里精确指定。"
        )
        self.hint.show()

    def append_recent(self, record: dict) -> None:
        self._insert_row(record, 0)
        while self.table.rowCount() > 8:
            self.table.removeRow(self.table.rowCount() - 1)

    def _fill_table(self, rows: list[dict]) -> None:
        self.table.setRowCount(0)
        for r in rows:
            self._insert_row(
                {
                    "time": time.strftime("%H:%M:%S", time.localtime(r["ts"])),
                    "process": r.get("process") or "",
                    "title": r.get("title") or "",
                    "action": r.get("action") or "",
                    "result": r.get("result") or "",
                    "mode": r.get("mode") or "",
                },
                self.table.rowCount(),
            )

    def _insert_row(self, record: dict, at: int) -> None:
        self.table.insertRow(at)
        values = [
            record.get("time", ""),
            record.get("process", ""),
            record.get("title", "") or f"[{record.get('class_name','')}]",
            ACTION_TEXT.get(record.get("action", ""), record.get("action", "")),
            RESULT_TEXT.get(record.get("result", ""), record.get("result", "")),
        ]
        for col, text in enumerate(values):
            item = QTableWidgetItem(str(text))
            if col == 0:
                item.setForeground(Qt.gray)
            if col in (3, 4):
                item.setTextAlignment(Qt.AlignCenter)
                if record.get("result") == "success":
                    item.setForeground(QColor(SUCCESS))
                elif record.get("result") == "observed":
                    item.setForeground(QColor(WARN))
                elif record.get("result") in ("failed", "needs_elevation"):
                    item.setForeground(QColor(DANGER))
            if col == 2:
                item.setToolTip(text)
            self.table.setItem(at, col, item)
        self.table.setRowHeight(at, 30)
