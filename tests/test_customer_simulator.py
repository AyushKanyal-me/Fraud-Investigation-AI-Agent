import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.simulator import CustomerSimulator
from agent.policy import CustomerReplyOutcome

@pytest.fixture
def simulator():
    return CustomerSimulator(llm_caller=None)

def test_customer_report_trigger(simulator):
    outcome, inq_type, text, provenance = simulator.simulate_inquiry(
        customer_id="C08623",
        card_id="C08623-K2",
        flagged_txn_id="3530164",
        txn_amt=49.00,
        product_cd="W",
        trigger_type="customer_report",
        risk_score=0.85
    )
    assert outcome == CustomerReplyOutcome.DENIED_UNAUTHORIZED
    assert inq_type == "customer_validation"
    assert "denies" in text.lower() or "not authorize" in text.lower()
    assert provenance["source"] == "simulator"
    assert "request_id" in provenance

def test_recurring_dispute_simulation(simulator):
    outcome, inq_type, text, provenance = simulator.simulate_inquiry(
        customer_id="C08623",
        card_id="C08623-K2",
        flagged_txn_id="3530164",
        txn_amt=49.00,
        product_cd="W",
        trigger_type="customer_report",
        risk_score=0.85,
        is_recurring_dispute=True
    )
    assert outcome == CustomerReplyOutcome.RECURRING_DISPUTE
    assert inq_type == "customer_validation"
    assert "subscription" in text.lower() or "recurring" in text.lower()

def test_card_testing_step_up_failure(simulator):
    outcome, inq_type, text, provenance = simulator.simulate_inquiry(
        customer_id="C11923",
        card_id="C11923-K2",
        flagged_txn_id="3583368",
        txn_amt=131.30,
        product_cd="C",
        trigger_type="risk_score",
        risk_score=0.90,
        is_card_testing=True
    )
    assert outcome == CustomerReplyOutcome.STEP_UP_FAILED
    assert inq_type == "step_up_auth"
    assert "step-up" in text.lower() or "authentication" in text.lower()

def test_low_risk_legitimate_simulation(simulator):
    outcome, inq_type, text, provenance = simulator.simulate_inquiry(
        customer_id="C04570",
        card_id="C04570-K1",
        flagged_txn_id="3450629",
        txn_amt=100.09,
        product_cd="W",
        trigger_type="risk_score",
        risk_score=0.52,
        is_new_device=False,
        is_region_anomaly=False
    )
    assert outcome == CustomerReplyOutcome.CONFIRMED_LEGITIMATE
    assert inq_type == "customer_validation"
    assert "authorized" in text.lower() or "validates" in text.lower()
