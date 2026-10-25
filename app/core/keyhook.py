"""拾窗期间用的全局 Esc 监听。

为什么需要它：全屏遮罩一旦因为任何原因没拿到键盘焦点（Windows 前台锁、
父窗口处于模态、多显示器切换……），Qt 的 keyPressEvent 就永远收不到按键，
用户按 Esc 毫无反应。这里用 WH_KEYBOARD_LL 兜底 —— 它不依赖窗口焦点。

使用约束（重要）：
- 只在拾窗器显示的那一两秒内安装，关闭立即卸载，不做常驻键盘监听
- 回调里只做一次信号 emit，绝不做耗时操作（系统键盘钩子有超时限制）
- 安装失败时静默降级，不影响拾窗器本身的 Qt 键盘路径
"""
from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes

log = logging.getLogger(__name__)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012
VK_ESCAPE = 0x1B

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


class EscapeHook:
    """安一个只认 Esc 的全局键盘钩子。on_escape 会在钩子线程里被调用。"""

    def __init__(self, on_escape) -> None:
        self._on_escape = on_escape
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self.ok = False

    def start(self) -> bool:
        if self._thread is not None:
            return self.ok
        self._thread = threading.Thread(target=self._run, name="EscHook", daemon=True)
        self._thread.start()
        self._ready.wait(1.0)
        return self.ok

    def stop(self) -> None:
        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
        if self._thread_id:
            try:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread = None
        self._thread_id = 0
        self.ok = False

    # ---------------- 线程内部 ----------------

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        try:
            self._proc = HOOKPROC(self._callback)   # 必须保引用
            self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
            self.ok = bool(self._hook)
            if not self.ok:
                log.warning("全局 Esc 钩子安装失败，错误码 %s", ctypes.get_last_error())
        except Exception:
            log.exception("安装全局 Esc 钩子异常")
            self.ok = False
        finally:
            self._ready.set()

        if not self.ok:
            return

        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _callback(self, n_code, w_param, l_param):
        if n_code == 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == VK_ESCAPE:
                    self._on_escape()
                    return 1        # 吃掉这个 Esc，不再传给别的窗口
            except Exception:
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)
