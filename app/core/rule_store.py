"""规则库：内置规则 + 用户自定义规则 + 启用状态，含匹配函数。

规则结构：
{
  "id": "builtin-wps-news",
  "name": "WPS 资讯弹窗",
  "vendor": "WPS",
  "source": "builtin" | "user",
  "enabled": true,
  "priority": 80,                # 越大越优先
  "action": "hide" | "close" | "click_close",
  "note": "说明",
  "match": { ...条件... }
}

match 条件（全部 AND，同 key 的列表内部 OR）：
  process        ["wps.exe", "360*.exe"]      exe 名，支持 * 通配
  path_contains  ["\\kingsoft\\"]             路径包含任一
  class_re       ["^KWPS"]                    类名正则，任一命中
  title_re       "资讯|热点"                  标题正则（字符串或列表）
  title_not_re   "升级|错误"                   命中则本规则不成立
  exstyle_has    ["WS_EX_TOOLWINDOW"]         必须全部具备
  exstyle_lacks  ["WS_EX_APPWINDOW"]          一个都不能有
  no_owner       true                         无 owner 窗口
  not_foreground true                         非当前前台进程
  min_area_ratio 0.0 / max_area_ratio 0.5     窗口面积占屏幕比例区间
  title_not_empty true
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from ..config import BUILTIN_RULES_PATH, USER_RULES_PATH, ensure_dirs

RULE_STATE_PATH = USER_RULES_PATH.parent / "rule_state.json"

_ACTION_LABEL = {"hide": "隐藏", "close": "关闭", "click_close": "点关闭按钮"}


def action_label(action: str) -> str:
    return _ACTION_LABEL.get(action, action)


class RuleStore:
    def __init__(self) -> None:
        self.builtin: list[dict] = []
        self.user: list[dict] = []
        self.disabled: set[str] = set()
        self._re_cache: dict[str, re.Pattern] = {}
        self.load()

    # ---------- 读写 ----------

    def load(self) -> None:
        self.builtin = self._read_json(BUILTIN_RULES_PATH, [])
        for r in self.builtin:
            r["source"] = "builtin"
            r.setdefault("enabled", True)
            r.setdefault("priority", 60)
            r.setdefault("action", "hide")
        self.user = self._read_json(USER_RULES_PATH, [])
        for r in self.user:
            r["source"] = "user"
            r.setdefault("enabled", True)
            r.setdefault("priority", 200)
            r.setdefault("action", "hide")
        state = self._read_json(RULE_STATE_PATH, {})
        self.disabled = set(state.get("disabled", []))

    @staticmethod
    def _read_json(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default
        except Exception:
            return default

    def save_user(self) -> None:
        ensure_dirs()
        USER_RULES_PATH.write_text(
            json.dumps(self.user, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save_state(self) -> None:
        ensure_dirs()
        RULE_STATE_PATH.write_text(
            json.dumps({"disabled": sorted(self.disabled)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- 合并视图 ----------

    def all_rules(self) -> list[dict]:
        out = []
        for r in self.builtin + self.user:
            rr = dict(r)
            rr["enabled"] = r["id"] not in self.disabled and bool(r.get("enabled", True))
            out.append(rr)
        out.sort(key=lambda x: (-int(x.get("priority", 0)), x.get("name", "")))
        return out

    def enabled_rules(self) -> list[dict]:
        return [r for r in self.all_rules() if r["enabled"]]

    def get(self, rule_id: str) -> dict | None:
        for r in self.all_rules():
            if r["id"] == rule_id:
                return r
        return None

    def set_enabled(self, rule_id: str, enabled: bool) -> None:
        # 用户规则直接改文件里的 enabled；内置规则记到 disabled 列表
        if any(r["id"] == rule_id for r in self.user):
            for r in self.user:
                if r["id"] == rule_id:
                    r["enabled"] = enabled
            self.save_user()
        if enabled:
            self.disabled.discard(rule_id)
        else:
            self.disabled.add(rule_id)
        self.save_state()

    # ---------- 用户规则增删改 ----------

    def add_user(self, rule: dict) -> None:
        rule = dict(rule)
        rule["source"] = "user"
        rule.setdefault("priority", 200)
        self.user.append(rule)
        self.save_user()

    def update_user(self, rule: dict) -> None:
        for i, r in enumerate(self.user):
            if r["id"] == rule["id"]:
                new = dict(rule)
                new["source"] = "user"
                self.user[i] = new
                self.save_user()
                return
        self.add_user(rule)

    def delete_user(self, rule_id: str) -> bool:
        before = len(self.user)
        self.user = [r for r in self.user if r["id"] != rule_id]
        if len(self.user) != before:
            self.save_user()
            return True
        return False

    # ---------- 导入导出 ----------

    def export_rules(self, path: Path, include_builtin: bool = False) -> int:
        rules = self.user if not include_builtin else self.all_rules()
        payload = [
            {k: v for k, v in r.items() if k not in ("source",)}
            for r in rules
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(payload)

    def import_rules(self, path: Path) -> int:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = [raw]
        added = 0
        existing = {r["id"] for r in self.user}
        for r in raw:
            if not isinstance(r, dict) or "id" not in r:
                continue
            rule = dict(r)
            rule["source"] = "user"
            rule.setdefault("enabled", True)
            rule.setdefault("priority", 200)
            rule.setdefault("action", "hide")
            rule.setdefault("match", {})
            if rule["id"] in existing:
                rule["id"] = f"{rule['id']}-imported"
            self.user.append(rule)
            existing.add(rule["id"])
            added += 1
        if added:
            self.save_user()
        return added

    # ---------- 匹配 ----------

    def _re(self, pattern: str) -> re.Pattern:
        pat = self._re_cache.get(pattern)
        if pat is None:
            pat = re.compile(pattern, re.IGNORECASE)
            self._re_cache[pattern] = pat
        return pat

    def matches(self, rule: dict, feat: dict) -> bool:
        return self.match_dict(rule.get("match") or {}, feat)

    def match_dict(self, match: dict, feat: dict) -> bool:
        if not match:
            return False

        proc = (feat.get("process") or "").lower()
        path = (feat.get("exe_path") or "").lower()
        cls = feat.get("class_name") or ""
        title = (feat.get("title") or "").strip()
        exnames = set(feat.get("exstyle_names") or [])

        if "process" in match:
            pats = match["process"]
            if isinstance(pats, str):
                pats = [pats]
            if not any(fnmatch.fnmatch(proc, p.lower()) for p in pats):
                return False

        if "path_contains" in match:
            pats = match["path_contains"]
            if isinstance(pats, str):
                pats = [pats]
            if not any(p.lower() in path for p in pats):
                return False

        if "class_re" in match:
            pats = match["class_re"]
            if isinstance(pats, str):
                pats = [pats]
            if not any(self._re(p).search(cls) for p in pats):
                return False

        if "title_re" in match:
            pats = match["title_re"]
            if isinstance(pats, str):
                pats = [pats]
            if not any(self._re(p).search(title) for p in pats):
                return False

        if "title_not_re" in match:
            pats = match["title_not_re"]
            if isinstance(pats, str):
                pats = [pats]
            if any(self._re(p).search(title) for p in pats):
                return False

        if "title_not_empty" in match and match["title_not_empty"] and not title:
            return False

        if "exstyle_has" in match:
            if not all(name in exnames for name in match["exstyle_has"]):
                return False

        if "exstyle_lacks" in match:
            if any(name in exnames for name in match["exstyle_lacks"]):
                return False

        if "no_owner" in match and bool(match["no_owner"]) != (not feat.get("owner_hwnd")):
            return False

        if "not_foreground" in match and bool(match["not_foreground"]) != (not feat.get("is_foreground")):
            return False

        if "min_area_ratio" in match and feat.get("area_ratio", 0) < match["min_area_ratio"]:
            return False

        if "max_area_ratio" in match and feat.get("area_ratio", 0) > match["max_area_ratio"]:
            return False

        return True


def describe_match(rule: dict) -> str:
    """把 match 翻成一句人话，供表格里显示。"""
    m = rule.get("match") or {}
    parts: list[str] = []
    if "process" in m:
        v = m["process"]
        parts.append("进程 " + "/".join(v if isinstance(v, list) else [v]))
    if "class_re" in m:
        v = m["class_re"]
        parts.append("类名 " + "/".join(v if isinstance(v, list) else [v]))
    if "title_re" in m:
        v = m["title_re"]
        parts.append("标题 " + "/".join(v if isinstance(v, list) else [v]))
    if "path_contains" in m:
        v = m["path_contains"]
        parts.append("路径含 " + "/".join(v if isinstance(v, list) else [v]))
    if m.get("exstyle_has"):
        parts.append("样式 " + "+".join(m["exstyle_has"]))
    if m.get("not_foreground"):
        parts.append("非前台")
    if m.get("no_owner"):
        parts.append("无主窗")
    return " · ".join(parts) if parts else "（无条件）"
