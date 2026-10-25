"""规则管理页：内置规则 + 自定义规则，可启停、编辑、导入导出、测试。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import action as action_mod
from ...core.rule_store import action_label, describe_match
from ..dialogs.rule_editor import RuleEditor
from ..dialogs.window_picker import pick_window
from ..widgets import ACCENT, TEXT_DIM, TEXT_MUTED, WARN, Card, PageHeader

COLUMNS = ["启用", "规则名称", "匹配条件", "动作", "命中", "来源"]


class _RuleTable(QTableWidget):
    def __init__(self, on_toggle, parent=None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.on_toggle = on_toggle
        self._loading = False
        self.setHorizontalHeaderLabels(COLUMNS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.resizeSection(0, 52)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.resizeSection(1, 190)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.resizeSection(3, 92)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.resizeSection(4, 56)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        hh.resizeSection(5, 80)
        self.itemChanged.connect(self._item_changed)

    def load(self, rules: list[dict], hits: dict[str, int]) -> None:
        self._loading = True
        self.setRowCount(0)
        for rule in rules:
            row = self.rowCount()
            self.insertRow(row)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if rule.get("enabled") else Qt.Unchecked)
            chk.setData(Qt.UserRole, rule.get("id"))
            self.setItem(row, 0, chk)

            name_item = QTableWidgetItem(rule.get("name", ""))
            name_item.setData(Qt.UserRole, rule.get("id"))
            if rule.get("note"):
                name_item.setToolTip(rule["note"])
            self.setItem(row, 1, name_item)

            cond = QTableWidgetItem(describe_match(rule))
            cond.setForeground(QColor(TEXT_DIM))
            cond.setToolTip(describe_match(rule))
            self.setItem(row, 2, cond)

            act = QTableWidgetItem(action_label(rule.get("action", "")))
            act.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 3, act)

            cnt = QTableWidgetItem(str(hits.get(rule.get("id", ""), 0)))
            cnt.setTextAlignment(Qt.AlignCenter)
            if hits.get(rule.get("id", ""), 0):
                cnt.setForeground(QColor(ACCENT))
            self.setItem(row, 4, cnt)

            src = QTableWidgetItem(rule.get("vendor") or ("内置" if rule.get("source") == "builtin" else "自定义"))
            src.setForeground(QColor(TEXT_MUTED))
            src.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 5, src)
            self.setRowHeight(row, 32)
        self._loading = False

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != 0:
            return
        rule_id = item.data(Qt.UserRole)
        if rule_id:
            self.on_toggle(rule_id, item.checkState() == Qt.Checked)

    def selected_rule_id(self) -> str:
        row = self.currentRow()
        if row < 0:
            return ""
        item = self.item(row, 1)
        return item.data(Qt.UserRole) if item else ""


class RulesPage(QWidget):
    def __init__(self, engine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(PageHeader("规则管理", "命中即执行：内置规则开箱可用，自定义规则说清你的偏好"))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.btn_new = QPushButton("新建规则")
        self.btn_new.setObjectName("Primary")
        self.btn_new.clicked.connect(self._new)
        toolbar.addWidget(self.btn_new)

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.clicked.connect(self._edit)
        toolbar.addWidget(self.btn_edit)

        self.btn_copy = QPushButton("复制")
        self.btn_copy.clicked.connect(self._copy)
        toolbar.addWidget(self.btn_copy)

        self.btn_del = QPushButton("删除")
        self.btn_del.setObjectName("Danger")
        self.btn_del.clicked.connect(self._delete)
        toolbar.addWidget(self.btn_del)

        toolbar.addStretch(1)

        self.btn_test = QPushButton("测试规则")
        self.btn_test.setObjectName("Ghost")
        self.btn_test.clicked.connect(self._test)
        toolbar.addWidget(self.btn_test)

        self.btn_import = QPushButton("导入")
        self.btn_import.setObjectName("Ghost")
        self.btn_import.clicked.connect(self._import)
        toolbar.addWidget(self.btn_import)

        self.btn_export = QPushButton("导出")
        self.btn_export.setObjectName("Ghost")
        self.btn_export.clicked.connect(self._export)
        toolbar.addWidget(self.btn_export)
        root.addLayout(toolbar)

        self.tabs = QTabWidget()
        card_builtin = Card(padding=10)
        self.table_builtin = _RuleTable(self._toggle)
        card_builtin.body().addWidget(self.table_builtin)
        card_user = Card(padding=10)
        self.table_user = _RuleTable(self._toggle)
        card_user.body().addWidget(self.table_user)
        self.tabs.addTab(card_builtin, "内置规则")
        self.tabs.addTab(card_user, "自定义规则")
        self.tabs.currentChanged.connect(self._on_tab)
        root.addWidget(self.tabs, 1)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

    def _on_tab(self, index: int) -> None:
        self.refresh()

    # ---------------- 数据 ----------------

    def refresh(self) -> None:
        store = self.engine.rules
        store.load()
        hits: dict[str, int] = {}
        try:
            rows = self.engine.stats.query(limit=2000)
            for r in rows:
                rid = r.get("rule_id") or ""
                if rid:
                    hits[rid] = hits.get(rid, 0) + 1
        except Exception:
            pass

        builtin = [r for r in store.all_rules() if r.get("source") == "builtin"]
        user = [r for r in store.all_rules() if r.get("source") == "user"]
        self.table_builtin.load(builtin, hits)
        self.table_user.load(user, hits)
        self.status.setText(
            f"内置 {len(builtin)} 条（{sum(1 for r in builtin if r['enabled'])} 条启用）· "
            f"自定义 {len(user)} 条"
        )
        is_user_tab = self.tabs.currentIndex() == 1
        self.btn_edit.setEnabled(is_user_tab)
        self.btn_copy.setEnabled(True)
        self.btn_del.setEnabled(is_user_tab)

    def _current_table(self) -> _RuleTable:
        return self.table_user if self.tabs.currentIndex() == 1 else self.table_builtin

    def _toggle(self, rule_id: str, enabled: bool) -> None:
        self.engine.rules.set_enabled(rule_id, enabled)
        self.engine.reload_rules()
        self.status.setText("已更新规则状态")

    # ---------------- 操作 ----------------

    def _new(self) -> None:
        dlg = RuleEditor(None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.engine.rules.add_user(dlg.rule())
            self.engine.reload_rules()
            self.tabs.setCurrentIndex(1)
            self.refresh()

    def _edit(self) -> None:
        table = self._current_table()
        rule_id = table.selected_rule_id()
        if not rule_id:
            QMessageBox.information(self, "编辑规则", "请先选中一条规则")
            return
        rule = self.engine.rules.get(rule_id)
        if not rule:
            return
        if rule.get("source") == "builtin":
            QMessageBox.information(
                self, "内置规则",
                "内置规则不能直接改。可以点「复制」生成一条自定义规则再改。",
            )
            return
        dlg = RuleEditor(rule, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.engine.rules.update_user(dlg.rule())
            self.engine.reload_rules()
            self.refresh()

    def _copy(self) -> None:
        table = self._current_table()
        rule_id = table.selected_rule_id()
        if not rule_id:
            QMessageBox.information(self, "复制规则", "请先选中一条规则")
            return
        rule = self.engine.rules.get(rule_id)
        if not rule:
            return
        new_rule = {
            "id": f"user-{int(time.time() * 1000)}",
            "name": f"{rule.get('name','规则')}（副本）",
            "vendor": rule.get("vendor", "自定义"),
            "priority": 200,
            "action": rule.get("action", "hide"),
            "enabled": True,
            "note": rule.get("note", ""),
            "match": dict(rule.get("match") or {}),
        }
        self.engine.rules.add_user(new_rule)
        self.engine.reload_rules()
        self.tabs.setCurrentIndex(1)
        self.refresh()
        QMessageBox.information(self, "已复制", "副本已放进「自定义规则」，可以直接编辑。")

    def _delete(self) -> None:
        table = self._current_table()
        rule_id = table.selected_rule_id()
        if not rule_id:
            QMessageBox.information(self, "删除规则", "请先选中一条规则")
            return
        rule = self.engine.rules.get(rule_id)
        if not rule or rule.get("source") != "user":
            QMessageBox.information(self, "删除规则", "内置规则不能删除，可以取消勾选来停用。")
            return
        ret = QMessageBox.question(
            self, "删除规则", f"确定删除「{rule.get('name','')}」吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.engine.rules.delete_user(rule_id)
            self.engine.reload_rules()
            self.refresh()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入规则", "", "规则文件 (*.json)")
        if not path:
            return
        try:
            count = self.engine.rules.import_rules(__import__("pathlib").Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self.engine.reload_rules()
        self.tabs.setCurrentIndex(1)
        self.refresh()
        QMessageBox.information(self, "导入完成", f"已导入 {count} 条规则")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出规则", f"弹窗规则_{time.strftime('%Y%m%d')}.json", "规则文件 (*.json)"
        )
        if not path:
            return
        try:
            count = self.engine.rules.export_rules(__import__("pathlib").Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出完成", f"已导出 {count} 条规则到\n{path}")

    def _test(self) -> None:
        feat = pick_window(self)
        if not feat:
            return
        matches = self.engine.classifier.explain(feat)
        hit = [m for m in matches if m["matched"]]
        head = (
            f"进程：{feat.get('process')}\n"
            f"类名：{feat.get('class_name')}\n"
            f"标题：{feat.get('title') or '（无标题）'}\n"
            f"面积占比：{feat.get('area_ratio')}\n\n"
        )
        if hit:
            body = "命中的规则：\n" + "\n".join(
                f"  · {m['name']}（{m['vendor']}，{action_label(m['action'])}）"
                + ("" if m["enabled"] else "【已停用】")
                for m in hit
            )
        else:
            score, why = self.engine.classifier.heuristic_score(feat)
            body = (
                "没有任何规则命中。\n\n"
                f"启发式评分：{score}（{'、'.join(why) if why else '无特征'}）\n"
                + ("照这个分数会被当作可疑弹窗记录。" if score >= 5 else "这个窗口大概率是用户自己的正常窗口。")
            )
        QMessageBox.information(self, "规则测试结果", head + body)
