import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_config_loading():
    import config
    assert config.DATASET_DIR.exists(), f"Dataset dir {config.DATASET_DIR} must exist"
    assert (config.DATASET_DIR / "case_pack.csv").exists(), "case_pack.csv must exist"
    assert (config.DATASET_DIR / "transactions.csv").exists() or (BASE_DIR / "tests" / "fixtures" / "sample_transactions.csv").exists(), "transactions dataset or fixture must exist"
    assert (config.DATASET_DIR / "closed_cases_history.csv").exists(), "closed_cases_history.csv must exist"

def test_policy_engine_basic_evaluation():
    from agent.policy import evaluate_policy_rules, CustomerReplyOutcome
    actions, sar_file, sar_reason = evaluate_policy_rules(
        stage="initial",
        verdict="uncertain",
        fraud_prob=0.45,
        pattern="card_not_present_fraud",
        exposure_usd=100.0,
        connected_cards=[]
    )
    assert len(actions) > 0
    assert actions[0]["action"] == "VERIFY_WITH_CUSTOMER"
    assert actions[0]["route"] == "auto"

def test_fastapi_app_initialization():
    from app import app
    assert app is not None
    assert app.title == "TigerGraph Agentic Fraud Investigation API"

def test_canonical_card_mapper():
    from agent.card_identity import get_canonical_card_mapper
    mapper = get_canonical_card_mapper()
    assert mapper is not None
