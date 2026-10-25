"""界面快照：离屏渲染每个页面并存成 PNG，用来检查排版有没有崩。

用法：
    .venv\\Scripts\\python.exe tools\\ui_snapshot.py [输出目录]
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="silen-snap-"))
os.environ["SILENWINDOW_DATA_DIR"] = str(TMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import ensure_dirs, settings  # noqa: E402
from app.core.engine import Engine  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.widgets import QSS  # noqa: E402


def load_system_fonts() -> None:
    """沙箱/离屏渲染时 Qt 拿不到系统字体库，手动把雅黑塞进去，只为截图好看。"""
    for path in (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(path).exists():
            QFontDatabase.addApplicationFont(path)

DEMO = [
    ("wps.exe", r"C:\Program Files\Kingsoft\WPS Office\wps.exe", "KWPSNewsWnd", "WPS 热点资讯：今日必读", "hide", "success", "WPS 资讯 / 热点弹窗", "block", 0),
    ("360se.exe", r"C:\Users\Wayne\AppData\Local\360Chrome\360se.exe", "Chrome_WidgetWin_1", "限时优惠 立即领取", "hide", "success", "360 浏览器推广窗", "block", 0),
    ("QQ.exe", r"C:\Program Files\Tencent\QQ\Bin\QQ.exe", "TXGuiFoundation", "游戏中心 新服开启", "close", "success", "QQ 资讯 / 游戏推广窗", "block", 0),
    ("SogouCloud.exe", r"C:\Program Files\SogouInput\SogouCloud.exe", "SogouFlashWnd", "皮肤推荐", "hide", "success", "搜狗输入法热搜 / 皮肤推广", "block", 0),
    ("Thunder.exe", r"C:\Program Files\Thunder\Thunder.exe", "ThunderRT6FormDC", "会员限时 5 折", "click_close", "failed", "迅雷广告 / 会员推荐", "block", 0),
    ("unknown.exe", r"C:\Users\Wayne\Downloads\某软件.exe", "Afx:12345", "猜你喜欢", "hide", "observed", "智能识别(仅记录)", "observe", 6),
    ("2345Explorer.exe", r"C:\Program Files\2345\2345Explorer.exe", "Chrome_WidgetWin_1", "今日推荐", "hide", "observed", "智能识别(仅记录)", "observe", 7),
    ("DrvInst.exe", r"C:\Program Files\DriverGenius\DrvInst.exe", "#32770", "福利活动", "hide", "needs_elevation", "驱动精灵推广窗", "block", 0),
]


def seed(engine: Engine) -> None:
    now = time.time()
    for i, (proc, path, cls, title, action, result, rule, mode, score) in enumerate(DEMO):
        feat = {
            "pid": 1000 + i,
            "process": proc,
            "exe_path": path,
            "class_name": cls,
            "title": title,
        }
        engine.stats.add_event(
            feat, action=action, result=result, rule_id=f"r{i}",
            rule_name=rule, mode=mode, score=score,
        )
        # 往前铺开，让 7 日趋势有形状
        engine.stats._conn.execute(
            "UPDATE events SET ts = ?, day = ? WHERE id = (SELECT MAX(id) FROM events)",
            (now - i * 3600 * 11, time.strftime("%Y-%m-%d", time.localtime(now - i * 3600 * 11))),
        )
    engine.stats._conn.commit()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    ensure_dirs()

    app = QApplication([])
    load_system_fonts()
    app.setStyleSheet(QSS)
    settings.set("engine_mode", "block")

    engine = Engine(settings)
    seed(engine)
    win = MainWindow(engine)
    win.resize(1020, 720)
    win.show()
    app.processEvents()

    for key in ("overview", "records", "rules", "lists", "settings"):
        win._select(key)
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        path = out / f"{key}.png"
        win.grab().save(str(path))
        print("saved", path)

    win.close()
    engine.stop()
    shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
