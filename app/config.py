"""全局配置：路径、常量、用户设置读写。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "静窗"
APP_ID = "SilenWindow"
VERSION = "1.0.0"


def _base_dir() -> Path:
    """打包后以 exe 所在目录为根，开发时以项目根目录为根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SILENWINDOW_DATA_DIR") or (BASE_DIR / "data"))
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "blocker.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
USER_RULES_PATH = DATA_DIR / "user_rules.json"
LOG_FILE = LOG_DIR / "silenwindow.log"


def _resource(*parts: str) -> Path:
    """打包后资源可能在 _MEIPASS 里，这里挨个试。"""
    candidates = [APP_DIR.joinpath(*parts)]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass).joinpath("app", *parts))
        candidates.append(Path(meipass).joinpath(*parts))
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


BUILTIN_RULES_PATH = _resource("data", "builtin_rules.json")

DEFAULT_SETTINGS: dict = {
    "engine_mode": "observe",      # observe=只观察不拦截 / block=实际拦截
    "minimize_to_tray": True,
    "start_minimized": False,
    "autostart": False,
    "notify_on_block": True,
    "retention_days": 30,
    "smart_block": False,          # 启发式自动拦截
    "log_level": "INFO",
}


def ensure_dirs() -> None:
    for d in (DATA_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


class Settings:
    """极简设置容器，dict 语义 + 自动落盘。"""

    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self.path = path
        self._data: dict = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULT_SETTINGS:
                        self._data[k] = v
        except FileNotFoundError:
            self.save()
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()

    def as_dict(self) -> dict:
        return dict(self._data)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)


settings = Settings()


def is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def setup_logging(level: str = "INFO") -> None:
    import logging
    from logging.handlers import RotatingFileHandler

    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if root.handlers:
        return
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
