# -*- coding: utf-8 -*-
"""个股分析的 LLM 请求要带超时（2026-11-18）。

11-17 美东上午 Gemini 大量 503 high demand，一次请求卡住不返回（LiteLLM 默认 6000 秒），
把整次 45 分钟的 A 股运行拖到被取消。
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from src.analyzer import GeminiAnalyzer
from src.config import Config


def _analyze_and_capture(**cfg_extra):
    analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
    analyzer._router = None
    analyzer._litellm_available = True
    analyzer._config_override = SimpleNamespace(
        generation_backend="codex_cli", generation_fallback_backend="", generation_backend_timeout_seconds=300,
        generation_backend_max_output_bytes=1048576, generation_backend_max_concurrency=1,
        local_cli_backend_max_concurrency=1, litellm_model="", gemini_request_delay=0, report_language="zh",
        llm_temperature=0.7, report_integrity_enabled=False, report_integrity_retry=0, **cfg_extra)
    response = json.dumps({"sentiment_score": 50, "trend_prediction": "震荡", "operation_advice": "持有",
                           "analysis_summary": "测试"})
    seen = {}

    def fake_call(prompt, generation_config, **kwargs):
        seen.update(generation_config)
        return response, "codex_cli", {"usage_available": False, "usage_source": "unavailable"}

    with patch.object(analyzer, "get_generation_backend_config_error", return_value=None), \
         patch.object(analyzer, "is_available", return_value=True), \
         patch.object(analyzer, "_get_analysis_system_prompt", return_value="system"), \
         patch.object(analyzer, "_get_skill_prompt_sections", return_value=(None, None, True)), \
         patch.object(analyzer, "_format_prompt", return_value="prompt"), \
         patch.object(analyzer, "_call_litellm", side_effect=fake_call), \
         patch.object(analyzer, "_build_market_snapshot", return_value={}), \
         patch("src.analyzer.persist_llm_usage"):
        analyzer.analyze({"code": "600519", "stock_name": "贵州茅台"})
    return seen


def test_analysis_call_carries_configured_timeout():
    assert _analyze_and_capture(llm_analysis_timeout_sec=90.0)["timeout"] == 90.0


def test_analysis_call_defaults_to_120s_when_config_lacks_field():
    assert _analyze_and_capture()["timeout"] == 120.0


def test_config_reads_env_with_floor(monkeypatch):
    monkeypatch.setenv("LLM_ANALYSIS_TIMEOUT_SEC", "75")
    assert Config._load_from_env().llm_analysis_timeout_sec == 75.0
    monkeypatch.setenv("LLM_ANALYSIS_TIMEOUT_SEC", "3")
    assert Config._load_from_env().llm_analysis_timeout_sec == 10.0
    monkeypatch.delenv("LLM_ANALYSIS_TIMEOUT_SEC")
    assert Config._load_from_env().llm_analysis_timeout_sec == 120.0
