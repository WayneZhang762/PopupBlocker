"""规则编辑器：可视化拼一条匹配规则，不用手写 JSON。"""
from __future__ import annotations

import re
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..widgets import TEXT_DIM
from .window_picker import pick_window

ACTIONS = [("隐藏窗口（最温和）", "hide"), ("发送关闭消息", "close"), ("模拟点关闭按钮", "click_close")]


def _split(text: str) -> list[str]:
    parts = re.split(r"[,，;；\n]+", text)
    return [p.strip() for p in parts if p.strip()]


class RuleEditor(QDialog):
    def __init__(self, rule: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑规则" if rule else "新建规则")
        self.resize(600, 620)
        self._rule = dict(rule or {})
        self._build()
        self._fill(self._rule)

    # ---------------- 布局 ----------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        tip = QLabel(
            "「进程 / 类名 / 标题 / 路径」里填写的条件会同时生效（都要满足）；"
            "同一栏里用逗号分隔多个值，表示满足任一即可。"
        )
        tip.setObjectName("Dim")
        tip.setWordWrap(True)
        root.addWidget(tip)

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name = QLineEdit()
        self.name.setPlaceholderText("例如：WPS 右下角资讯窗")
        form.addRow("规则名称", self.name)

        self.vendor = QLineEdit()
        self.vendor.setPlaceholderText("例如：WPS（可留空）")
        form.addRow("厂商/分类", self.vendor)

        self.priority = QSpinBox()
        self.priority.setRange(0, 999)
        self.priority.setValue(200)
        self.priority.setToolTip("数值越大越优先匹配。用户规则默认 200，高于内置规则")
        form.addRow("优先级", self.priority)

        self.action = QComboBox()
        for label, key in ACTIONS:
            self.action.addItem(label, key)
        form.addRow("拦截动作", self.action)

        self.process = QLineEdit()
        self.process.setPlaceholderText("wps.exe, 360*.exe")
        form.addRow("进程名", self.process)

        self.path = QLineEdit()
        self.path.setPlaceholderText(r"\kingsoft\  （可留空）")
        form.addRow("路径包含", self.path)

        self.class_re = QLineEdit()
        self.class_re.setPlaceholderText("^KWPS.*  （正则，可留空）")
        form.addRow("窗口类名", self.class_re)

        self.title_re = QLineEdit()
        self.title_re.setPlaceholderText("资讯|热点|推荐  （正则，可留空）")
        form.addRow("标题匹配", self.title_re)

        self.title_not_re = QLineEdit()
        self.title_not_re.setPlaceholderText("升级|错误  （命中则本条规则作废）")
        form.addRow("标题排除", self.title_not_re)

        style_row = QHBoxLayout()
        self.cb_toolwindow = QCheckBox("必须是工具窗口")
        self.cb_notaskbar = QCheckBox("任务栏无按钮")
        style_row.addWidget(self.cb_toolwindow)
        style_row.addWidget(self.cb_notaskbar)
        style_row.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(style_row)
        form.addRow("窗口样式", wrapper)

        flags = QHBoxLayout()
        self.cb_notfg = QCheckBox("非前台")
        self.cb_noowner = QCheckBox("无主窗口")
        flags.addWidget(self.cb_notfg)
        flags.addWidget(self.cb_noowner)
        flags.addStretch(1)
        fw = QWidget()
        fw.setLayout(flags)
        form.addRow("其他条件", fw)

        self.max_area = QDoubleSpinBox()
        self.max_area.setRange(0.0, 1.0)
        self.max_area.setSingleStep(0.05)
        self.max_area.setDecimals(2)
        self.max_area.setSpecialValueText("不限")
        form.addRow("最大面积占比", self.max_area)

        self.note = QPlainTextEdit()
        self.note.setFixedHeight(56)
        self.note.setPlaceholderText("备注（可留空）")
        form.addRow("备注", self.note)

        root.addLayout(form)

        pick_row = QHBoxLayout()
        self.pick_btn = QPushButton("从屏幕窗口抓取特征")
        self.pick_btn.clicked.connect(self._pick)
        pick_row.addWidget(self.pick_btn)
        self.preview = QLabel("")
        self.preview.setObjectName("Dim")
        self.preview.setWordWrap(True)
        pick_row.addWidget(self.preview, 1)
        root.addLayout(pick_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---------------- 数据 ----------------

    def _fill(self, rule: dict) -> None:
        m = rule.get("match") or {}
        self.name.setText(rule.get("name", ""))
        self.vendor.setText(rule.get("vendor", ""))
        self.priority.setValue(int(rule.get("priority", 200)))
        idx = self.action.findData(rule.get("action", "hide"))
        self.action.setCurrentIndex(max(0, idx))

        self.process.setText(", ".join(m.get("process", []) if isinstance(m.get("process"), list) else [m.get("process", "")]) if m.get("process") else "")
        self.path.setText(", ".join(m.get("path_contains", [])) if m.get("path_contains") else "")
        self.class_re.setText(", ".join(m.get("class_re", [])) if m.get("class_re") else "")
        tr = m.get("title_re", "")
        self.title_re.setText(", ".join(tr) if isinstance(tr, list) else tr)
        tn = m.get("title_not_re", "")
        self.title_not_re.setText(", ".join(tn) if isinstance(tn, list) else tn)
        self.cb_toolwindow.setChecked(bool(m.get("exstyle_has")))
        self.cb_notaskbar.setChecked(bool(m.get("exstyle_lacks")))
        self.cb_notfg.setChecked(bool(m.get("not_foreground")))
        self.cb_noowner.setChecked(bool(m.get("no_owner")))
        self.max_area.setValue(float(m.get("max_area_ratio", 0.0) or 0.0))
        self.note.setPlainText(rule.get("note", ""))

    def _pick(self) -> None:
        feat = pick_window(self)
        if not feat:
            return
        self.process.setText(feat.get("process") or "")
        self.class_re.setText(re.escape(feat.get("class_name") or ""))
        title = (feat.get("title") or "").strip()
        if title:
            self.title_re.setText(re.escape(title[:24]))
        if not self.name.text():
            self.name.setText(f"{feat.get('process','')} 弹窗")
        self.cb_notfg.setChecked(True)
        self.preview.setText(
            f"已抓取：{feat.get('process')} / {feat.get('class_name')} / {title[:20]}"
        )

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "还差一步", "请填写规则名称")
            return

        match: dict = {}
        if _split(self.process.text()):
            match["process"] = _split(self.process.text())
        if _split(self.path.text()):
            match["path_contains"] = _split(self.path.text())
        if _split(self.class_re.text()):
            match["class_re"] = _split(self.class_re.text())
        if _split(self.title_re.text()):
            match["title_re"] = _split(self.title_re.text())
        if _split(self.title_not_re.text()):
            match["title_not_re"] = _split(self.title_not_re.text())
        if self.cb_toolwindow.isChecked():
            match["exstyle_has"] = ["WS_EX_TOOLWINDOW"]
        if self.cb_notaskbar.isChecked():
            match["exstyle_lacks"] = ["WS_EX_APPWINDOW"]
        if self.cb_notfg.isChecked():
            match["not_foreground"] = True
        if self.cb_noowner.isChecked():
            match["no_owner"] = True
        if self.max_area.value() > 0:
            match["max_area_ratio"] = round(self.max_area.value(), 2)

        if not match:
            QMessageBox.warning(self, "还差一步", "至少填一个匹配条件，否则规则会匹配所有窗口")
            return

        # 正则合法性校验
        for key in ("class_re", "title_re", "title_not_re"):
            for pattern in match.get(key, []):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    QMessageBox.warning(self, "正则有误", f"{key} 里的 `{pattern}` 无法解析：{exc}")
                    return

        rule = {
            "id": self._rule.get("id") or f"user-{int(time.time() * 1000)}",
            "name": name,
            "vendor": self.vendor.text().strip() or "自定义",
            "priority": self.priority.value(),
            "action": self.action.currentData(),
            "enabled": self._rule.get("enabled", True),
            "note": self.note.toPlainText().strip(),
            "match": match,
        }
        self.result_rule = rule
        self.accept()

    def rule(self) -> dict:
        return getattr(self, "result_rule", {})
