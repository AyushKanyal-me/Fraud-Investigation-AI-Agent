import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.schemas import (
    HypothesisOutput,
    EvidenceSynthesisOutput,
    SARNarrativeOutput,
    extract_json_from_llm_text
)

def test_extract_json_from_markdown():
    raw_text = """Here is the preliminary hypothesis:
```json
{
    "preliminary_verdict": "fraud",
    "preliminary_probability": 0.85,
    "preliminary_pattern": "card_testing",
    "reasoning": "Observed multiple rapid micro-charges followed by high-dollar purchase.",
    "suggested_evidence_queries": ["card_history", "device_neighbors"]
}
```
Please let me know if you need anything else.
"""
    data = extract_json_from_llm_text(raw_text)
    assert data["preliminary_verdict"] == "fraud"
    assert data["preliminary_probability"] == 0.85

    hyp = HypothesisOutput.from_llm_text(raw_text)
    assert hyp is not None
    assert hyp.preliminary_verdict == "fraud"
    assert hyp.preliminary_probability == 0.85
    assert len(hyp.suggested_evidence_queries) == 2

def test_verdict_field_validator_normalization():
    hyp1 = HypothesisOutput(
        preliminary_verdict="Confirmed Fraud",
        preliminary_probability=0.90,
        preliminary_pattern="card_not_present_fraud",
        reasoning="Suspicious anomaly"
    )
    assert hyp1.preliminary_verdict == "fraud"

    hyp2 = HypothesisOutput(
        preliminary_verdict="legit customer purchase",
        preliminary_probability=0.10,
        preliminary_pattern="none",
        reasoning="Normal recurring payment"
    )
    assert hyp2.preliminary_verdict == "legitimate"

def test_sar_narrative_output_parsing():
    raw_sar = """```json
{
    "file_sar": true,
    "reason": "Exceeds $1,000 threshold with confirmed unauthorized fraud",
    "narrative": "On 2026-09-20, customer CUST-1001 experienced unauthorized transactions totaling $1,250.00. The activity conformed to card_not_present_fraud typology. Immediate card blocking was executed. Connected devices were flagged. FinCEN report filed in accordance with banking guidelines.",
    "subjects": ["CUST-1001", "CARD-202"],
    "activity_dates": ["2026-09-20", "2026-09-20"],
    "total_amount_usd": 1250.00
}
```"""
    sar = SARNarrativeOutput.from_llm_text(raw_sar)
    assert sar is not None
    assert sar.file_sar is True
    assert sar.total_amount_usd == 1250.00
    assert "CUST-1001" in sar.subjects

def test_evidence_synthesis_output_parsing():
    synth = EvidenceSynthesisOutput(
        final_verdict="fraud",
        calibrated_probability=0.92,
        final_pattern="card_testing",
        pattern_description="Rapid series of authorizations",
        what_changed="Evidence confirmed 3 micro-transactions preceding $250 purchase",
        stop_reason="Policy R5 card testing triggered block and SAR evaluation",
        cited_transaction_ids=["TXN-1", "TXN-2"]
    )
    assert synth.final_verdict == "fraud"
    assert synth.calibrated_probability == 0.92
