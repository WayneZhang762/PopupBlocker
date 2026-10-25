"""拦截记录页：全量流水、筛选、导出。"""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..widgets import ACCENT, DANGER, SUCCESS, TEXT_DIM, WARN, Card, PageHeader

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
RANGE_OPTIONS = [("今天", 1), ("近 7 天", 7), ("近 30 天", 30), ("全部", 0)]

COLUMNS = ["时间", "进程", "窗口标题", "动作", "结果", "命中规则"]


class DetailDialog(QDialog):
    def __init__(self, record: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("记录详情")
        self.resize(560, 380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        ts = record.get("ts")
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "—"
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "\n".join(
                [
                    f"时间：{when}",
                    f"进程：{record.get('process') or '—'}  (PID {record.get('pid')})",
                    f"路径：{record.get('exe_path') or '—'}",
                    f"窗口类名：{record.get('class_name') or '—'}",
                    f"窗口标题：{record.get('title') or '（无标题）'}",
                    f"动作：{ACTION_TEXT.get(record.get('action',''), record.get('action',''))}",
                    f"结果：{RESULT_TEXT.get(record.get('result',''), record.get('result',''))}",
                    f"模式：{'拦截' if record.get('mode') == 'block' else '观察'}",
                    f"命中规则：{record.get('rule_name') or '—'}  ({record.get('rule_id') or '—'})",
                    f"可疑评分：{record.get('score', 0)}",
                ]
            )
        )
        lay.addWidget(text)

        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("关闭")
        btn.clicked.connect(self.accept)
        row.addWidget(btn)
        lay.addLayout(row)
        btn.setDefault(True)


class RecordsPage(QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._rows: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(PageHeader("拦截记录", "每一次判定都留痕，方便回溯和调规则"))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.range_box = QComboBox()
        for label, days in RANGE_OPTIONS:
            self.range_box.addItem(label, days)
        self.range_box.setCurrentIndex(1)
        self.range_box.currentIndexChanged.connect(self.reload)
        toolbar.addWidget(self.range_box)

        self.process_box = QComboBox()
        self.process_box.addItem("全部进程", "")
        self.process_box.currentIndexChanged.connect(self.reload)
        toolbar.addWidget(self.process_box)

        self.action_box = QComboBox()
        self.action_box.addItem("全部动作", "")
        for key, label in ACTION_TEXT.items():
            if key != "allow":
                self.action_box.addItem(label, key)
        self.action_box.currentIndexChanged.connect(self.reload)
        toolbar.addWidget(self.action_box)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索窗口标题 / 进程 / 类名")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload)
        toolbar.addWidget(self.search, 1)

        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("Ghost")
        export_btn.clicked.connect(self.export_csv)
        toolbar.addWidget(export_btn)

        clear_btn = QPushButton("清空记录")
        clear_btn.setObjectName("Danger")
        clear_btn.clicked.connect(self.clear_all)
        toolbar.addWidget(clear_btn)
        root.addLayout(toolbar)

        card = Card(padding=10)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.doubleClicked.connect(self._show_detail)
        hh = self.table.horizontalHeader()
        widths = [(0, 140), (1, 142), (3, 96), (4, 84), (5, 140)]
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for col, w in widths:
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            hh.resizeSection(col, w)
        card.body().addWidget(self.table)
        root.addWidget(card, 1)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

    # ---------------- 数据 ----------------

    def refresh(self) -> None:
        self._refresh_process_box()
        self.reload()

    def _refresh_process_box(self) -> None:
        current = self.process_box.currentData()
        try:
            rows = self.engine.stats.query(limit=2000)
        except Exception:
            rows = self._rows
        names = sorted({(r.get("process") or "") for r in rows if r.get("process")})
        self.process_box.blockSignals(True)
        self.process_box.clear()
        self.process_box.addItem("全部进程", "")
        for name in names:
            self.process_box.addItem(name, name)
        idx = self.process_box.findData(current)
        self.process_box.setCurrentIndex(max(0, idx))
        self.process_box.blockSignals(False)

    def reload(self) -> None:
        days = self.range_box.currentData() or 0
        process = self.process_box.currentData() or ""
        action = self.action_box.currentData() or ""
        keyword = self.search.text().strip()
        try:
            rows = self.engine.stats.query(
                days=0 if days is None else int(days),
                process=process,
                action=action,
                keyword=keyword,
                limit=800,
            )
        except Exception:
            rows = []
        self._rows = rows
        self._fill(rows)
        self.status.setText(f"共 {len(rows)} 条记录（最多显示 800 条）")

    def _fill(self, rows: list[dict]) -> None:
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            when = time.strftime("%m-%d %H:%M:%S", time.localtime(r["ts"])) if r.get("ts") else ""
            values = [
                when,
                r.get("process") or "",
                r.get("title") or f"[{r.get('class_name','')}]",
                ACTION_TEXT.get(r.get("action", ""), r.get("action", "")),
                RESULT_TEXT.get(r.get("result", ""), r.get("result", "")),
                r.get("rule_name") or "",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignCenter)
                    if r.get("result") == "success":
                        item.setForeground(QColor(SUCCESS))
                    elif r.get("result") == "observed":
                        item.setForeground(QColor(WARN))
                    elif r.get("result") in ("failed", "needs_elevation"):
                        item.setForeground(QColor(DANGER))
                elif col == 0:
                    item.setForeground(QColor(TEXT_DIM))
                if col in (2, 5):
                    item.setToolTip(str(text))
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 30)

    def _show_detail(self) -> None:
        idx = self.table.currentRow()
        if 0 <= idx < len(self._rows):
            DetailDialog(self._rows[idx], self).exec()

    # ---------------- 操作 ----------------

    def export_csv(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "导出", "当前筛选条件下没有记录")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出拦截记录", f"拦截记录_{time.strftime('%Y%m%d_%H%M')}.csv",
            "CSV 文件 (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "进程", "PID", "窗口标题", "类名", "动作", "结果", "规则", "模式"])
                for r in self._rows:
                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])),
                        r.get("process", ""), r.get("pid", ""), r.get("title", ""),
                        r.get("class_name", ""),
                        ACTION_TEXT.get(r.get("action", ""), r.get("action", "")),
                        RESULT_TEXT.get(r.get("result", ""), r.get("result", "")),
                        r.get("rule_name", ""),
                        "拦截" if r.get("mode") == "block" else "观察",
                    ])
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出完成", f"已保存到：\n{path}")

    def clear_all(self) -> None:
        ret = QMessageBox.question(
            self, "清空记录",
            "将删除全部拦截记录和统计数据，且无法恢复。确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.engine.stats.clear()
            self.refresh()
