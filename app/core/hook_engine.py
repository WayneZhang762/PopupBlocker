"""全局窗口事件监听。

两个事件源：
1. SetWinEventHook（进程外钩子，不注入 DLL）——窗口创建/显示时立即通知
2. 定时补扫 EnumWindows —— 启动时已在的窗口、以及偶发漏掉的事件

两者只做最轻过滤，然后把 HWND 丢进队列，由工作线程处理。

说明：pywin32 的 win32gui 并没有暴露 SetWinEventHook，这里直接用 ctypes
调用 user32，顺带自己跑消息循环（GetMessage + DispatchMessage）。
"""
from __future__ import annotations

import ctypes
import logging
import queue
import threading
from ctypes import wintypes

import win32con
import win32gui

from . import window_probe

log = logging.getLogger(__name__)

EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
OBJID_WINDOW = 0

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WinEventProc = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,   # hWinEventHook
    wintypes.DWORD,    # event
    wintypes.HWND,     # hwnd
    wintypes.LONG,     # idObject
    wintypes.LONG,     # idChild
    wintypes.DWORD,    # idEventThread
    wintypes.DWORD,    # dwmsEventTime
)


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


user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WinEventProc,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
]
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

# 系统外壳窗口，永远不处理
SHELL_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "TaskListThumbnailWnd",
    "Windows.UI.Core.CoreWindow",
    "XamlExplorerHostIslandWindow",
    "MultitaskingViewFrame",
    "ForegroundStaging",
    "ThumbnailDeviceHelperWnd",
    "DummyDWMListenerWindow",
    "EdgeUiInputTopWndClass",
    "SysShadow",
    "IME",
    "Default IME",
    "MSCTFIME UI",
    "MSCTFIME Composition",
    "GDI+ Window",
    "tooltips_class32",
    "Windows.Internal.Shell.TabProxyWindow",
}


class _HookThread(threading.Thread):
    def __init__(self, sink: "queue.Queue[int]") -> None:
        super().__init__(daemon=True, name="SilenWindowHook")
        self.sink = sink
        self.thread_id = 0
        self.hook = None
        self._cb_ref = None
        self._ready = threading.Event()

    def run(self) -> None:
        self.thread_id = kernel32.GetCurrentThreadId()
        try:
            self._cb_ref = WinEventProc(self._on_event)  # 必须持有引用，否则被回收
            self.hook = user32.SetWinEventHook(
                EVENT_OBJECT_CREATE,
                EVENT_OBJECT_SHOW,
                None,
                self._cb_ref,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if not self.hook:
                log.error("SetWinEventHook 返回空句柄，错误码 %s", ctypes.get_last_error())
        except Exception:
            log.exception("SetWinEventHook 失败")
        finally:
            self._ready.set()

        msg = MSG()
        try:
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            log.exception("钩子消息循环异常退出")
        log.info("钩子线程退出")

    def _on_event(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        # 只关心"窗口对象本身"，忽略子控件/光标/焦点等对象
        if idObject != OBJID_WINDOW or idChild != 0 or not hwnd:
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32gui.GetAncestor(hwnd, window_probe.GA_ROOT) != hwnd:
                return
            self.sink.put_nowait(hwnd)
        except Exception:
            pass

    def stop(self) -> None:
        if self.hook:
            try:
                user32.UnhookWinEvent(self.hook)
            except Exception:
                pass
            self.hook = None
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, win32con.WM_QUIT, 0, 0)


class _SweepThread(threading.Thread):
    def __init__(self, sink: "queue.Queue[int]", interval: float = 3.0) -> None:
        super().__init__(daemon=True, name="SilenWindowSweep")
        self.sink = sink
        self.interval = interval
        self._stop = threading.Event()

    def run(self) -> None:
        self._sweep()  # 启动先补扫一次已有窗口
        while not self._stop.wait(self.interval):
            self._sweep()

    def _sweep(self) -> None:
        for hwnd in window_probe.enumerate_top_level():
            try:
                self.sink.put_nowait(hwnd)
            except Exception:
                return

    def stop(self) -> None:
        self._stop.set()


class WindowWatcher:
    """对外只暴露 start/stop 与一个 Queue。"""

    def __init__(self, sweep_interval: float = 3.0) -> None:
        self.queue: "queue.Queue[int]" = queue.Queue(maxsize=4096)
        self._hook = _HookThread(self.queue)
        self._sweep = _SweepThread(self.queue, sweep_interval)

    def start(self) -> None:
        self._hook.start()
        self._sweep.start()
        log.info("窗口监听已启动")

    def stop(self) -> None:
        self._sweep.stop()
        self._hook.stop()
        log.info("窗口监听已停止")


def is_shell_class(class_name: str) -> bool:
    return class_name in SHELL_CLASSES
