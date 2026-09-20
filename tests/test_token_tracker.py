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

    assert tracker.get_total_tokens() == (420 + 85) + (950 + 210) + (600 + 180)
    assert tracker.get_total_latency() == pytest.approx(0.45 + 0.82 + 0.65, rel=1e-3)

    summary = tracker.get_summary()
    assert summary["total_calls"] == 3
    assert summary["total_prompt_tokens"] == 420 + 950 + 600
    assert summary["total_completion_tokens"] == 85 + 210 + 180
    assert len(summary["records"]) == 3
    assert summary["records"][0]["step"] == "hypothesis_generation"
