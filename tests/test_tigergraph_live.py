import os
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME
from agent.repository.tigergraph import TigerGraphFraudRepository

# Only run live TigerGraph tests if explicitly requested or if live service is reachable
LIVE_TG_ENABLED = os.getenv("TIGERGRAPH_LIVE_TESTS", "false").lower() in ("true", "1", "yes")

@pytest.fixture(scope="module")
def live_tg_repo():
    if not LIVE_TG_ENABLED:
        pytest.skip("Live TigerGraph tests disabled. Set TIGERGRAPH_LIVE_TESTS=true to run.")
    repo = TigerGraphFraudRepository()
    if not repo.is_connected():
        pytest.skip(f"TigerGraph instance at {TG_HOST}:{TG_RESTPP_PORT} is not reachable.")
    return repo

@pytest.mark.skipif(not LIVE_TG_ENABLED, reason="TIGERGRAPH_LIVE_TESTS not enabled")
def test_live_tg_connection(live_tg_repo):
    assert live_tg_repo.is_connected() is True
    health = live_tg_repo.get_health_status()
    assert health["is_connected"] is True
    assert health["graph_name"] == TG_GRAPH_NAME

@pytest.mark.skipif(not LIVE_TG_ENABLED, reason="TIGERGRAPH_LIVE_TESTS not enabled")
def test_live_tg_transaction_detail(live_tg_repo):
    # Query known transaction from HHG-001
    txn = live_tg_repo.get_transaction_detail("3514030")
    assert txn is not None
    assert txn.transaction_id == "3514030"
    assert txn.amount > 0


@pytest.mark.skipif(not LIVE_TG_ENABLED, reason="TIGERGRAPH_LIVE_TESTS not enabled")
def test_live_tg_card_baseline(live_tg_repo):
    baseline = live_tg_repo.get_card_baseline("CUST1001-K1", before_ts=1500000000.0)
    assert baseline is not None
    assert baseline.txn_count >= 0

@pytest.mark.skipif(not LIVE_TG_ENABLED, reason="TIGERGRAPH_LIVE_TESTS not enabled")
def test_live_tg_persist_case(live_tg_repo):
    test_case_data = {
        "case": {
            "status": "closed_fraud",
            "verdict": "fraud",
            "pattern": "card_testing",
            "fraud_probability": 0.95,
            "exposure_usd": 1250.00
        }
    }
    success = live_tg_repo.persist_case_graph("HHG-LIVE-TEST", test_case_data)
    assert success is True
