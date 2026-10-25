"""黑白名单存储。

条目结构：
{"id":"...", "type":"process"|"window", "field":"process"|"path"|"class"|"title",
 "value":"wps.exe" 或正则, "note":""}
白名单命中 -> 永不拦截；黑名单命中 -> 直接按 action 拦截。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..config import DATA_DIR, ensure_dirs

LISTS_PATH = DATA_DIR / "lists.json"


class Lists:
    def __init__(self, path: Path = LISTS_PATH) -> None:
        self.path = path
        self.whitelist: list[dict] = []
        self.blacklist: list[dict] = []
        self._re: dict[str, re.Pattern] = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.whitelist = raw.get("whitelist", []) or []
                self.blacklist = raw.get("blacklist", []) or []
        except FileNotFoundError:
            self.save()
        except Exception:
            pass

    def save(self) -> None:
        ensure_dirs()
        self.path.write_text(
            json.dumps(
                {"whitelist": self.whitelist, "blacklist": self.blacklist},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def add(self, kind: str, entry: dict) -> dict:
        entry = dict(entry)
        entry.setdefault("id", f"{kind[:1]}-{int(time.time() * 1000)}")
        target = self.whitelist if kind == "whitelist" else self.blacklist
        target.append(entry)
        self.save()
        return entry

    def remove(self, kind: str, entry_id: str) -> bool:
        target = self.whitelist if kind == "whitelist" else self.blacklist
        before = len(target)
        target[:] = [e for e in target if e.get("id") != entry_id]
        if len(target) != before:
            self.save()
            return True
        return False

    # ---------- 匹配 ----------

    def _match(self, entry: dict, feat: dict) -> bool:
        field = entry.get("field", "process")
        value = str(entry.get("value", "")).strip()
        if not value:
            return False
        if field == "process":
            return (feat.get("process") or "").lower() == value.lower()
        if field == "path":
            return value.lower() in (feat.get("exe_path") or "").lower()
        if field == "class":
            pat = self._re.get(value)
            if pat is None:
                pat = re.compile(value, re.IGNORECASE)
                self._re[value] = pat
            return bool(pat.search(feat.get("class_name") or ""))
        if field == "title":
            pat = self._re.get(value)
            if pat is None:
                pat = re.compile(value, re.IGNORECASE)
                self._re[value] = pat
            return bool(pat.search(feat.get("title") or ""))
        return False

    def whitelisted(self, feat: dict) -> dict | None:
        for e in self.whitelist:
            if self._match(e, feat):
                return e
        return None

    def blacklisted(self, feat: dict) -> dict | None:
        for e in self.blacklist:
            if self._match(e, feat):
                return e
        return None

    def add_from_window(self, kind: str, feat: dict, field: str = "process",
                        action: str = "hide") -> dict:
        value = {
            "process": feat.get("process", ""),
            "path": feat.get("exe_path", ""),
            "class": feat.get("class_name", ""),
            "title": re.escape((feat.get("title") or "")[:60]),
        }.get(field, "")
        entry = {
            "type": "process" if field in ("process", "path") else "window",
            "field": field,
            "value": value,
            "note": f"{feat.get('process','')} / {feat.get('class_name','')}",
            "action": action,
        }
        return self.add(kind, entry)
