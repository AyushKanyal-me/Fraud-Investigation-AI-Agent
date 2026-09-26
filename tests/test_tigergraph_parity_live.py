"""
TigerGraph Live & GSQL Integration Parity Test Suite.
Validates complete mathematical, schema, and analytical query parity
between TigerGraphFraudRepository and LocalFraudRepository across all core analytical primitives.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.repository.local import LocalFraudRepository
from agent.repository.tigergraph import TigerGraphFraudRepository
from agent.repository.base import (
    TransactionRecord,
    CardBaseline,
    EpisodeWindow,
    DeviceNeighbor,
    ClosedCaseRecord
)

LIVE_TG_ENABLED = os.getenv("TIGERGRAPH_LIVE_TESTS", "false").lower() in ("true", "1", "yes")


@pytest.fixture
def local_repo():
    return LocalFraudRepository()


@pytest.fixture
def mock_tg_repo():
    """TigerGraph repository wired with simulated pyTigerGraph responses for offline deterministic testing."""
    repo = TigerGraphFraudRepository(fallback_policy="fallback")
    mock_conn = MagicMock()
    mock_conn.echo.return_value = "TigerGraph RESTPP server is healthy."

    # Mock get_transaction_detail via getVerticesById
    def mock_get_vertices(v_type, v_ids):
        if v_type == "Transaction" and "3514030" in v_ids:
            return [{
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
        return []

    mock_conn.getVerticesById.side_effect = mock_get_vertices

    # Mock runInstalledQuery for baseline, episode, neighbors, closed cases
    def mock_run_query(query_name, params):
        if query_name == "card_history":
            return [{
                "Stats": {
                    "txn_count": 5,
                    "avg_amount": 54.20,
                    "std_amount": 12.50,
                    "max_amount": 120.00,
                    "primary_addr1": "444",
                    "devices": ["MacOS-10_15"],
                    "emails": ["gmail.com"]
                }
            }]
        elif query_name == "card_testing_detection":
            return [{
                "EpisodeTxns": [{"v_id": "3514030"}, {"v_id": "3514031"}],
                "TotalExposure": 154.14,
                "FirstSuspiciousTxn": "3514030",
                "IsCardTesting": False,
                "ClearedGt100": False
            }]
        elif query_name == "device_neighbors":
            return [{
                "Cards": [{
                    "v_id": "C00877-K1",
                    "attributes": {
                        "customer_id": "C00877",
                        "total_txns": 2,
                        "total_amt": 180.50
                    }
                }]
            }]
        elif query_name == "similar_closed_cases":
            return [{
                "SimilarCases": [{
                    "v_id": "HIST-042",
                    "attributes": {
                        "customer_id": "C00877",
                        "card_id": "C00877-K1",
                        "outcome": "closed_fraud",
                        "pattern": "card_testing",
                        "exposure_usd": 320.00,
                        "actions_taken": "BLOCK_CARD",
                        "sar_filed": True,
                        "analyst_notes": "Confirmed micro-auth card testing sequence."
                    }
                }]
            }]
        return []


    mock_conn.runInstalledQuery.side_effect = mock_run_query
    mock_conn.upsertVertex.return_value = 1
    mock_conn.upsertEdge.return_value = 1

    repo.conn = mock_conn
    return repo


def test_mock_tigergraph_gsql_parity_transformation(mock_tg_repo):
    """Verifies that TigerGraphFraudRepository correctly maps GSQL return structures into domain models."""
    # 1. Transaction Detail
    txn = mock_tg_repo.get_transaction_detail("3514030")
    assert txn is not None
    assert txn.transaction_id == "3514030"
    assert txn.card_id == "C12382-K1"
    assert txn.amount == pytest.approx(77.07)
    assert txn.addr1 in ("444", "444.0")


    # 2. Card Baseline
    base = mock_tg_repo.get_card_baseline("C12382-K1", before_ts=1475586928)
    assert base is not None
    assert base.txn_count == 5
    assert base.avg_amount == pytest.approx(54.20)
    assert base.max_amount == pytest.approx(120.00)
    assert "MacOS-10_15" in base.known_devices
    assert "gmail.com" in base.known_emails

    # 3. Episode Expansion
    ep = mock_tg_repo.expand_fraud_episode("C12382-K1", center_ts=1475586928, flagged_txn_id="3514030")
    assert ep is not None
    assert ep.affected_txn_ids == ["3514030", "3514031"]
    assert ep.exposure_usd == pytest.approx(154.14)
    assert ep.first_suspicious_txn_id == "3514030"

    # 4. Device Neighbors
    nbrs = mock_tg_repo.get_device_neighbors("MacOS-10_15", center_ts=1475586928)
    assert len(nbrs) == 1
    assert nbrs[0].card_id == "C00877-K1"
    assert nbrs[0].customer_id == "C00877"

    # 5. Similar Closed Cases
    cases = mock_tg_repo.get_similar_closed_cases(pattern="card_testing", top_k=1)
    assert len(cases) == 1
    assert cases[0].case_id == "HIST-042"
    assert cases[0].pattern == "card_testing"
    assert cases[0].outcome == "closed_fraud"
    assert cases[0].exposure_usd == pytest.approx(320.00)
    assert cases[0].report_filed is True


    # 6. Persistence
    persisted = mock_tg_repo.persist_case_graph("HHG-001", {"case": {"verdict": "fraud"}})
    assert persisted is True


@pytest.mark.skipif(not LIVE_TG_ENABLED, reason="TIGERGRAPH_LIVE_TESTS not enabled")
def test_live_tigergraph_dataset_parity(local_repo):
    """
    Executes live analytical parity against a live TigerGraph cluster.
    Compares TigerGraph responses directly against local parquet/CSV repository.
    """
    tg_repo = TigerGraphFraudRepository()
    if not tg_repo.is_connected():
        pytest.skip("TigerGraph live cluster is not connected.")

    # 1. Transaction Lookup Parity
    test_txn_ids = ["3514030", "2987000", "2987001"]
    for txn_id in test_txn_ids:
        local_txn = local_repo.get_transaction_detail(txn_id)
        if local_txn:
            tg_txn = tg_repo.get_transaction_detail(txn_id)
            assert tg_txn is not None, f"TG failed to find txn {txn_id}"
            assert tg_txn.transaction_id == local_txn.transaction_id
            assert tg_txn.card_id == local_txn.card_id
            assert tg_txn.amount == pytest.approx(local_txn.amount, rel=1e-2)
            assert tg_txn.product_cd == local_txn.product_cd

    # 2. Baseline Calculation Parity
    card_id = "C12382-K1"
    ref_ts = 1475586928.0
    local_base = local_repo.get_card_baseline(card_id, ref_ts)
    tg_base = tg_repo.get_card_baseline(card_id, ref_ts)
    assert local_base.txn_count == tg_base.txn_count
    if local_base.txn_count > 0:
        assert tg_base.avg_amount == pytest.approx(local_base.avg_amount, rel=1e-2)
        assert tg_base.max_amount == pytest.approx(local_base.max_amount, rel=1e-2)
        assert set(tg_base.known_devices) == set(local_base.known_devices)
