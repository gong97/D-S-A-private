# -*- coding: utf-8 -*-
"""持仓规则判定（src/rule_actions.py）：读取、提示词、总览表一列。"""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from src import rule_actions as ra
from src.core.tiered_analysis import TieredAnalysisOutcome
from src.core.tiered_report import render_decision_summary

PAYLOAD = {
    "date": "2026-11-16",
    "score_date": "2026-11-13",
    "holdings": [
        {"code": "300750", "name": "宁德时代", "weight": 0.2045, "close": 237.7, "action": "hold", "shares": 0,
         "limit": None, "exits": [], "hints": ["近 5 日涨幅居前"], "basis": ["position-limit"],
         "why": "超过上限 20.2% 不到 100 股，不动", "data_missing": False},
        {"code": "002044", "name": "美年健康", "weight": 0.0154, "close": 4.92, "action": "exit", "shares": 4400,
         "limit": 4.82, "exits": ["ML 后 20%"], "hints": [], "basis": ["ml-bottom-veto"],
         "why": "ML 后 20%", "data_missing": False,
         "declined": {"date": "2026-11-10", "review_date": "2026-11-24"}},
        {"code": "600900", "name": "长江电力", "weight": 0.30, "close": 29.7, "action": "trim", "shares": 3000,
         "limit": 29.1, "hints": [], "basis": ["position-limit"], "why": "仓位 30.0% 超过上限 25.0%",
         "data_missing": False},  # 旧文件没有 exits 字段
    ],
    "watch": [
        {"code": "002080", "name": "中材科技", "status": "no_buy", "blocks": ["ML 后 20%"], "hints": [],
         "why": "ML 后 20%", "max_shares": 0, "limit": None},
        {"code": "300750", "name": "宁德时代", "status": "buy", "blocks": [], "hints": [], "why": "没有触发否决"},
    ],
}
TODAY = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _local_file(tmp_path, monkeypatch):
    path = tmp_path / "2026-11-16.json"
    path.write_text(json.dumps(PAYLOAD, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv(ra.ENV_FILE, str(path))
    for name in ra.TOKEN_ENVS:
        monkeypatch.delenv(name, raising=False)
    ra.reset_cache()
    yield
    ra.reset_cache()


def test_lookup_holdings_watch_and_suffixed_codes():
    e = ra.rule_action_for("300750.SZ", TODAY)
    assert (e["kind"], e["value"], e["label"]) == ("holding", "hold", "不动")  # 持仓优先于关注名单
    assert e["date"] == "2026-11-16" and e["score_date"] == "2026-11-13"
    assert ra.rule_action_for("002044", TODAY)["exits"] == ["ML 后 20%"]
    assert ra.rule_action_for("sh600900", TODAY)["label"] == "减到上限"
    w = ra.rule_action_for("002080", TODAY)
    assert (w["kind"], w["label"], w["exits"]) == ("watch", "不买", ["ML 后 20%"])
    assert ra.rule_action_for("600519", TODAY) is None
    assert ra.rule_action_for("AAPL", TODAY) is None


def test_stale_file_ignored():
    assert ra.rule_action_for("300750", date(2026, 11, 25)) is None


def test_no_token_no_file_skips(monkeypatch):
    monkeypatch.delenv(ra.ENV_FILE, raising=False)
    ra.reset_cache()
    assert ra.load_rule_actions() == {}
    assert ra.rule_action_for("300750", TODAY) is None


def test_conflicts():
    hold, sell, trim = (ra.rule_action_for(c, TODAY) for c in ("300750", "002044", "600900"))
    no_buy = ra.rule_action_for("002080", TODAY)
    assert ra.conflicts(hold, "sell") and ra.conflicts(hold, "reduce")
    assert not ra.conflicts(hold, "hold") and not ra.conflicts(hold, "watch") and not ra.conflicts(hold, "alert")
    assert ra.conflicts(sell, "hold") and ra.conflicts(sell, "buy") and not ra.conflicts(sell, "sell")
    assert ra.conflicts(trim, "watch") and not ra.conflicts(trim, "reduce")
    assert ra.conflicts(no_buy, "buy") and not ra.conflicts(no_buy, "watch")
    assert not ra.conflicts(None, "sell")


def test_prompt_section_says_rule_governs_action_not_score():
    text = ra.render_rule_action_prompt(ra.rule_action_for("002044", TODAY))
    assert "2026-11-16 开盘用，依据 2026-11-13 收盘" in text
    assert "持仓判定：**卖出参考**" in text
    assert "触发的规则：ML 后 20%" in text
    assert "操作建议以它为准" in text
    assert "评分按你自己的分析打" in text
    assert "用户已于 2026-11-10 决定暂不执行，复核日 2026-11-24" in text
    assert ra.render_rule_action_prompt(None) == ""


def test_short_text():
    assert ra.short_text(ra.rule_action_for("300750", TODAY)) == "不动"
    assert ra.short_text(ra.rule_action_for("002044", TODAY)) == "卖出参考（ML 后 20%）·已决定暂不执行"
    assert ra.short_text(ra.rule_action_for("600900", TODAY)) == "减到上限（卖 3,000 股）"
    assert ra.short_text(None) == "—"


def _lite(code, name, action, score, dashboard):
    return SimpleNamespace(
        code=code, name=name, success=True, action=action, operation_advice=None, action_label=None,
        report_type=None, report_language="zh", sentiment_score=score, guardrail_reason=None,
        downgrade_reason=None, dashboard=dashboard, market_snapshot=None, decision_type=None,
    )


def test_apply_and_summary_column():
    held = _lite("300750.SZ", "宁德时代", "hold", 50, {})
    sold = _lite("002044.SZ", "美年健康", "hold", 50, {})
    assert ra.apply_rule_action(held, ra.rule_action_for("300750", TODAY))
    assert ra.apply_rule_action(sold, ra.rule_action_for("002044", TODAY))
    summary = render_decision_summary(TieredAnalysisOutcome(lite_results=[held, sold]))
    assert "| 股票 | 规则判定 | LLM 动作 |" in summary
    assert "| 宁德时代 300750.SZ | 不动 | HOLD |" in summary
    assert "| 美年健康 002044.SZ | ⚠️ 卖出参考（ML 后 20%）·已决定暂不执行 | HOLD |" in summary
    assert summary.index("美年健康") < summary.index("宁德时代")  # 规则要卖的排最前
    assert "Macd-Qlib 规则操作单（2026-11-16 开盘用，依据 2026-11-13 收盘）" in summary


def test_summary_without_rule_actions_keeps_old_columns():
    summary = render_decision_summary(TieredAnalysisOutcome(lite_results=[_lite("300750", "宁德时代", "hold", 50, {})]))
    assert "| 股票 | 动作 | 现价 |" in summary
    assert "规则判定" not in summary
