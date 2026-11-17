"""akshare 接口改名的兼容层（2026-11-17 起）。

akshare 1.20.41 ~ 1.20.46 把一批接口改了名，旧名字一调用就抛错（「已在 1.20.46 更名为 ...」）。
requirements 里 akshare 不锁版本，CI 装到 1.20.65 后，本仓库用到的 8 个改名接口全部失败：
A 股大盘复盘的指数行情回退到 Yahoo，上证 / 深证显示 nan%、其余 +0.00%（2026-11-17 报告），
A 股日线的东财、新浪两条也每只都失败（只剩腾讯）。

用法：``ak_api(ak, "新名字")``——新名字存在就用新名字，否则用改名前的旧名字（旧版 akshare 仍可用）。
返回的就是 akshare 模块里的函数本身，不做包装：_akshare_call_with_timeout 用 spawn 子进程，函数要能 pickle。

返回的列不变（对照过 1.18.94 与 1.20.65 的源码）。参数的变化如下，调用时都已避开：
    stock_zh_a_hist_em            去掉了 timeout（本仓库不传，超时由 _akshare_call_with_timeout 管）
    stock_zh_a_hist_sina          多了 period（默认 daily）
    stock_us_hist_sina            多了 period（默认 daily）
    stock_fund_flow_individual_hist_em  第一个参数 stock → symbol（按位置传）

本仓库用到的见 RENAMES（akshare/data/renames.json，1.20.65）。
"""

from __future__ import annotations

from typing import Any, Callable

# 新名字 → 旧名字
RENAMES = {
    "stock_zh_a_hist_em": "stock_zh_a_hist",                          # 1.20.46
    "stock_zh_a_hist_sina": "stock_zh_a_daily",                       # 1.20.46
    "stock_zh_a_spot_sina": "stock_zh_a_spot",                        # 1.20.46
    "stock_hk_hist_em": "stock_hk_hist",                              # 1.20.46
    "stock_hk_spot_sina": "stock_hk_spot",                            # 1.20.46
    "stock_us_hist_sina": "stock_us_daily",                           # 1.20.46
    "index_zh_spot_sina": "stock_zh_index_spot_sina",                 # 1.20.44
    "stock_fund_flow_individual_hist_em": "stock_individual_fund_flow",  # 1.20.45
}


def ak_api(ak: Any, new: str) -> Callable:
    """akshare 的接口：新名字存在就用新名字，否则用改名前的旧名字。"""
    fn = getattr(ak, new, None)
    if fn is not None:
        return fn
    return getattr(ak, RENAMES[new])
