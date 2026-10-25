"""拦截执行器（温和档）：隐藏 / 发送关闭消息 / 点击关闭按钮。

设计要点：
- 绝不结束进程，只对"窗口"做动作
- 同一 (pid, 类名, 标题) 60 秒内只处理一次，防"关了又弹"死循环
- 隐藏后有看门狗复查，被重新显示会再隐藏（最多 2 次）
- 目标进程权限高于自己时，返回 needs_elevation 而不是反复徒劳尝试
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui

log = logging.getLogger(__name__)

SUCCESS = "success"
FAILED = "failed"
SKIPPED = "skipped"
NEEDS_ELEVATION = "needs_elevation"

COOLDOWN_SEC = 60.0
_lock = threading.Lock()
_cooldown: dict[tuple, float] = {}

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TokenIntegrityLevel = 25
SMTO_ABORTIFHUNG = 0x0002
SMTO_BLOCK = 0x0001
HTCLOSE = 20

_advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
_advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
_advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


# ---------------------------------------------------------------- 权限级别

def integrity_level(pid: int) -> int | None:
    """返回进程完整性级别：0x1000 普通 / 0x2000 管理员 / 0x3000 系统。"""
    if not pid:
        return None
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    token = wintypes.HANDLE()
    try:
        if not _advapi32.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
            return None
        size = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(size))
        if size.value == 0:
            return None
        buf = ctypes.create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(
            token, TokenIntegrityLevel, buf, size, ctypes.byref(size)
        ):
            return None
        sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid:
            return None
        count_ptr = _advapi32.GetSidSubAuthorityCount(sid)
        if not count_ptr:
            return None
        count = count_ptr[0]
        level_ptr = _advapi32.GetSidSubAuthority(sid, count - 1)
        if not level_ptr:
            return None
        return int(level_ptr[0])
    except Exception:
        return None
    finally:
        if token:
            try:
                _kernel32.CloseHandle(token)
            except Exception:
                pass
        _kernel32.CloseHandle(handle)


_own_level: int | None = None


def _higher_than_us(pid: int) -> bool:
    global _own_level
    if _own_level is None:
        _own_level = integrity_level(os.getpid()) or 0x1000
    lv = integrity_level(pid)
    return lv is not None and lv > (_own_level or 0x1000)


# ---------------------------------------------------------------- 冷却表

def _key(feat: dict) -> tuple:
    return (
        feat.get("pid", 0),
        feat.get("class_name", ""),
        (feat.get("title") or "")[:40],
    )


def is_cooling(feat: dict) -> bool:
    now = time.time()
    with _lock:
        dead = [k for k, ts in _cooldown.items() if now - ts > 600]
        for k in dead:
            _cooldown.pop(k, None)
        ts = _cooldown.get(_key(feat))
    return ts is not None and now - ts < COOLDOWN_SEC


def _touch(feat: dict) -> None:
    with _lock:
        _cooldown[_key(feat)] = time.time()


# ---------------------------------------------------------------- 基础判断

def _alive(hwnd: int) -> bool:
    try:
        return bool(win32gui.IsWindow(hwnd))
    except Exception:
        return False


def _visible(hwnd: int) -> bool:
    try:
        return bool(win32gui.IsWindowVisible(hwnd))
    except Exception:
        return False


def _gone(hwnd: int) -> bool:
    return (not _alive(hwnd)) or (not _visible(hwnd))


# ---------------------------------------------------------------- 三种动作

def _watchdog(hwnd: int, pid: int) -> None:
    """被隐藏的窗口可能被软件重新 ShowWindow，短暂复查两次。"""

    def run() -> None:
        for delay in (0.8, 1.8):
            time.sleep(delay)
            if not _alive(hwnd):
                return
            if _visible(hwnd):
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    log.debug("看门狗再次隐藏 hwnd=%x pid=%s", hwnd, pid)
                except Exception:
                    return

    threading.Thread(target=run, daemon=True, name="HideWatchdog").start()


def _do_hide(hwnd: int, pid: int) -> bool:
    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    if _gone(hwnd):
        _watchdog(hwnd, pid)
        return True
    return False


def _do_close(hwnd: int, pid: int) -> bool:
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    for _ in range(4):
        time.sleep(0.1)
        if _gone(hwnd):
            return True
    # 同步再试一次，应对消息队列繁忙
    try:
        result = wintypes.DWORD()
        _user32.SendMessageTimeoutW(
            wintypes.HWND(hwnd),
            win32con.WM_CLOSE,
            wintypes.WPARAM(0),
            wintypes.LPARAM(0),
            SMTO_ABORTIFHUNG | SMTO_BLOCK,
            400,
            ctypes.byref(result),
        )
    except Exception:
        pass
    time.sleep(0.15)
    if _gone(hwnd):
        return True
    # 关不掉就退回隐藏
    return _do_hide(hwnd, pid)


_CLOSE_TEXTS = {"关闭", "确定", "取消", "close", "cancel", "×", "x"}


def _find_close_button(hwnd: int) -> int:
    found: list[int] = []

    def cb(h, _param):
        try:
            cls = win32gui.GetClassName(h) or ""
            txt = (win32gui.GetWindowText(h) or "").strip().lower()
            if cls.lower() == "button" and txt in _CLOSE_TEXTS:
                found.append(h)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass
    return found[0] if found else 0


def _do_click_close(hwnd: int, pid: int) -> bool:
    button = _find_close_button(hwnd)
    if button:
        try:
            win32gui.PostMessage(button, win32con.BM_CLICK, 0, 0)
            time.sleep(0.2)
            if _gone(hwnd):
                return True
        except Exception:
            pass
    try:
        _, _, cw, ch = win32gui.GetClientRect(hwnd)
    except Exception:
        cw, ch = 200, 120
    x, y = max(4, cw - 14), 14
    lp = win32api.MAKELONG(x, y)
    try:
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)
        time.sleep(0.15)
        if _gone(hwnd):
            return True
        # 试标题栏关闭热区
        win32gui.PostMessage(hwnd, win32con.WM_NCLBUTTONDOWN, HTCLOSE, lp)
        win32gui.PostMessage(hwnd, win32con.WM_NCLBUTTONUP, HTCLOSE, lp)
        time.sleep(0.15)
        if _gone(hwnd):
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- 入口

def apply_action(feat: dict, action: str) -> str:
    hwnd = int(feat.get("hwnd") or 0)
    pid = int(feat.get("pid") or 0)
    if not hwnd or not _alive(hwnd):
        return SKIPPED
    if action not in ("hide", "close", "click_close"):
        return SKIPPED
    if is_cooling(feat):
        return SKIPPED
    _touch(feat)

    try:
        if action == "hide":
            ok = _do_hide(hwnd, pid)
        elif action == "close":
            ok = _do_close(hwnd, pid)
        else:
            ok = _do_click_close(hwnd, pid)
    except Exception:
        log.exception("执行拦截动作失败 hwnd=%x action=%s", hwnd, action)
        return FAILED

    if ok:
        log.info("已拦截 [%s] %s | %s | %s", action, feat.get("process"), feat.get("title"), feat.get("class_name"))
        return SUCCESS

    if _higher_than_us(pid):
        return NEEDS_ELEVATION
    return FAILED
