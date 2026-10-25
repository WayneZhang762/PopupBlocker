"""窗口特征采集：把一个 HWND 反查成可判定的特征包。"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import win32api
import win32gui
import win32process

from . import process_info

GA_ROOT = 2
GW_OWNER = 4
GWL_STYLE = -16
GWL_EXSTYLE = -20

WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

EXSTYLE_NAMES = {
    WS_EX_TOOLWINDOW: "WS_EX_TOOLWINDOW",
    WS_EX_APPWINDOW: "WS_EX_APPWINDOW",
    WS_EX_TOPMOST: "WS_EX_TOPMOST",
    WS_EX_NOACTIVATE: "WS_EX_NOACTIVATE",
}


def virtual_screen() -> tuple[int, int, int, int]:
    try:
        return (
            win32api.GetSystemMetrics(SM_XVIRTUALSCREEN),
            win32api.GetSystemMetrics(SM_YVIRTUALSCREEN),
            win32api.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            win32api.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
    except Exception:
        return (0, 0, 1920, 1080)


def exstyle_names(exstyle: int) -> list[str]:
    return [name for bit, name in EXSTYLE_NAMES.items() if exstyle & bit]


def foreground_pid() -> int:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return 0
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
    except Exception:
        return 0


def probe(hwnd: int, with_process: bool = True) -> dict | None:
    """采集特征。返回 None 表示这不是一个值得关注的顶层可见窗口。"""
    if not hwnd:
        return None
    try:
        if not win32gui.IsWindow(hwnd):
            return None
        if win32gui.GetAncestor(hwnd, GA_ROOT) != hwnd:
            return None
        if not win32gui.IsWindowVisible(hwnd):
            return None
        class_name = win32gui.GetClassName(hwnd) or ""
        title = win32gui.GetWindowText(hwnd) or ""
        rect = win32gui.GetWindowRect(hwnd)
        owner = win32gui.GetWindow(hwnd, GW_OWNER)
        style = win32gui.GetWindowLong(hwnd, GWL_STYLE) & 0xFFFFFFFF
        exstyle = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return None

    left, top, right, bottom = rect
    width = max(0, right - left)
    height = max(0, bottom - top)
    # 隐藏的辅助窗口 / 0 尺寸窗口没有分析价值，直接丢弃（大幅降噪）
    if width < 8 or height < 8:
        return None
    vx, vy, vw, vh = virtual_screen()
    screen_area = max(1, vw * vh)

    info = {
        "hwnd": hwnd,
        "pid": pid,
        "process": "",
        "exe_path": "",
        "parent_process": "",
        "process_age_s": -1,
        "class_name": class_name,
        "title": title,
        "style": style,
        "exstyle": exstyle,
        "exstyle_names": exstyle_names(exstyle),
        "rect": (left, top, right, bottom),
        "width": width,
        "height": height,
        "area_ratio": round((width * height) / screen_area, 3),
        "owner_hwnd": owner or 0,
        "is_foreground": False,
        "is_topmost": bool(exstyle & WS_EX_TOPMOST),
        "has_taskbar_button": False,
        "seen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ts": time.time(),
    }

    if with_process and pid:
        pinfo = process_info.describe(pid)
        info["process"] = pinfo.get("process", "")
        info["exe_path"] = pinfo.get("exe_path", "")
        info["parent_process"] = pinfo.get("parent", "")
        info["process_age_s"] = pinfo.get("age_s", -1)

    # 任务栏按钮的近似判定：无 owner、非 toolwindow、无 NOACTIVATE
    info["has_taskbar_button"] = (
        not owner
        and not (exstyle & WS_EX_TOOLWINDOW)
        and not (exstyle & WS_EX_NOACTIVATE)
        and bool(style & WS_VISIBLE)
    )
    try:
        info["is_foreground"] = win32gui.GetForegroundWindow() == hwnd
    except Exception:
        pass
    return info


def enumerate_top_level() -> list[int]:
    """枚举当前所有顶层可见窗口，用于启动时补扫。"""
    result: list[int] = []

    def _cb(hwnd, _lparam):
        try:
            if win32gui.IsWindowVisible(hwnd):
                result.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return result
