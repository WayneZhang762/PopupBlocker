"""引擎：把「窗口事件 → 特征 → 判定 → 动作 → 记录」串起来。

钩子线程只负责把 HWND 塞进队列；真正的工作全部在这个后台线程里做，
避免拖慢系统事件投递。
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from ..config import Settings
from . import action, window_probe
from .classifier import SUSPICIOUS_SCORE, Classifier
from .hook_engine import WindowWatcher
from .lists import Lists
from .rule_store import RuleStore
from .stats import Stats

log = logging.getLogger(__name__)

DEDUPE_TTL = 45.0


class Engine(QObject):
    windowEvent = Signal(dict)     # 一条判定结果（同时也是入库的那条）
    statsChanged = Signal()
    stateChanged = Signal(str)     # "block" / "observe" / "paused"

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.rules = RuleStore()
        self.lists = Lists()
        self.stats = Stats()
        self.classifier = Classifier(
            rules=self.rules,
            lists=self.lists,
            own_pid=os.getpid(),
            smart_block=bool(settings.get("smart_block")),
            allow_score=SUSPICIOUS_SCORE,
        )
        self._watcher: WindowWatcher | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._seen: dict[int, float] = {}
        self._paused = False

    # ---------------- 生命周期 ----------------

    def start(self) -> None:
        self._stop.clear()
        self._watcher = WindowWatcher()
        self._watcher.start()
        self._worker = threading.Thread(target=self._run, name="SilenWindowWorker", daemon=True)
        self._worker.start()
        days = int(self.settings.get("retention_days") or 0)
        if days:
            try:
                self.stats.purge(days)
            except Exception:
                log.exception("清理历史记录失败")
        self.stateChanged.emit(self.state)

    def stop(self) -> None:
        self._stop.set()
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2)

    # ---------------- 状态 ----------------

    @property
    def state(self) -> str:
        if self._paused:
            return "paused"
        return str(self.settings.get("engine_mode") or "observe")

    def set_mode(self, mode: str) -> None:
        if mode in ("block", "observe"):
            self.settings.set("engine_mode", mode)
            self._paused = False
            self.stateChanged.emit(self.state)

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self.stateChanged.emit(self.state)

    def reload_config(self) -> None:
        self.classifier.smart_block = bool(self.settings.get("smart_block"))

    def reload_rules(self) -> None:
        self.rules.load()
        self.lists.load()

    # ---------------- 工作线程 ----------------

    def _run(self) -> None:
        q = self._watcher.queue if self._watcher else None
        if q is None:
            return
        while not self._stop.is_set():
            try:
                hwnd = q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._handle(hwnd)
            except Exception:
                log.exception("处理窗口事件失败 hwnd=%s", hwnd)

    def _dedupe(self, hwnd: int) -> bool:
        now = time.time()
        last = self._seen.get(hwnd)
        if last is not None and now - last < DEDUPE_TTL:
            return True
        if len(self._seen) > 2000:
            self._seen = {k: v for k, v in self._seen.items() if now - v < DEDUPE_TTL}
        self._seen[hwnd] = now
        return False

    def _handle(self, hwnd: int) -> None:
        feat = window_probe.probe(hwnd)
        if not feat:
            return
        if self._dedupe(hwnd):
            return

        decision = self.classifier.decide(feat)
        mode = self.state
        result = ""

        if decision.blocked and mode == "block":
            result = action.apply_action(feat, decision.action)
        elif decision.blocked:
            result = "observed"

        interesting = decision.blocked or decision.score >= SUSPICIOUS_SCORE
        if not interesting:
            return

        record = {
            "hwnd": hwnd,
            "ts": feat["ts"],
            "time": time.strftime("%H:%M:%S", time.localtime(feat["ts"])),
            "day": time.strftime("%Y-%m-%d", time.localtime(feat["ts"])),
            "pid": feat["pid"],
            "process": feat["process"],
            "exe_path": feat["exe_path"],
            "class_name": feat["class_name"],
            "title": feat["title"],
            "action": decision.action,
            "result": result,
            "rule_id": decision.rule_id,
            "rule_name": decision.rule_name or decision.reason,
            "mode": mode,
            "score": decision.score,
            "reason": decision.reason,
        }
        try:
            self.stats.add_event(
                feat,
                action=decision.action,
                result=result,
                rule_id=decision.rule_id,
                rule_name=record["rule_name"],
                mode=mode,
                score=decision.score,
            )
        except Exception:
            log.exception("写入记录失败")
        self.windowEvent.emit(record)
        self.statsChanged.emit()

    # ---------------- 手动分析（给"规则测试"用） ----------------

    def analyze_hwnd(self, hwnd: int) -> dict | None:
        return window_probe.probe(hwnd)
