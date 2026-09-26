import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.token_tracker import TokenTracker, TokenUsageRecord

def test_token_tracker_per_case_recording():
    tracker = TokenTracker()

    tracker.record_usage(
        step_name="hypothesis_generation",
        model_name="gemini-2.0-flash",
        prompt_tokens=420,
        completion_tokens=85,
        latency_s=0.45
    )

    tracker.record_usage(
        step_name="evidence_synthesis",
        model_name="gemini-2.0-flash",
        prompt_tokens=950,
        completion_tokens=210,
        latency_s=0.82
    )

    tracker.record_usage(
        step_name="sar_narrative_drafting",
        model_name="gemini-2.0-flash",
        prompt_tokens=600,
        completion_tokens=180,
        latency_s=0.65
    )

    summary = tracker.get_summary()
    assert summary["total_calls"] == 3
    assert summary["total_prompt_tokens"] == 420 + 950 + 600
    assert summary["total_completion_tokens"] == 85 + 210 + 180
    assert len(summary["records"]) == 3
    assert summary["records"][0]["step"] == "hypothesis_generation"

def test_graph_token_tracker_wiring():
    from agent.graph import FraudInvestigationGraph
    from agent.schemas import HypothesisOutput
    from unittest.mock import MagicMock

    graph = FraudInvestigationGraph()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"preliminary_verdict": "fraud", "preliminary_probability": 0.9, "preliminary_pattern": "card_testing", "reasoning": "testing detected"}'
    mock_response.usage_metadata.prompt_token_count = 120
    mock_response.usage_metadata.candidates_token_count = 35
    mock_client.models.generate_content.return_value = mock_response

    graph.client = mock_client
    res = graph._call_gemini_structured("test prompt", HypothesisOutput, step_name="test_step")
    assert res is not None
    assert graph.token_tracker.get_total_tokens() == 155
    summary = graph.token_tracker.get_summary()
    assert summary["total_calls"] == 1
    assert summary["records"][0]["step"] == "test_step"


