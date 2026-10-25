"""拦截记录与统计（SQLite）。"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import date, datetime, timedelta

from ..config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL    NOT NULL,
    day        TEXT    NOT NULL,
    pid        INTEGER,
    process    TEXT,
    exe_path   TEXT,
    class_name TEXT,
    title      TEXT,
    action     TEXT,
    result     TEXT,
    rule_id    TEXT,
    rule_name  TEXT,
    mode       TEXT,
    score      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_day     ON events(day);
CREATE INDEX IF NOT EXISTS idx_events_process ON events(process);
CREATE INDEX IF NOT EXISTS idx_events_rule    ON events(rule_id);
"""


class Stats:
    def __init__(self, path=DB_PATH) -> None:
        ensure_dirs()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- 写入 ----------

    def add_event(self, feat: dict, action: str, result: str,
                  rule_id: str = "", rule_name: str = "",
                  mode: str = "observe", score: int = 0) -> int:
        now = time.time()
        row = (
            now,
            date.fromtimestamp(now).isoformat(),
            feat.get("pid", 0),
            feat.get("process", ""),
            feat.get("exe_path", ""),
            feat.get("class_name", ""),
            (feat.get("title") or "")[:300],
            action,
            result,
            rule_id,
            rule_name,
            mode,
            score,
        )
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts, day, pid, process, exe_path, class_name,"
                " title, action, result, rule_id, rule_name, mode, score)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                row,
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    # ---------- 查询 ----------

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def query(self, days: int = 0, process: str = "", action: str = "",
              keyword: str = "", limit: int = 500) -> list[dict]:
        sql = ["SELECT * FROM events WHERE 1=1"]
        args: list = []
        if days > 0:
            sql.append("AND ts >= ?")
            args.append(time.time() - days * 86400)
        if process:
            sql.append("AND process = ?")
            args.append(process)
        if action:
            sql.append("AND action = ?")
            args.append(action)
        if keyword:
            sql.append("AND (title LIKE ? OR class_name LIKE ? OR process LIKE ?)")
            args += [f"%{keyword}%"] * 3
        sql.append("ORDER BY id DESC LIMIT ?")
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(" ".join(sql), args).fetchall()
        return [dict(r) for r in rows]

    def count(self, since_days: float = 0, actions: tuple[str, ...] = ()) -> int:
        sql = ["SELECT COUNT(*) FROM events WHERE 1=1"]
        args: list = []
        if since_days > 0:
            sql.append("AND ts >= ?")
            args.append(time.time() - since_days * 86400)
        if actions:
            sql.append("AND action IN (%s)" % ",".join("?" * len(actions)))
            args += list(actions)
        with self._lock:
            return int(self._conn.execute(" ".join(sql), args).fetchone()[0])

    def count_today(self) -> int:
        today = date.today().isoformat()
        with self._lock:
            return int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE day = ?", (today,)
                ).fetchone()[0]
            )

    def total(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def daily_counts(self, days: int = 7) -> list[tuple[str, int]]:
        start = date.today() - timedelta(days=days - 1)
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, COUNT(*) c FROM events WHERE day >= ? GROUP BY day",
                (start.isoformat(),),
            ).fetchall()
        bucket = {r["day"]: r["c"] for r in rows}
        out = []
        for i in range(days):
            d = start + timedelta(days=i)
            out.append((d.isoformat(), bucket.get(d.isoformat(), 0)))
        return out

    def top_rules(self, limit: int = 5) -> list[tuple[str, int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT COALESCE(NULLIF(rule_name,''), '(未命中规则)') n, COUNT(*) c"
                " FROM events GROUP BY rule_name ORDER BY c DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(r["n"], r["c"]) for r in rows]

    def top_processes(self, limit: int = 5) -> list[tuple[str, int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT COALESCE(NULLIF(process,''),'(未知)') n, COUNT(*) c"
                " FROM events GROUP BY process ORDER BY c DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(r["n"], r["c"]) for r in rows]

    def suspicious(self, limit: int = 50) -> list[dict]:
        """只观察、未拦截的候选弹窗，按进程聚合。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT process, class_name, COUNT(*) c, MAX(ts) last_ts"
                " FROM events WHERE mode='observe' AND score >= 5"
                " GROUP BY process, class_name ORDER BY c DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def purge(self, keep_days: int) -> int:
        if keep_days <= 0:
            return 0
        cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
        with self._lock:
            cur = self._conn.execute("DELETE FROM events WHERE day < ?", (cutoff,))
            self._conn.commit()
            return cur.rowcount

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM events")
            self._conn.execute("DELETE FROM sqlite_sequence WHERE name='events'")
            self._conn.commit()
