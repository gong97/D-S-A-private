# -*- coding: utf-8 -*-
"""给模型写的看多理由（以及 2026-11-14 起看空的技术理由）标注历史检验结论：已检验过、在 A 股上没有优势或方向相反的理由，后面加一句说明。

为什么
------
2026-10-15 检查日报：24 只持仓的「最强看多信号」「利好催化」里反复出现缩量洗盘、RSI 超卖反弹、
均线多头排列、中报业绩大增、主力资金净流入——这些在 Macd-Qlib-Analyzer 的研究台账里都检验过，
没有一条站得住，有的方向还是反的。提示词早已写明资金流「只作描述」，模型仍把它列为利好，
所以由程序在展示层标注，不靠提示词约束。

只标注、不删除、不改分：理由本身可能是对公司的正确描述，标注说的是「把它当成买入理由，历史上
没有优势」。估值偏低不标注——估值因子是台账里确认成立的（value-factor）。

规则与出处（Macd-Qlib-Analyzer research_ledger.jsonl 的条目 id）
--------------------------------------------------------------
    缩量回调 / 洗盘        skill-rules-revision：技巧一的缩量条件方向相反（t −4.36）
    RSI 超卖 / 超跌反弹     reversal-flow-robustness：跌得最多的 20% 之后不反弹
    均线多头排列            skill-rules-revision：趋势向上在短周期偏负（t −1.85）
    主力资金流入            capital-flow：净流入最强的之后 10 日反而多数跑输
    业绩大增 / 超预期       earnings-drift：业绩意外在披露窗口内就被消化，之后没有漂移
    增持                    insider-buying：股东 / 高管增持之后不跑赢
    高股息                  dividend-yield：高股息组不显著跑赢（t 1.46）
    突破                    pattern-breakout：突破确认没有优势
    突破后回踩 / 回踩确认   platform-retest（2026-11-19）：平台突破后回踩守住、次日买入，之后 10 / 20 日两段都显著跑输；
                            回踩均线（技巧一、缩量回踩扫描）不在此列，没有单独的标注

美股（2026-10-17 起）用另一套规则（US-stock-macd-analyzer research_ledger.jsonl），只标美股检验无效的理由：
    缩量回调 / 洗盘、均线多头   six-skill-bonus-us：技术加分项在标普 500 上没有优势
    MACD 金叉 / 底背离          macd-buy-trigger-us、six-skill-bonus-us（B4）
    突破 / 形态                 pattern-detectors-us：29 个形态都没有方向信息
    突破后回踩                  platform-retest-us：回踩之后不跑赢也不跑输（A 股是跑输）
    估值便宜                    value-portfolio-us：最便宜一组不跑赢（A 股估值因子成立，所以 A 股不标）
不标：增持（美股内部人买入之后跑赢，方向与 A 股相反）、超跌反弹（标普 500 跌得多的反而反弹，事后选股偏乐观）、
业绩超预期（前瞻复核中）、资金流和高股息（美股没测过）。
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Pattern, Tuple

# 平台 / 前高突破后的回踩（不含回踩均线：那是技巧一，单独没有检验结论可标）
_RETEST_PATTERN = re.compile(
    r"(?:突破|平台|箱体|前高|颈线)[^，。；]{0,10}回(?:踩|抽)"
    r"|回(?:踩|抽)[^，。；]{0,6}(?:前高|平台|箱体|颈线|突破位|突破点)"
    r"|回(?:踩|抽)(?![^，。；]{0,6}(?:均线|MA|ma|日线))(?:确认|不破|企稳|有效|获支撑|支撑)"
)
_RULES: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"缩量(?:回调|回踩|洗盘|整理|企稳|调整)|洗盘"), "缩量回踩的缩量条件历史上方向相反"),
    (_RETEST_PATTERN, "平台突破后回踩守住，之后 10 / 20 日反而跑输"),
    (re.compile(r"超卖|超跌|反弹(?:需求|动能|要求|空间)"), "跌得多的股票之后不反弹"),
    (re.compile(r"多头排列|均线多头|多头均线"), "均线多头在 10 日上没有优势"),
    (re.compile(r"(?:主力|北向|大单)?资金[^，。；]{0,6}(?:净流入|流入|抢筹)"), "主力净流入之后 10 日反而多数跑输"),
    (re.compile(r"(?:净利润|归母|业绩|营收|利润)[^，。；]{0,10}(?:大增|高增|爆发|超预期|翻倍|大幅增长|高速增长)|超预期"),
     "已公布的业绩在公告窗口内就被消化，之后没有漂移"),
    (re.compile(r"增持"), "股东 / 高管增持之后不跑赢"),
    (re.compile(r"高股息|股息率"), "高股息组不显著跑赢"),
    (re.compile(r"突破"), "突破确认之后没有优势"),
)
_US_RULES: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"缩量(?:回调|回踩|洗盘|整理|企稳|调整)|洗盘"), "缩量回踩在美股大盘股上没有优势"),
    (re.compile(r"多头排列|均线多头|多头均线"), "均线多头在美股大盘股上没有优势"),
    (re.compile(r"MACD[^，。；]{0,6}(?:金叉|底背离|背离)|金叉|底背离"), "MACD 金叉 / 底背离在美股没有优势"),
    (_RETEST_PATTERN, "突破后回踩在美股没有方向信息"),
    (re.compile(r"突破|头肩底|双底|W底|杯柄|旗形|三角形整理"), "形态与突破在美股没有方向信息"),
    (re.compile(r"低估|估值(?:偏低|较低|便宜|有吸引力|具吸引力|吸引)|便宜"), "美股估值最便宜一组不跑赢"),
)
# 看空的技术理由（2026-11-14 起）：11-13 那次 33 只里 31 只「观望」，理由几乎都是空头排列；
# signal_log 9-30~11-13 里模型评分与过去 20 日涨跌秩相关 +0.54，扣掉过去 5 / 20 日涨跌后对之后 10 日
# 几乎没有信息（秩相关 0.23 → 0.03）。看空这一侧同样没有检验支持：
#     A 股  reversal-flow-robustness：跌得最多的 20% 之后不反弹也不继续跑输；momentum-12-1：输家组 t 0.35；
#           risk-rules：200 日均线 / 回撤止损不改善结果
#     美股  risk-rules-us：200 日均线 / 回撤止损不成立
_BEARISH_PATTERN = re.compile(
    r"空头排列|均线空头|空头均线|弱势空头|跌破(?:关键)?(?:均线|MA\d+|\d+\s*日(?:均)?线)"
    r"|(?:趋势|走势)(?:走弱|转弱|向下|恶化)|下降(?:趋势|通道)"
)
_BEARISH_RULES: Tuple[Tuple[Pattern[str], str], ...] = (
    (_BEARISH_PATTERN, "空头排列 / 跌破均线之后不继续跑输，不作减仓或卖出依据"),
)
_US_BEARISH_RULES: Tuple[Tuple[Pattern[str], str], ...] = (
    (_BEARISH_PATTERN, "美股均线 / 趋势止损不成立，不作减仓或卖出依据"),
)
_TAG_OPEN, _TAG_CLOSE = "〔历史检验：", "〕"
_MAX_NOTES = 2


def tested_notes(text: Any, market: Optional[str] = "cn", *, bearish: bool = False) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    if bearish:
        rules = _US_BEARISH_RULES if market == "us" else _BEARISH_RULES
    else:
        rules = _US_RULES if market == "us" else _RULES
    notes: List[str] = []
    for pattern, note in rules:
        if pattern.search(text) and note not in notes:
            notes.append(note)
    return notes[:_MAX_NOTES]


def annotate(text: Any, market: Optional[str] = "cn", *, bearish: bool = False) -> Any:
    """命中规则就在末尾加〔历史检验：…〕；已标注过、或不命中，原样返回。bearish=True 用看空规则。"""
    if not isinstance(text, str) or _TAG_OPEN in text:
        return text
    notes = tested_notes(text, market, bearish=bearish)
    if not notes:
        return text
    return f"{text.rstrip()} {_TAG_OPEN}{'；'.join(notes)}{_TAG_CLOSE}"


def annotate_tested_signals(result: Any, language: str = "zh", market: Optional[str] = "cn") -> List[str]:
    """就地标注 dashboard 里的看多理由和看空的技术理由，返回改动过的字段名。只做中文（规则是中文关键词）。

    market：'cn' 用 A 股规则，'us' 用美股规则，其他市场（没有检验）不标注。
    """
    if language not in (None, "", "zh") or market not in ("cn", "us"):
        return []
    dashboard = getattr(result, "dashboard", None)
    if not isinstance(dashboard, dict):
        return []
    changed: List[str] = []

    attribution = dashboard.get("signal_attribution")
    if isinstance(attribution, dict):
        old = attribution.get("strongest_bullish_signal")
        new = annotate(old, market)
        if new != old:
            attribution["strongest_bullish_signal"] = new
            changed.append("signal_attribution.strongest_bullish_signal")
        old = attribution.get("strongest_bearish_signal")
        new = annotate(old, market, bearish=True)
        if new != old:
            attribution["strongest_bearish_signal"] = new
            changed.append("signal_attribution.strongest_bearish_signal")

    intel = dashboard.get("intelligence")
    catalysts = intel.get("positive_catalysts") if isinstance(intel, dict) else None
    if isinstance(catalysts, list):
        new_list = [annotate(item, market) for item in catalysts]
        if new_list != catalysts:
            intel["positive_catalysts"] = new_list
            changed.append("intelligence.positive_catalysts")

    battle = dashboard.get("battle_plan")
    checklist = battle.get("action_checklist") if isinstance(battle, dict) else None
    if isinstance(checklist, list):
        # 只标模型自己写的【模型】项：✅ 项按看多规则，⚠️/❌ 项按看空的技术规则（空头排列、跌破均线等）；
        # 【程序】项本身就是检验口径
        def _checklist_item(item: Any) -> Any:
            if not isinstance(item, str) or "【模型】" not in item:
                return item
            head = item.lstrip()
            if head.startswith("✅"):
                return annotate(item, market)
            if head.startswith(("⚠️", "⚠", "❌")):
                return annotate(item, market, bearish=True)
            return item

        new_list = [_checklist_item(item) for item in checklist]
        if new_list != checklist:
            battle["action_checklist"] = new_list
            changed.append("battle_plan.action_checklist")
    return changed
