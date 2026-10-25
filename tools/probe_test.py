"""命令行诊断工具：不启动界面，直接打印窗口事件流。

用法（项目根目录）：
    .venv\\Scripts\\python.exe tools\\probe_test.py [秒数]
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import window_probe                     # noqa: E402
from app.core.classifier import Classifier            # noqa: E402
from app.core.hook_engine import WindowWatcher        # noqa: E402
from app.core.lists import Lists                      # noqa: E402
from app.core.rule_store import RuleStore             # noqa: E402


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    rules = RuleStore()
    clf = Classifier(rules=rules, lists=Lists(), own_pid=os.getpid())
    print(f"内置规则 {len(rules.builtin)} 条，用户规则 {len(rules.user)} 条")

    watcher = WindowWatcher()
    watcher.start()

    proc = None
    if "--no-notepad" not in sys.argv:
        time.sleep(0.5)
        proc = subprocess.Popen(["notepad.exe"])
        print("已启动记事本用于产生窗口事件")

    deadline = time.time() + seconds
    count = 0
    while time.time() < deadline:
        try:
            hwnd = watcher.queue.get(timeout=0.3)
        except queue.Empty:
            continue
        feat = window_probe.probe(hwnd)
        if not feat:
            continue
        d = clf.decide(feat)
        count += 1
        if count <= 40:
            print(
                f"[{feat['process'] or '?':<18}] cls={feat['class_name'][:26]:<26} "
                f"title={feat['title'][:28]:<28} area={feat['area_ratio']:.2f} "
                f"score={d.score} -> {d.action} ({d.reason})"
            )

    watcher.stop()
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    print(f"共处理 {count} 个窗口事件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
