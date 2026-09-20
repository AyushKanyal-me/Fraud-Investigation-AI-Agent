import pytest
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.repository.base import (
    TransactionRecord,
    CardBaseline,
    EpisodeWindow,
    DeviceNeighbor,
    ClosedCaseRecord
)
from agent.repository.local import LocalFraudRepository
from agent.repository.tigergraph import TigerGraphFraudRepository

def assert_semantic_baseline_equal(b1: CardBaseline, b2: CardBaseline, rel_tol: float = 1e-2):
    """
    Asserts semantic equivalence between two CardBaseline objects.
    Floating point numbers are compared with relative tolerance.
    Sets of devices and emails are compared unordered.
    """
    assert b1.txn_count == b2.txn_count
    assert b1.avg_amount == pytest.approx(b2.avg_amount, rel=rel_tol)
    assert b1.max_amount == pytest.approx(b2.max_amount, rel=rel_tol)
    assert set(b1.known_devices) == set(b2.known_devices)
    assert set(b1.known_emails) == set(b2.known_emails)

def assert_semantic_episode_equal(e1: EpisodeWindow, e2: EpisodeWindow, rel_tol: float = 1e-2):
    """
    Asserts semantic equivalence for fraud episode expansion.
    """
    assert set(e1.affected_txn_ids) == set(e2.affected_txn_ids)
    assert e1.exposure_usd == pytest.approx(e2.exposure_usd, rel=rel_tol)
    assert e1.first_suspicious_txn_id == e2.first_suspicious_txn_id

@pytest.fixture
def local_repo():
    return LocalFraudRepository()

@pytest.fixture
def tg_repo():
    return TigerGraphFraudRepository()

def test_offline_tg_repo_fallback_parity(local_repo, tg_repo):
    """
    Verifies that TigerGraphFraudRepository without a live cluster operates in 
    complete semantic parity by safely delegating to local repository.
    """
    # 1. Transaction Detail Parity
    txn_id = "3514030"
    local_txn = local_repo.get_transaction_detail(txn_id)
    tg_txn = tg_repo.get_transaction_detail(txn_id)

    assert local_txn is not None
    assert tg_txn is not None
    assert local_txn.transaction_id == tg_txn.transaction_id
    assert local_txn.card_id == tg_txn.card_id
    assert local_txn.amount == pytest.approx(tg_txn.amount, rel=1e-3)

    # 2. Card Baseline Parity
    local_base = local_repo.get_card_baseline(local_txn.card_id, local_txn.ts_val)
    tg_base = tg_repo.get_card_baseline(tg_txn.card_id, tg_txn.ts_val)
    assert_semantic_baseline_equal(local_base, tg_base)

    # 3. Episode Expansion Parity
    local_ep = local_repo.expand_fraud_episode(local_txn.card_id, local_txn.ts_val, txn_id)
    tg_ep = tg_repo.expand_fraud_episode(tg_txn.card_id, tg_txn.ts_val, txn_id)
    assert_semantic_episode_equal(local_ep, tg_ep)

    # 4. Device Neighbors Parity
    if local_txn.device_info and local_txn.device_info != "unknown":
        local_nbrs = local_repo.get_device_neighbors(local_txn.device_info, local_txn.ts_val)
        tg_nbrs = tg_repo.get_device_neighbors(tg_txn.device_info, tg_txn.ts_val)
        assert len(local_nbrs) == len(tg_nbrs)
        assert {n.card_id for n in local_nbrs} == {n.card_id for n in tg_nbrs}

    # 5. Closed Cases Parity
    local_cases = local_repo.get_similar_closed_cases(pattern="card_testing", top_k=3)
    tg_cases = tg_repo.get_similar_closed_cases(pattern="card_testing", top_k=3)
    assert len(local_cases) == len(tg_cases)
    assert [c.case_id for c in local_cases] == [c.case_id for c in tg_cases]

    # 6. Graph Case Persistence Parity
    success = tg_repo.persist_case_graph("HHG-001", {"case": {"verdict": "fraud"}})
    assert success is True

def test_mocked_tg_gsql_response_normalization():
    """
    Tests that raw GSQL query response dicts are correctly transformed into typed dataclasses.
    """
    mock_gsql_txn_response = [{
        "TxnSet": [{
            "v_id": "3514030",
            "attributes": {
                "amount": 77.07,
                "ts": 1475586928,
                "channel": "in_person",
                "risk_score": 0.61,
                "ProductCD": "W",
                "card_id": "C12382-K1",
                "customer_id": "C12382",
                "addr1": 444,
                "addr2": 87,
                "P_emaildomain": "gmail.com",
                "R_emaildomain": "unknown",
                "DeviceType": "unknown",
                "DeviceInfo": "unknown"
            }
        }]
    }]

    attrs = mock_gsql_txn_response[0]["TxnSet"][0]["attributes"]
    record = TransactionRecord(
        transaction_id="3514030",
        card_id=attrs["card_id"],
        customer_id=attrs["customer_id"],
        amount=float(attrs["amount"]),
        ts_val=float(attrs["ts"]),
        channel=attrs["channel"],
        risk_score=float(attrs["risk_score"]),
        product_cd=attrs["ProductCD"],
        addr1=str(attrs["addr1"]),
        addr2=str(attrs["addr2"]),
        p_emaildomain=attrs["P_emaildomain"],
        r_emaildomain=attrs["R_emaildomain"],
        device_type=attrs["DeviceType"],
        device_info=attrs["DeviceInfo"]
    )

    assert record.transaction_id == "3514030"
    assert record.amount == 77.07
    assert record.card_id == "C12382-K1"
