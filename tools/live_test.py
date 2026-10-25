"""端到端联调：造一个真弹窗 + 一个正常窗口，验证拦截是否生效。

前提：静窗正在运行，且处于「实际拦截」模式。
用法：.venv\\Scripts\\python.exe tools\\live_test.py
"""
from __future__ import annotations

import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

import win32gui


def pump(app: QApplication, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)


def main() -> int:
    app = QApplication(sys.argv)

    popup = QWidget()
    popup.setWindowTitle("限时优惠 立即领取 福利活动")
    popup.setWindowFlags(
        Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    )
    popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
    popup.setGeometry(220, 220, 300, 180)
    popup.show()

    normal = QWidget()
    normal.setWindowTitle("我的工作台 - 正常窗口")
    normal.setGeometry(620, 300, 420, 300)
    normal.show()

    pump(app, 0.6)
    popup_hwnd = int(popup.winId())
    normal_hwnd = int(normal.winId())
    print(f"弹窗 hwnd={popup_hwnd:x} 正常窗 hwnd={normal_hwnd:x}")
    print("等待引擎处理（约 6 秒）…")
    pump(app, 6.0)

    popup_visible = bool(win32gui.IsWindowVisible(popup_hwnd)) if win32gui.IsWindow(popup_hwnd) else False
    normal_visible = bool(win32gui.IsWindowVisible(normal_hwnd)) if win32gui.IsWindow(normal_hwnd) else False

    print(f"广告弹窗还可见: {popup_visible}   <- 期望 False")
    print(f"正常窗口还可见: {normal_visible}   <- 期望 True")
    ok = (not popup_visible) and normal_visible
    print("结论:", "拦截生效 ✅" if ok else "没有按预期工作 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
