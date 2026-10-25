"""规则链路冒烟测试：存规则 → 落盘 → 表格能显示 → 编辑器返回 Accepted → Esc 能取消。

用法：.venv\\Scripts\\python.exe tools\\rules_smoke.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="silen-rules-"))
os.environ["SILENWINDOW_DATA_DIR"] = str(TMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from app.config import USER_RULES_PATH, ensure_dirs, settings  # noqa: E402
from app.core.engine import Engine  # noqa: E402
from app.ui.dialogs.rule_editor import RuleEditor  # noqa: E402
from app.ui.dialogs.window_picker import WindowPicker  # noqa: E402
from app.ui.pages.rules_page import RulesPage  # noqa: E402
from app.ui.widgets import QSS  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    ensure_dirs()
    app = QApplication([])
    app.setStyleSheet(QSS)
    engine = Engine(settings)

    print("\n[1] 用户规则落盘")
    rule = {
        "id": "user-smoke-1",
        "name": "冒烟测试规则",
        "vendor": "测试",
        "priority": 200,
        "action": "hide",
        "enabled": True,
        "match": {"process": ["smoke.exe"], "title_re": "广告"},
    }
    engine.rules.add_user(rule)
    check("user_rules.json 已创建", USER_RULES_PATH.exists(), str(USER_RULES_PATH))
    stored = json.loads(USER_RULES_PATH.read_text(encoding="utf-8")) if USER_RULES_PATH.exists() else []
    check("文件里有 1 条规则", len(stored) == 1, str(stored))
    check("规则 source=user", stored and stored[0].get("source") == "user")

    print("\n[2] 重新加载后仍在")
    engine.rules.load()
    users = [r for r in engine.rules.all_rules() if r.get("source") == "user"]
    check("all_rules 能筛出用户规则", len(users) == 1, f"got {len(users)}")

    print("\n[3] 规则管理页表格能显示")
    page = RulesPage(engine)
    page.refresh()
    check("自定义 Tab 有 1 行", page.table_user.rowCount() == 1, f"rows={page.table_user.rowCount()}")
    if page.table_user.rowCount():
        check("名称列内容正确", page.table_user.item(0, 1).text() == "冒烟测试规则",
              page.table_user.item(0, 1).text())
    check("内置规则 Tab 非空", page.table_builtin.rowCount() > 0,
          f"rows={page.table_builtin.rowCount()}")

    print("\n[4] 规则编辑器返回 Accepted")
    editor = RuleEditor(None)
    editor.name.setText("编辑器测试")
    editor.process.setText("editor.exe")
    editor._save()
    check("result 是 Accepted", editor.result() == QDialog.DialogCode.Accepted, str(editor.result()))
    got = editor.rule()
    check("返回的规则带 match", got.get("match") == {"process": ["editor.exe"]}, str(got.get("match")))

    print("\n[5] 拾窗器 Esc 能取消")
    picker = WindowPicker()
    picker.show()
    app.processEvents()
    QTest.keyClick(picker, Qt.Key_Escape)
    app.processEvents()
    check("Esc 后已关闭", not picker.isVisible(), f"visible={picker.isVisible()}")
    check("result 是 Rejected", picker.result() == QDialog.DialogCode.Rejected, str(picker.result()))

    print("\n[6] 走一遍「新建规则」按钮的完整代码路径")
    import app.ui.pages.rules_page as rp

    RealEditor = rp.RuleEditor

    class StubEditor(RealEditor):
        """替身：构造时填好字段并保存，exec() 直接返回 Accepted。"""

        def __init__(self, rule=None, parent=None):
            super().__init__(rule, parent)
            self.name.setText("按钮路径测试")
            self.process.setText("btn.exe")
            self._save()

        def exec(self):
            return QDialog.DialogCode.Accepted

    rp.RuleEditor = StubEditor
    try:
        before = page.table_user.rowCount()
        page._new()
        after = page.table_user.rowCount()
    finally:
        rp.RuleEditor = RealEditor

    check("表格多了一行", after == before + 1, f"{before} -> {after}")
    stored = json.loads(USER_RULES_PATH.read_text(encoding="utf-8"))
    check("文件里变成 2 条", len(stored) == 2, f"got {len(stored)}")
    check("新规则名称正确", any(r.get("name") == "按钮路径测试" for r in stored))

    page.close()
    shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + ("全部通过 ✅" if not failures else f"失败 {len(failures)} 项 ❌ -> {failures}"))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
