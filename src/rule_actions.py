# -*- coding: utf-8 -*-
"""持仓规则判定：运行时读 Macd-Qlib-Analyzer 每天的 portfolio/rule_actions/<日期>.json，接进 A 股持仓日报。

为什么
------
2026-11-14 检查：DSA 的 LLM 评分与过去 20 日涨跌秩相关 +0.54，扣掉过去 5 / 20 日涨跌后对之后 10 日几乎没有信息
（Macd-Qlib-Analyzer scripts/dsa_score_forward.py 的「已经看过」）。而检验成立的卖出 / 不买规则（ML 后 20%、
中小盘危险信号、仓位上限、财报后等重新打分等）都在 Macd-Qlib 的规则操作单里，DSA 看不到——两封邮件可能给出
相反的结论。这里把规则判定接过来：

- 写进提示词，要求操作建议以它为准（规则看不到的新事件除外，且要写明是哪件事）；评分不因此调整；
- 总览表「今日持仓决策」加一列「规则判定」，LLM 动作与之相反时标出来；
- 不改评分、不改模型的动作（展示层只标注），由用户按规则操作单执行。

文件结构（Macd-Qlib-Analyzer scripts/portfolio_rules.py 生成，日报 CI 约北京时间 23:30 提交）
-------------------------------------------------------------------------------------
    date        这份判定用于哪个交易日开盘
    score_date  依据哪天收盘
    holdings    持仓：action = exit（卖出参考）/ conditional_exit（等重新打分）/ trim（减到上限）/ hold（不动）
    watch       关注名单：status = buy（可以买）/ wait（等重新打分）/ no_buy（不买）/ unknown（未核对）
取目录里日期最新的一份。DSA 夜里跑时它通常已经提交（score_date = 当天）；还没提交时用前一份，表下注明依据日期。

数据来源与隐私：与 src/valuation_red_flags.py 相同，只读 token（VALUATION_RED_FLAGS_TOKEN 或 MACD_QLIB_READ_TOKEN）
走 GitHub API，没有 token 时整段跳过。本地调试用 RULE_ACTIONS_FILE 指向一份本地 json。只用于 A 股。
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime
from typing import Any, Dict, Optional

from src.market_evidence import evidence_market

logger = logging.getLogger(__name__)

TOKEN_ENVS = ("VALUATION_RED_FLAGS_TOKEN", "MACD_QLIB_READ_TOKEN")
ENV_REPO = "RULE_ACTIONS_REPO"
ENV_FILE = "RULE_ACTIONS_FILE"
DEFAULT_REPO = "gong97/Macd-Qlib-Analyzer"
REMOTE_DIR = "portfolio/rule_actions"
TIMEOUT_SEC = 15
MAX_AGE_DAYS = 7  # score_date 超过一周的判定不再引用（CI 断了几天时宁可不显示）

HOLDING_LABEL = {"exit": "卖出参考", "conditional_exit": "等重新打分", "trim": "减到上限", "hold": "不动"}
WATCH_LABEL = {"buy": "可以买", "wait": "等重新打分", "no_buy": "不买", "unknown": "未核对"}
SOURCE = "Macd-Qlib 规则操作单"

_lock = threading.Lock()
_cache: Optional[Dict[str, Any]] = None
_FILE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def _token() -> str:
    for name in TOKEN_ENVS:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _fetch_remote(token: str, repo: str) -> Dict[str, Any]:
    import requests

    headers = {"Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
    listing = requests.get(f"https://api.github.com/repos/{repo}/contents/{REMOTE_DIR}",
                           headers={**headers, "Accept": "application/vnd.github+json"}, timeout=TIMEOUT_SEC)
    listing.raise_for_status()
    names = sorted(x.get("name", "") for x in listing.json() if _FILE_NAME.match(str(x.get("name", ""))))
    if not names:
        return {}
    resp = requests.get(f"https://api.github.com/repos/{repo}/contents/{REMOTE_DIR}/{names[-1]}",
                        headers={**headers, "Accept": "application/vnd.github.raw+json"}, timeout=TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def load_rule_actions() -> Dict[str, Any]:
    """{'date', 'score_date', 'stocks': {6 位代码: 条目}}；取不到返回 {}。整次运行只取一次。"""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        out: Dict[str, Any] = {}
        try:
            local = os.getenv(ENV_FILE, "").strip()
            token = _token()
            if local:
                with open(local, encoding="utf-8") as fh:
                    payload = json.load(fh)
            elif token:
                payload = _fetch_remote(token, os.getenv(ENV_REPO, "").strip() or DEFAULT_REPO)
            else:
                logger.info("[rule_actions] 未配置只读 token，跳过持仓规则判定")
                payload = {}
            if isinstance(payload, dict) and payload.get("date"):
                stocks: Dict[str, Any] = {}
                # 关注名单先放、持仓后放：同一只两边都有时以持仓判定为准
                for kind, rows in (("watch", payload.get("watch")), ("holding", payload.get("holdings"))):
                    for row in rows or []:
                        code = _digits(row.get("code")) if isinstance(row, dict) else ""
                        if code:
                            stocks[code] = {**row, "kind": kind}
                out = {"date": str(payload.get("date")), "score_date": str(payload.get("score_date") or ""),
                       "stocks": stocks}
                logger.info("[rule_actions] 已载入 %s 的规则判定（依据 %s 收盘，%d 只）",
                            out["date"], out["score_date"], len(stocks))
        except Exception as exc:  # 只是补充信息，取不到不影响日报
            logger.warning("[rule_actions] 读取失败，跳过：%s", exc)
            out = {}
        _cache = out
        return out


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def _digits(code: Any) -> str:
    m = re.search(r"\d{6}", str(code or ""))
    return m.group(0) if m else ""


def _age_days(day: str, today: Optional[date] = None) -> Optional[int]:
    try:
        d = datetime.strptime(day, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return ((today or date.today()) - d).days


def rule_action_for(code: Any, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """该股的规则判定（只 A 股）；没有、太旧时返回 None。"""
    if evidence_market(code) != "cn":
        return None
    key = _digits(code)
    payload = load_rule_actions()
    row = (payload.get("stocks") or {}).get(key) if key else None
    if not isinstance(row, dict):
        return None
    age = _age_days(payload.get("score_date", ""), today)
    if age is not None and age > MAX_AGE_DAYS:
        return None
    kind = row["kind"]
    if kind == "holding":
        value = "unknown" if row.get("data_missing") else str(row.get("action") or "hold")
        label = "未判定" if value == "unknown" else HOLDING_LABEL.get(value, value)
    else:
        value = str(row.get("status") or "unknown")
        label = WATCH_LABEL.get(value, value)
    declined = row.get("declined") if isinstance(row.get("declined"), dict) else None
    return {
        "kind": kind, "value": value, "label": label,
        "why": str(row.get("why") or ""),
        "exits": [str(x) for x in row.get("exits") or row.get("blocks") or [] if str(x).strip()],
        "hints": [str(x) for x in row.get("hints") or [] if str(x).strip()],
        "shares": row.get("shares") or row.get("max_shares") or 0,
        "limit": row.get("limit"),
        "declined": declined,
        "date": payload.get("date", ""), "score_date": payload.get("score_date", ""),
        "source": SOURCE,
    }


# 与规则判定相反的 LLM 动作（src/schemas/decision_action.py 的 action 值）
_SELLS = ("sell", "reduce")
_BUYS = ("buy", "add")


def conflicts(entry: Optional[Dict[str, Any]], action: Optional[str]) -> bool:
    """LLM 的动作和规则判定方向相反：规则不动却给卖 / 减，规则卖出 / 减到上限却给买 / 加或持有，
    关注名单规则不买 / 等重新打分却给买。等重新打分（持仓）、未判定不算冲突。"""
    if not entry or not action:
        return False
    value = entry.get("value")
    if entry.get("kind") == "holding":
        if value == "hold":
            return action in _SELLS
        if value in ("exit", "trim"):
            return action not in _SELLS
        if value == "conditional_exit":
            return action in _BUYS
        return False
    return value in ("no_buy", "wait") and action in _BUYS


def short_text(entry: Optional[Dict[str, Any]]) -> str:
    """总览表一格：判定 + 简短依据（不动且没有提示时只写「不动」）。"""
    if not entry:
        return "—"
    text = entry["label"]
    if entry["value"] in ("exit", "trim", "conditional_exit", "no_buy", "wait") and entry["exits"]:
        text += "（" + "、".join(entry["exits"][:2]) + "）"
    elif entry["value"] == "trim" and entry.get("shares"):
        text += f"（卖 {int(entry['shares']):,} 股）"
    if entry.get("declined"):
        text += "·已决定暂不执行"
    return text


def render_rule_action_prompt(entry: Optional[Dict[str, Any]]) -> str:
    """提示词段落：规则判定作为操作建议的基准。"""
    if not entry:
        return ""
    scope = "持仓" if entry["kind"] == "holding" else "关注名单（未持有）"
    lines = [f"\n### 持仓规则判定（{SOURCE}，{entry['date']} 开盘用，依据 {entry['score_date']} 收盘）",
             f"- {scope}判定：**{entry['label']}**" + (f"（{entry['why']}）" if entry["why"] else "")]
    if entry["exits"]:
        lines.append(f"- 触发的规则：{'、'.join(entry['exits'])}")
    for hint in entry["hints"][:3]:
        lines.append(f"- 提示（不改判定）：{hint}")
    if entry.get("declined"):
        lines.append(f"- 用户已于 {entry['declined'].get('date')} 决定暂不执行，复核日 {entry['declined'].get('review_date')}")
    lines.append(
        "\n> 这是按研究台账里检验成立的规则（ML 分数后 20%、中小盘危险信号、仓位上限、财报后等重新打分等）算出的判定，"
        "**操作建议以它为准**：判「不动」时不要因为技术面给减仓 / 卖出；判「卖出参考」「减到上限」时不要给买入 / 加仓；"
        "关注名单判「不买」「等重新打分」时不要给买入。只有出现规则看不到的新事件（立案、处罚、重大公告、业绩大幅变脸等）"
        "才可以给出不同的结论，并在理由里写明是哪件事。**评分按你自己的分析打，不要因为这一段调高或调低。**"
        "报告的总览表会单列「规则判定」。"
    )
    return "\n".join(lines) + "\n"


def apply_rule_action(result: Any, entry: Optional[Dict[str, Any]]) -> bool:
    """挂到 dashboard 供总览表显示；不改评分和动作。"""
    dashboard = getattr(result, "dashboard", None)
    if not entry or not isinstance(dashboard, dict):
        return False
    dashboard["rule_action"] = entry
    return True
