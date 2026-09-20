import pytest
import os
import sys
import copy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.validator import validate_case_invariants

@pytest.fixture
def valid_fraud_case():
    return {
        "case_id": "HHG-001",
        "case": {
            "status": "closed_fraud",
            "verdict": "fraud",
            "fraud_probability": 0.90,
            "pattern": "out_of_region_use",
            "pattern_description": "",
            "affected_txn_ids": ["3514030"],
            "first_suspicious_txn_id": "3514030",
            "connected_card_ids": [],
            "connected_device_profiles": [],
            "exposure_usd": 77.07,
            "evidence": [
                {
                    "claim": "Transaction in region 444 differs from 204",
                    "source": "graph",
                    "ref": "query:region_anomaly",
                    "entity_ids": ["3514030"]
                }
            ],
            "similar_prior_cases": ["CC-1066"],
            "summary": "Investigation confirmed out_of_region_use fraud.",
            "written_to_graph": True,
            "graph_case_id": "CASE-HHG-001"
        },
        "evidence_requests": [
            {
                "type": "customer_validation",
                "asked_after_step": 7,
                "assumed_response": "Customer states they did not authorize purchase."
            }
        ],
        "next_best_actions": {
            "initial": [
                {
                    "action": "VERIFY_WITH_CUSTOMER",
                    "route": "auto",
                    "reason": "R1: Verify with customer"
                }
            ],
            "final": [
                {
                    "action": "BLOCK_CARD",
                    "route": "L1",
                    "reason": "R2: Customer denied"
                },
                {
                    "action": "CREATE_CASE",
                    "route": "auto",
                    "reason": "R2: Open case"
                }
            ],
            "what_changed": "Customer denial confirmed fraud."
        },
        "sar": {
            "file": False,
            "reason": "Exposure is under $1000",
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0.0,
            "activity_dates": []
        },
        "stop_reason": "Definitive evidence of unauthorized activity established.",
        "tool_calls": 8,
        "tokens": 1200,
        "latency_s": 1.5
    }

@pytest.fixture
def valid_legitimate_case():
    return {
        "case_id": "HHG-003",
        "case": {
            "status": "closed_legitimate",
            "verdict": "legitimate",
            "fraud_probability": 0.05,
            "pattern": "none",
            "pattern_description": "",
            "affected_txn_ids": [],
            "first_suspicious_txn_id": "",
            "connected_card_ids": [],
            "connected_device_profiles": [],
            "exposure_usd": 0.0,
            "evidence": [
                {
                    "claim": "Matches recurring subscription pattern",
                    "source": "graph",
                    "ref": "query:card_history",
                    "entity_ids": ["3530164"]
                }
            ],
            "similar_prior_cases": [],
            "summary": "Legitimate transaction confirmed.",
            "written_to_graph": True,
            "graph_case_id": "CASE-HHG-003"
        },
        "evidence_requests": [],
        "next_best_actions": {
            "initial": [
                {
                    "action": "CREATE_CASE",
                    "route": "auto",
                    "reason": "R7: Recurring subscription dispute"
                },
                {
                    "action": "VERIFY_WITH_CUSTOMER",
                    "route": "auto",
                    "reason": "R7: Verify terms"
                },
                {
                    "action": "WARN_CUSTOMER",
                    "route": "auto",
                    "reason": "R7: Remind terms"
                }
            ],
            "final": [
                {
                    "action": "ALLOW_TRANSACTION",
                    "route": "auto",
                    "reason": "R3: Confirmed authorized"
                },
                {
                    "action": "CLOSE_NO_FRAUD",
                    "route": "auto",
                    "reason": "R3: Closed as legitimate"
                }
            ],
            "what_changed": "Resolved as recurring billing dispute."
        },
        "sar": {
            "file": False,
            "reason": "Legitimate transaction",
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0.0,
            "activity_dates": []
        },
        "stop_reason": "Cardholder confirmed subscription.",
        "tool_calls": 5,
        "tokens": 800,
        "latency_s": 0.9
    }

def test_valid_case_passes(valid_fraud_case, valid_legitimate_case):
    is_valid, errors, warnings = validate_case_invariants(valid_fraud_case, case_id_expected="HHG-001")
    assert is_valid, f"Expected valid fraud case, got errors: {errors}"
    assert len(errors) == 0

    is_valid_legit, errors_legit, _ = validate_case_invariants(valid_legitimate_case, case_id_expected="HHG-003")
    assert is_valid_legit, f"Expected valid legit case, got errors: {errors_legit}"
    assert len(errors_legit) == 0

def test_missing_top_level_field(valid_fraud_case):
    bad_case = copy.deepcopy(valid_fraud_case)
    del bad_case["sar"]
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("Missing required top-level field: 'sar'" in e for e in errors)

def test_legitimate_verdict_with_non_empty_affected_txns(valid_legitimate_case):
    bad_case = copy.deepcopy(valid_legitimate_case)
    bad_case["case"]["affected_txn_ids"] = ["3530164"]
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("affected_txn_ids must be empty" in e for e in errors)

def test_legitimate_verdict_with_non_zero_exposure(valid_legitimate_case):
    bad_case = copy.deepcopy(valid_legitimate_case)
    bad_case["case"]["exposure_usd"] = 49.00
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("exposure_usd must be 0" in e for e in errors)

def test_sar_file_consistency_with_actions(valid_fraud_case):
    # Case has sar.file = False, but we inject FILE_REPORT into final actions -> violation
    bad_case = copy.deepcopy(valid_fraud_case)
    bad_case["next_best_actions"]["final"].append({
        "action": "FILE_REPORT",
        "route": "L2",
        "reason": "Test"
    })
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("must agree with presence of 'FILE_REPORT'" in e for e in errors)

def test_approval_route_enforcement(valid_fraud_case):
    # BLOCK_CARD with exposure <= 2500 assigned route 'L2' instead of 'L1'
    bad_case = copy.deepcopy(valid_fraud_case)
    bad_case["case"]["exposure_usd"] = 100.0
    bad_case["next_best_actions"]["final"][0] = {
        "action": "BLOCK_CARD",
        "route": "L2",
        "reason": "Incorrect route"
    }
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("Approval route mismatch for action 'BLOCK_CARD'" in e for e in errors)

def test_sar_narrative_and_dates_required_when_file_true(valid_fraud_case):
    # sar.file = True, but dates format is invalid or narrative empty
    bad_case = copy.deepcopy(valid_fraud_case)
    bad_case["next_best_actions"]["final"].append({
        "action": "FILE_REPORT",
        "route": "L2",
        "reason": "High exposure"
    })
    bad_case["sar"] = {
        "file": True,
        "reason": "Exposure > 1000",
        "narrative": "",
        "subjects": [],
        "total_amount_usd": 0.0,
        "activity_dates": ["invalid-date"]
    }
    is_valid, errors, _ = validate_case_invariants(bad_case)
    assert not is_valid
    assert any("sar.narrative' is required" in e for e in errors)
    assert any("sar.subjects' must contain" in e for e in errors)
    assert any("sar.total_amount_usd' must be greater than 0" in e for e in errors)
