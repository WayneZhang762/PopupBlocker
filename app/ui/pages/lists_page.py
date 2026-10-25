"""黑白名单页：按进程/窗口特征精确放行或拦截。"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..dialogs.window_picker import pick_window
from ..widgets import ACCENT, DANGER, SUCCESS, TEXT_DIM, TEXT_MUTED, Card, PageHeader

FIELD_LABEL = {
    "process": "进程名",
    "path": "路径包含",
    "class": "窗口类名",
    "title": "标题正则",
}
FIELDS = [("进程名（精确）", "process"), ("路径包含", "path"),
          ("窗口类名（正则）", "class"), ("标题（正则）", "title")]
COLUMNS = ["匹配依据", "值", "备注", "操作"]


class AddEntryDialog(QDialog):
    def __init__(self, kind: str, feat: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加到" + ("白名单" if kind == "whitelist" else "黑名单"))
        self.resize(460, 250)
        self.kind = kind
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(9)

        self.field = QComboBox()
        for label, key in FIELDS:
            self.field.addItem(label, key)
        form.addRow("匹配依据", self.field)

        self.value = QLineEdit()
        self.value.setPlaceholderText("例如 wps.exe 或 ^KWPS.*")
        form.addRow("值", self.value)

        self.note = QLineEdit()
        self.note.setPlaceholderText("备注（可留空）")
        form.addRow("备注", self.note)
        lay.addLayout(form)

        if feat:
            lay.addWidget(self._hint(feat))

        pick = QPushButton("从屏幕窗口重新抓取")
        pick.setObjectName("Ghost")
        pick.clicked.connect(lambda: self._pick())
        lay.addWidget(pick, 0, Qt.AlignLeft)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("添加")
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._feat = feat
        if feat:
            self._apply(feat)

    def _hint(self, feat: dict) -> QLabel:
        lb = QLabel(
            f"已抓取：{feat.get('process')} / {feat.get('class_name')} / "
            f"{(feat.get('title') or '（无标题）')[:24]}"
        )
        lb.setObjectName("Dim")
        lb.setWordWrap(True)
        return lb

    def _apply(self, feat: dict) -> None:
        self._feat = feat
        idx = self.field.findData("process")
        self.field.setCurrentIndex(max(0, idx))
        self.value.setText(feat.get("process") or "")
        if not self.note.text():
            self.note.setText(f"{feat.get('process','')} · {feat.get('class_name','')}")

    def _pick(self) -> None:
        self.hide()
        feat = pick_window(self)
        self.show()
        if feat:
            self._apply(feat)

    def _accept(self) -> None:
        value = self.value.text().strip()
        if not value:
            QMessageBox.warning(self, "还差一步", "请填写要匹配的值")
            return
        field = self.field.currentData()
        if field in ("class", "title"):
            try:
                re.compile(value)
            except re.error as exc:
                QMessageBox.warning(self, "正则有误", str(exc))
                return
        self.accept()

    def entry(self) -> dict:
        return {
            "type": "process" if self.field.currentData() in ("process", "path") else "window",
            "field": self.field.currentData(),
            "value": self.value.text().strip(),
            "note": self.note.text().strip(),
        }


class ListsPage(QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(PageHeader("黑白名单", "白名单永不拦截，黑名单见一个拦一个 —— 比模糊规则更硬"))

        root.addWidget(self._build_section("whitelist", "白名单", "这些进程/窗口放行，任何规则都不动它",
                                           SUCCESS, "添加白名单"))
        root.addWidget(self._build_section("blacklist", "黑名单", "命中就按设定动作拦截，优先级高于内置规则",
                                           DANGER, "添加黑名单"), 1)

    def _build_section(self, kind: str, title: str, desc: str, color: str, btn_text: str) -> QWidget:
        card = Card(padding=14)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-weight:600; font-size:15px; color:{color};")
        head.addWidget(t)
        d = QLabel(desc)
        d.setObjectName("Muted")
        head.addSpacing(8)
        head.addWidget(d)
        head.addStretch(1)

        pick_btn = QPushButton(btn_text)
        pick_btn.setObjectName("Primary" if kind == "whitelist" else "Danger")
        pick_btn.clicked.connect(lambda: self._add(kind, from_picker=True))
        head.addWidget(pick_btn)

        manual = QPushButton("手动添加")
        manual.setObjectName("Ghost")
        manual.clicked.connect(lambda: self._add(kind, from_picker=False))
        head.addWidget(manual)
        card.body().addLayout(head)

        table = QTableWidget(0, len(COLUMNS))
        table.setHorizontalHeaderLabels(COLUMNS)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setShowGrid(False)
        table.setMinimumHeight(120)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.resizeSection(0, 110)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.resizeSection(3, 80)
        card.body().addWidget(table)

        setattr(self, f"table_{kind}", table)
        return card

    # ---------------- 数据 ----------------

    def refresh(self) -> None:
        self.engine.lists.load()
        for kind in ("whitelist", "blacklist"):
            table = getattr(self, f"table_{kind}", None)
            if table is None:
                continue
            entries = self.engine.lists.whitelist if kind == "whitelist" else self.engine.lists.blacklist
            table.setRowCount(0)
            for entry in entries:
                row = table.rowCount()
                table.insertRow(row)
                f_item = QTableWidgetItem(FIELD_LABEL.get(entry.get("field", ""), entry.get("field", "")))
                f_item.setForeground(QColor(TEXT_DIM))
                table.setItem(row, 0, f_item)
                v_item = QTableWidgetItem(str(entry.get("value", "")))
                v_item.setData(Qt.UserRole, entry.get("id"))
                table.setItem(row, 1, v_item)
                table.setItem(row, 2, QTableWidgetItem(entry.get("note", "")))
                btn = QPushButton("删除")
                btn.setObjectName("Danger")
                btn.setFixedHeight(24)
                btn.clicked.connect(lambda _=False, k=kind, i=entry.get("id"): self._remove(k, i))
                table.setCellWidget(row, 3, btn)
                table.setRowHeight(row, 32)

    # ---------------- 操作 ----------------

    def _add(self, kind: str, from_picker: bool) -> None:
        feat = pick_window(self) if from_picker else None
        if from_picker and not feat:
            return
        dlg = AddEntryDialog(kind, feat, self)
        if dlg.exec() == QDialog.Accepted:
            self.engine.lists.add(kind, dlg.entry())
            self.refresh()

    def _remove(self, kind: str, entry_id: str) -> None:
        self.engine.lists.remove(kind, entry_id)
        self.refresh()
