import pytest
import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.schemas import HypothesisOutput, EvidenceSynthesisOutput, SARNarrativeOutput
from agent.token_tracker import TokenTracker

def test_hypothesis_schema_validation():
    data = {
        "preliminary_verdict": "fraud",
        "preliminary_probability": 0.85,
        "preliminary_pattern": "card_testing",
        "reasoning": "Observed rapid authorizations under $15",
        "suggested_evidence_queries": ["query:expand_fraud_episode"]
    }
    model = HypothesisOutput(**data)
    assert model.preliminary_verdict == "fraud"
    assert model.preliminary_probability == 0.85

def test_evidence_synthesis_schema_validation():
    data = {
        "final_verdict": "fraud",
        "calibrated_probability": 0.90,
        "final_pattern": "out_of_region_use",
        "pattern_description": "",
        "what_changed": "Customer denial elevated risk",
        "stop_reason": "Definitive evidence of unauthorized activity established",
        "cited_transaction_ids": ["3514030"]
    }
    model = EvidenceSynthesisOutput(**data)
    assert model.final_verdict == "fraud"
    assert "3514030" in model.cited_transaction_ids

def test_sar_narrative_schema_validation():
    data = {
        "file_sar": True,
        "reason": "Exposure > $1000",
        "narrative": "On 2016-12-05, customer card C10434-K1 was used for $1000.03. Cardholder denied authorization.",
        "subjects": ["C10434", "C10434-K1"],
        "activity_dates": ["2016-12-02", "2016-12-02"],
        "total_amount_usd": 1000.03
    }
    model = SARNarrativeOutput(**data)
    assert model.file_sar is True
    assert model.total_amount_usd == 1000.03

def test_token_tracker_accounting():
    tracker = TokenTracker()
    tracker.record_usage("hypothesis", "gemini-2.0-flash", prompt_tokens=250, completion_tokens=100, latency_s=0.5)
    tracker.record_usage("sar_generation", "gemini-2.0-flash", prompt_tokens=400, completion_tokens=200, latency_s=1.2)

    assert tracker.get_total_tokens() == 950
    assert tracker.get_total_latency() == 1.7
    summary = tracker.get_summary()
    assert summary["total_calls"] == 2
    assert summary["total_tokens"] == 950
