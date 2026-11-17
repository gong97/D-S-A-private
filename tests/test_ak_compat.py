# -*- coding: utf-8 -*-
"""akshare 改名兼容与大盘指数不给假数（2026-11-17）。

那天的 A 股复盘：CI 装到 akshare 1.20.65，8 个改名接口全部失败；指数行情回退到 Yahoo，
period='2d' 拿到当天没开盘的 NaN 行 → 上证 / 深证 nan%，只回 1 行的 → +0.00%。
"""

import os
import pickle
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_provider.ak_compat import RENAMES, ak_api  # noqa: E402
from data_provider.yfinance_fetcher import YfinanceFetcher  # noqa: E402


def _old():
    return "old"


def _new():
    return "new"


def test_prefers_new_name_and_falls_back_to_old():
    assert ak_api(SimpleNamespace(stock_zh_a_hist_em=_new, stock_zh_a_hist=_old), "stock_zh_a_hist_em")() == "new"
    assert ak_api(SimpleNamespace(stock_zh_a_hist=_old), "stock_zh_a_hist_em")() == "old"


def test_returns_plain_picklable_function():
    """_akshare_call_with_timeout 用 spawn 子进程：传进去的函数必须能 pickle，所以不能包一层闭包。"""
    fn = ak_api(SimpleNamespace(index_zh_spot_sina=_new), "index_zh_spot_sina")
    assert fn is _new
    pickle.dumps(fn)


def test_installed_akshare_has_every_name():
    ak = pytest.importorskip("akshare")
    for new in RENAMES:
        ak_api(ak, new)  # 新旧名字至少有一个，否则 AttributeError


def test_no_direct_calls_to_renamed_functions():
    pattern = re.compile(r"\bak\.(" + "|".join(map(re.escape, RENAMES.values())) + r")\s*[(,]")
    hits = []
    for folder in ("data_provider", "src", "api", "bot", "scripts"):
        for path in (REPO / folder).rglob("*.py"):
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(REPO)}:{i}: {line.strip()}")
    assert hits == [], "改用 ak_api(ak, 新名字)：\n" + "\n".join(hits)


# ---------------------------------------------------------------- Yahoo 指数不给假数

def _hist(closes):
    idx = pd.date_range("2026-11-12", periods=len(closes), freq="B", tz="Asia/Shanghai")
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1.0}, index=idx)


def _yf(hist):
    ticker = MagicMock()
    ticker.history.return_value = hist
    return SimpleNamespace(Ticker=lambda code: ticker)


def test_yahoo_skips_unopened_nan_row():
    fetcher = YfinanceFetcher()
    item = fetcher._fetch_yf_ticker_data(_yf(_hist([3600.0, 3602.57, float("nan")])), "000001.SS", "上证指数", "sh000001")
    assert item["current"] == pytest.approx(3602.57)
    assert item["change_pct"] == pytest.approx((3602.57 / 3600 - 1) * 100)


def test_yahoo_single_row_gives_nothing_instead_of_zero():
    fetcher = YfinanceFetcher()
    assert fetcher._fetch_yf_ticker_data(_yf(_hist([2292.2])), "399006.SZ", "创业板指", "sz399006") is None
    assert fetcher._fetch_yf_ticker_data(_yf(_hist([float("nan"), 2292.2])), "399006.SZ", "创业板指", "sz399006") is None


# ---------------------------------------------------------------- 复盘表不列无效行

def test_market_analyzer_drops_non_finite_indices():
    from src.market_analyzer import MarketAnalyzer

    good = {"code": "sh000300", "name": "沪深300", "current": 3976.46, "change": -3.34, "change_pct": -0.084,
            "open": 3965.9, "high": 3986.0, "low": 3942.4, "prev_close": 3979.8, "volume": 1.0, "amount": 0.0,
            "amplitude": 1.1}
    bad = dict(good, code="sh000001", name="上证指数", current=float("nan"), change_pct=float("nan"))
    analyzer = MarketAnalyzer.__new__(MarketAnalyzer)
    analyzer.region = "cn"
    analyzer.data_manager = SimpleNamespace(get_main_indices=lambda region: [bad, good])
    out = analyzer._get_main_indices()
    assert [i.name for i in out] == ["沪深300"]
