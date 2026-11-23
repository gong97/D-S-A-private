# -*- coding: utf-8 -*-
"""看多理由的历史检验标注（src/tested_signals.py）：例句取自 2026-10-14 日报。"""

from types import SimpleNamespace

from src.tested_signals import annotate, annotate_tested_signals, tested_notes


def test_known_invalid_reasons_are_annotated() -> None:
    assert tested_notes("均线多头排列（MA5>MA10>MA20）") == ["均线多头在 10 日上没有优势"]
    assert tested_notes("RSI超卖存在技术反弹要求") == ["跌得多的股票之后不反弹"]
    assert tested_notes("缩量回调洗盘特征明显，高管曾有增持动作") == [
        "缩量回踩的缩量条件历史上方向相反", "股东 / 高管增持之后不跑赢",
    ]
    assert tested_notes("近5日主力资金整体呈现净流入状态") == ["主力净流入之后 10 日反而多数跑输"]
    assert tested_notes("中报归母净利润同比大增68.17%") == ["已公布的业绩在公告窗口内就被消化，之后没有漂移"]


def test_platform_retest_reasons_are_annotated() -> None:
    """platform-retest（2026-11-19）：A 股回踩之后跑输，美股没有方向；回踩均线不在此列。"""
    cn = "平台突破后回踩守住，之后 10 / 20 日反而跑输"
    assert tested_notes("放量突破平台后回踩确认，上沿支撑有效") == [cn, "突破确认之后没有优势"]
    assert tested_notes("回踩前高不破") == [cn]
    assert tested_notes("回踩确认完成，量能温和") == [cn]
    assert tested_notes("缩量回踩前期平台") == ["缩量回踩的缩量条件历史上方向相反", cn]
    # 回踩均线（技巧一）不标这一条
    assert tested_notes("回踩20日线获支撑") == []
    assert tested_notes("回踩确认MA20支撑") == []
    assert tested_notes("回踩前高不破", market="us") == ["突破后回踩在美股没有方向信息"]


def test_head_and_shoulders_reasons_are_annotated() -> None:
    """head-shoulders（2026-11-20）：头肩底突破之后跑输（看多理由标反）；头肩顶跌破之后跑输（看空理由标成立）。"""
    bottom = "头肩底突破颈线之后 10 / 20 日反而跑输"
    top = "头肩顶跌破颈线之后 10 / 20 日确实跑输，看空成立"
    assert tested_notes("日线构筑头肩底，放量突破颈线") == [bottom, "突破确认之后没有优势"]
    assert tested_notes("倒头肩形态右肩企稳") == [bottom]
    assert tested_notes("周线头肩顶形态成型，跌破颈线", bearish=True) == [top]
    assert tested_notes("头肩顶跌破颈线且均线空头排列", bearish=True) == [
        top, "空头排列 / 跌破均线之后不继续跑输，不作减仓或卖出依据"]
    # 只写「跌破颈线」不标；头肩顶不出现在看多规则里
    assert tested_notes("跌破颈线", bearish=True) == []
    assert tested_notes("头肩顶形态成型") == []
    # 美股没有单独检验头肩顶；头肩底沿用美股形态规则
    assert tested_notes("头肩顶形态成型", market="us", bearish=True) == []
    assert tested_notes("头肩底形态", market="us") == ["形态与突破在美股没有方向信息"]


def test_double_top_bottom_reasons_are_annotated() -> None:
    """double-top-bottom（2026-11-20）：双底提到就标反；双顶只在跌破时标成立，没跌破的不标。"""
    bottom = "双底（W 底）突破颈线之后 10 / 20 日反而跑输"
    top = "双顶跌破颈线之后 20 日确实跑输（10 日不显著），看空成立"
    assert tested_notes("日线双底成型，放量突破颈线") == [bottom, "突破确认之后没有优势"]
    assert tested_notes("W底右侧企稳") == [bottom]
    assert tested_notes("构筑W型底") == [bottom]
    assert tested_notes("双顶跌破颈线", bearish=True) == [top]
    assert tested_notes("M头形态已破位", bearish=True) == [top]
    assert tested_notes("股价跌破双顶颈线", bearish=True) == [top]
    # 没跌破的双顶形状没有方向信息，不标
    assert tested_notes("疑似构筑双顶", bearish=True) == []
    # 美股：双底沿用美股形态规则；双顶没检验过
    assert tested_notes("双底形态", market="us") == ["形态与突破在美股没有方向信息"]
    assert tested_notes("双顶跌破颈线", market="us", bearish=True) == []


def test_triangle_reasons_are_annotated() -> None:
    """pennant-triangle / flag-ascending-triangle（2026-11-22）：收敛 / 对称三角形、上升三角形各自标反；
    三角旗、旗形不成立，下降三角形没测过，都没有专门标注。"""
    tri = "收敛三角形向上突破之后 10 / 20 日反而跑输"
    asc = "上升三角形向上突破之后 10 / 20 日反而跑输"
    brk = "突破确认之后没有优势"
    assert tested_notes("日线收敛三角形整理末端，放量突破上轨") == [tri, brk]
    assert tested_notes("对称三角形即将选择方向") == [tri]
    assert tested_notes("股价处于三角形整理中") == [tri]
    assert tested_notes("三角收敛接近尾声") == [tri]
    # 上升三角形单独一条，不落进收敛三角形
    assert tested_notes("上升三角形整理") == [asc]
    assert tested_notes("构筑上升三角形，放量突破水平压力线") == [asc, brk]
    assert tested_notes("上升三角整理接近尾声") == [asc]
    # 三角旗（含「上升三角旗」）、旗形不成立，只按「突破」标；下降三角形没测过
    assert tested_notes("三角旗形向上突破") == [brk]
    assert tested_notes("上升三角旗形向上突破") == [brk]
    assert tested_notes("下降三角形整理") == []
    # 美股沿用美股形态规则（两种三角形美股都不复现）
    assert tested_notes("收敛三角形整理", market="us") == ["形态与突破在美股没有方向信息"]
    assert tested_notes("上升三角形整理", market="us") == ["形态与突破在美股没有方向信息"]


def test_valuation_and_neutral_facts_are_not_annotated() -> None:
    assert tested_notes("经营现金流稳健，估值处于合理区间") == []
    assert tested_notes("公司发布关于回购公司股份进展的公告") == []
    assert annotate("估值合理且中报业绩增速稳健") == "估值合理且中报业绩增速稳健"


def test_annotation_is_idempotent() -> None:
    once = annotate("RSI超卖技术反弹需求")
    assert once.endswith("〔历史检验：跌得多的股票之后不反弹〕")
    assert annotate(once) == once


def test_annotate_dashboard_fields_only_model_checks_with_tick() -> None:
    result = SimpleNamespace(dashboard={
        "signal_attribution": {"strongest_bullish_signal": "均线多头排列", "strongest_bearish_signal": "缩量"},
        "intelligence": {"positive_catalysts": ["利好1：近5日主力资金净流入", "利好2：回购进展"]},
        "battle_plan": {"action_checklist": [
            "✅ 【程序】高位过热（乖离过大/放量急拉）：未触发",
            "✅ 【模型】量价关系健康，缩量回调表明抛压较轻",
            "⚠️ 【模型】缩量回调但量能不足",
        ]},
    })
    changed = annotate_tested_signals(result, "zh")

    d = result.dashboard
    assert set(changed) == {"signal_attribution.strongest_bullish_signal", "intelligence.positive_catalysts",
                            "battle_plan.action_checklist"}
    assert "〔历史检验" in d["signal_attribution"]["strongest_bullish_signal"]
    assert d["signal_attribution"]["strongest_bearish_signal"] == "缩量"          # 看空理由不标
    assert "〔历史检验" in d["intelligence"]["positive_catalysts"][0]
    assert d["intelligence"]["positive_catalysts"][1] == "利好2：回购进展"
    checks = d["battle_plan"]["action_checklist"]
    assert "〔历史检验" not in checks[0]                                         # 【程序】项不标
    assert "〔历史检验" in checks[1]
    assert "〔历史检验" not in checks[2]                                         # ⚠️ 项已在提示风险


def test_non_chinese_reports_are_left_alone() -> None:
    result = SimpleNamespace(dashboard={"signal_attribution": {"strongest_bullish_signal": "均线多头排列"}})
    assert annotate_tested_signals(result, "en") == []


def test_bearish_technical_reasons_are_annotated() -> None:
    """看空的技术理由（2026-11-14 起）：例句取自 2026-11-13 日报。"""
    note = "空头排列 / 跌破均线之后不继续跑输，不作减仓或卖出依据"
    assert tested_notes("均线呈空头排列，短期趋势偏弱", bearish=True) == [note]
    assert tested_notes("股价跌破MA20支撑", bearish=True) == [note]
    assert tested_notes("跌破 60 日均线，趋势转弱", bearish=True) == [note]
    assert tested_notes("三季报增收不增利，毛利率连续下行", bearish=True) == []
    assert tested_notes("均线呈空头排列", market="us", bearish=True) == ["美股均线 / 趋势止损不成立，不作减仓或卖出依据"]
    # 看多规则不受影响
    assert tested_notes("均线呈空头排列") == []


def test_bearish_fields_and_warning_checks_are_annotated() -> None:
    result = SimpleNamespace(dashboard={
        "signal_attribution": {"strongest_bullish_signal": "回购进展", "strongest_bearish_signal": "均线空头排列"},
        "battle_plan": {"action_checklist": [
            "❌ 【模型】空头排列，趋势走弱",
            "⚠️ 【模型】三季报经营现金流偏弱",
            "❌ 【程序】近期高管减持：未触发",
        ]},
    })
    changed = annotate_tested_signals(result)
    dash = result.dashboard
    assert "signal_attribution.strongest_bearish_signal" in changed
    assert dash["signal_attribution"]["strongest_bearish_signal"].endswith("不作减仓或卖出依据〕")
    assert dash["signal_attribution"]["strongest_bullish_signal"] == "回购进展"
    checks = dash["battle_plan"]["action_checklist"]
    assert checks[0].endswith("不作减仓或卖出依据〕")
    assert checks[1] == "⚠️ 【模型】三季报经营现金流偏弱"
    assert checks[2] == "❌ 【程序】近期高管减持：未触发"
