"""判定引擎：给定窗口特征，决定拦还是不拦。

优先级（命中即返回）：
  0 硬白名单（自身/系统外壳/系统进程/全屏主窗/用户正在用的任务栏窗口）
  1 用户白名单
  2 用户黑名单
  3 规则库（用户规则优先于内置规则，同源按 priority 降序）
  4 启发式打分（默认只记录，开启"智能拦截"才动手）
  5 放行
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .hook_engine import is_shell_class
from .lists import Lists
from .process_info import is_system_process
from .rule_store import RuleStore

SUSPICIOUS_SCORE = 5


@dataclass
class Decision:
    action: str = "allow"          # allow | hide | close | click_close
    rule_id: str = ""
    rule_name: str = ""
    reason: str = ""
    score: int = 0
    source: str = ""               # hardwall | whitelist | blacklist | rule | heuristic | default

    @property
    def blocked(self) -> bool:
        return self.action != "allow"


@dataclass
class Classifier:
    rules: RuleStore
    lists: Lists
    own_pid: int = 0
    smart_block: bool = False
    allow_score: int = SUSPICIOUS_SCORE
    stats: dict = field(default_factory=dict)

    # ---------- 启发式 ----------

    def heuristic_score(self, feat: dict) -> tuple[int, list[str]]:
        """启发式打分。

        关键判据是「这个窗口像不像用户主动打开的应用窗口」：
        正常应用主窗口一定有任务栏按钮、一定在前台或刚被切换过来；
        广告弹窗通常没有任务栏按钮、不在前台、面积小。
        """
        score = 0
        why: list[str] = []
        exnames = set(feat.get("exstyle_names") or [])
        has_taskbar = bool(feat.get("has_taskbar_button"))

        if not has_taskbar:
            score += 3
            why.append("任务栏没有按钮")
        if "WS_EX_TOOLWINDOW" in exnames and "WS_EX_APPWINDOW" not in exnames:
            score += 2
            why.append("标记为工具窗口")
        if not feat.get("is_foreground"):
            score += 1
            why.append("不在前台")
        if feat.get("area_ratio", 1) < 0.4:
            score += 1
            why.append("窗口面积小")
        cls = feat.get("class_name") or ""
        if not has_taskbar and (cls.startswith("Afx:") or cls in ("#32770", "SunAwtDialog", "TApplication")):
            score += 1
            why.append("常见对话框类")
        age = feat.get("process_age_s", -1)
        if 0 <= age <= 180 and not has_taskbar:
            score += 1
            why.append("进程刚启动")
        # 有任务栏按钮的窗口基本可判定为用户自己的应用窗口，压分
        if has_taskbar:
            score -= 2
        return max(0, score), why

    # ---------- 主判定 ----------

    def decide(self, feat: dict) -> Decision:
        pid = feat.get("pid", 0)
        proc = (feat.get("process") or "").lower()
        # 路径统一成反斜杠，避免大小写/斜杠差异导致白名单失效
        path = (feat.get("exe_path") or "").lower().replace("/", "\\")
        cls = feat.get("class_name") or ""

        # 0. 硬白名单
        if pid and self.own_pid and pid == self.own_pid:
            return Decision(reason="自身进程", source="hardwall")
        if is_shell_class(cls):
            return Decision(reason="系统外壳窗口", source="hardwall")
        if not pid:
            return Decision(reason="无法获取进程", source="hardwall")
        if not proc:
            return Decision(reason="进程信息缺失", source="hardwall")
        if is_system_process(proc) and (path.startswith("c:\\windows\\") or not path):
            return Decision(reason="系统进程", source="hardwall")
        # 系统目录里的程序一律不碰（含 UWP 宿主、系统设置等）
        if path.startswith("c:\\windows\\") or path.startswith("c:\\program files\\windowsapps\\"):
            return Decision(reason="系统目录程序", source="hardwall")
        if feat.get("area_ratio", 0) >= 0.9:
            return Decision(reason="全屏/主窗口", source="hardwall")
        if feat.get("is_foreground") and feat.get("has_taskbar_button"):
            return Decision(reason="用户正在使用的窗口", source="hardwall")

        # 1. 用户白名单
        wl = self.lists.whitelisted(feat)
        if wl:
            return Decision(reason=f"白名单：{wl.get('value','')}", source="whitelist")

        # 2. 用户黑名单
        bl = self.lists.blacklisted(feat)
        if bl:
            return Decision(
                action=bl.get("action", "hide") or "hide",
                rule_id=bl.get("id", ""),
                rule_name=f"黑名单：{bl.get('value','')}",
                reason="命中黑名单",
                source="blacklist",
            )

        # 3. 规则库
        for rule in self.rules.enabled_rules():
            try:
                if self.rules.matches(rule, feat):
                    return Decision(
                        action=rule.get("action", "hide") or "hide",
                        rule_id=rule.get("id", ""),
                        rule_name=rule.get("name", ""),
                        reason=f"命中规则（{rule.get('vendor','') or rule.get('source','')}）",
                        source="rule",
                        score=self.heuristic_score(feat)[0],
                    )
            except Exception:
                continue

        # 4. 启发式
        score, why = self.heuristic_score(feat)
        if score >= self.allow_score:
            if self.smart_block:
                return Decision(
                    action="hide",
                    rule_name="智能识别",
                    reason="启发式判定为可疑弹窗：" + "、".join(why),
                    score=score,
                    source="heuristic",
                )
            return Decision(
                action="allow",
                rule_name="智能识别(仅记录)",
                reason="可疑弹窗，未开启智能拦截：" + "、".join(why),
                score=score,
                source="heuristic",
            )

        return Decision(reason="未命中任何规则", score=score, source="default")

    # ---------- 给"测试规则"功能用 ----------

    def explain(self, feat: dict) -> list[dict]:
        out = []
        for rule in self.rules.all_rules():
            try:
                hit = self.rules.matches(rule, feat)
            except Exception:
                hit = False
            out.append(
                {
                    "id": rule.get("id", ""),
                    "name": rule.get("name", ""),
                    "vendor": rule.get("vendor", ""),
                    "source": rule.get("source", ""),
                    "enabled": rule.get("enabled", True),
                    "action": rule.get("action", ""),
                    "matched": hit,
                }
            )
        return out
