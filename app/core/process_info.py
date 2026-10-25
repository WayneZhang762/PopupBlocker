"""PID -> 进程名 / 完整路径 / 启动时间，带缓存。

优先 QueryFullProcessImageNameW（比 psutil 更少 AccessDenied），
psutil 只用来补父进程与创建时间。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_OpenProcess = _kernel32.OpenProcess
_OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_OpenProcess.restype = wintypes.HANDLE
_QueryFullProcessImageNameW = _kernel32.QueryFullProcessImageNameW
_QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_QueryFullProcessImageNameW.restype = wintypes.BOOL
_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL


def exe_path(pid: int) -> str:
    if not pid:
        return ""
    handle = _OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if _QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        _CloseHandle(handle)


class _Cache:
    def __init__(self, ttl: float = 30.0, max_items: int = 512) -> None:
        self.ttl = ttl
        self.max_items = max_items
        self._d: dict[int, tuple[float, dict]] = {}

    def get(self, pid: int) -> dict | None:
        item = self._d.get(pid)
        if item and time.time() - item[0] < self.ttl:
            return item[1]
        return None

    def put(self, pid: int, value: dict) -> None:
        if len(self._d) > self.max_items:
            self._d.clear()
        self._d[pid] = (time.time(), value)


_cache = _Cache()


def describe(pid: int) -> dict:
    """返回 {pid, process, exe_path, parent, age_s, elevated_guess}。"""
    if not pid:
        return {
            "pid": 0,
            "process": "",
            "exe_path": "",
            "parent": "",
            "age_s": -1,
        }
    hit = _cache.get(pid)
    if hit is not None:
        return hit

    path = exe_path(pid)
    name = path.rsplit("\\", 1)[-1] if path else ""
    parent = ""
    age = -1.0
    if not name:
        try:
            import psutil

            p = psutil.Process(pid)
            name = p.name()
            try:
                path = p.exe()
            except Exception:
                path = ""
            try:
                parent = psutil.Process(p.ppid()).name()
            except Exception:
                parent = ""
            age = max(0.0, time.time() - p.create_time())
        except Exception:
            pass
    else:
        try:
            import psutil

            p = psutil.Process(pid)
            try:
                parent = psutil.Process(p.ppid()).name()
            except Exception:
                parent = ""
            age = max(0.0, time.time() - p.create_time())
        except Exception:
            pass

    info = {
        "pid": pid,
        "process": name,
        "exe_path": path,
        "parent": parent,
        "age_s": round(age, 1),
    }
    _cache.put(pid, info)
    return info


def is_system_process(name: str) -> bool:
    return name.lower() in {
        "explorer.exe",
        "sihost.exe",
        "taskhostw.exe",
        "dwm.exe",
        "winlogon.exe",
        "csrss.exe",
        "svchost.exe",
        "conhost.exe",
        "runtimebroker.exe",
        "searchhost.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
        "textinputhost.exe",
        "ctfmon.exe",
        "securityhealthsystray.exe",
        "applicationframehost.exe",
        "systemsettings.exe",
        "searchapp.exe",
        "searchhost.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
        "lockapp.exe",
        "useroobebroker.exe",
    }
