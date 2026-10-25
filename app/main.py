"""静窗 · 程序入口。"""
from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

# 允许直接 `python app\main.py` 运行
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.config import APP_ID, APP_NAME, VERSION, ensure_dirs, settings, setup_logging
from app.core.engine import Engine
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow
from app.ui.tray import Tray
from app.ui.widgets import QSS

log = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183
_mutex = None


def _single_instance() -> bool:
    """命名互斥体防止开两个实例。"""
    global _mutex
    try:
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Global\\{APP_ID}_SingleInstance")
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _install_excepthook() -> None:
    """Qt 槽函数里抛的异常默认会被吞掉（打包后没有控制台），必须显式暴露出来。"""
    shown = {"n": 0}

    def hook(exc_type, exc, tb) -> None:
        log.error("未捕获异常", exc_info=(exc_type, exc, tb))
        shown["n"] += 1
        if shown["n"] > 3:
            return
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} 出错了",
                f"{exc_type.__name__}: {exc}\n\n"
                "这个错误已经写入 data\\logs\\silenwindow.log。\n"
                "如果界面没反应，重启一下程序再试。",
            )
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    ensure_dirs()
    setup_logging(str(settings.get("log_level") or "INFO"))
    log.info("启动 %s v%s", APP_NAME, VERSION)

    if not _single_instance():
        app = QApplication(sys.argv)
        QMessageBox.information(None, APP_NAME, f"{APP_NAME} 已经在运行了，看右下角托盘图标。")
        return 0

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    _install_excepthook()
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(QSS)

    engine = Engine(settings)
    window = MainWindow(engine)
    tray = Tray(engine, window)
    window.tray_refresh = lambda: tray.refresh()
    window.closedToTray.connect(
        lambda: tray.icon.showMessage(
            APP_NAME, "还在后台看着呢，双击托盘图标可以再打开。",
            QSystemTrayIcon.Information, 1800,
        )
    )

    engine.start()

    if settings.get("start_minimized"):
        log.info("按设置启动即最小化到托盘")
    else:
        window.show()

    try:
        return app.exec()
    finally:
        engine.stop()
        log.info("退出")


if __name__ == "__main__":
    raise SystemExit(main())
