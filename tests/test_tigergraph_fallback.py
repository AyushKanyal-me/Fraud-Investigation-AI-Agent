import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.repository.tigergraph import TigerGraphFraudRepository
from agent.repository.local import LocalFraudRepository

def test_tigergraph_fallback_when_disconnected(caplog):
    repo = TigerGraphFraudRepository()
    repo.conn = None  # Ensure disconnected

    # Run query
    txn = repo.get_transaction_detail("2987000")
    
    # Assert fallback took place
    assert repo.fallback_count >= 1
    assert repo.query_count >= 1
    assert "not initialized" in repo.last_fallback_reason
    assert repo.last_fallback_timestamp is not None
    
    # Check health status
    health = repo.get_health_status()
    assert health["is_connected"] is False
    assert health["fallback_count"] >= 1
    assert health["query_count"] >= 1

def test_tigergraph_fallback_on_query_exception():
    mock_conn = MagicMock()
    mock_conn.runInstalledQuery.side_effect = RuntimeError("GSQL server unavailable")
    
    repo = TigerGraphFraudRepository()
    repo.conn = mock_conn

    # Trigger method that calls runInstalledQuery
    baseline = repo.get_card_baseline("CUST1001-K1", before_ts=1500000000.0)
    
    assert repo.fallback_count >= 1
    assert "GSQL server unavailable" in repo.last_fallback_reason
    assert baseline is not None

def test_tigergraph_fail_closed_policy_on_disconnection():
    from agent.repository.exceptions import TigerGraphUnavailableError

    repo = TigerGraphFraudRepository(fallback_policy="fail_closed")
    repo.conn = None

    with pytest.raises(TigerGraphUnavailableError) as exc_info:
        repo.get_transaction_detail("2987000")
    
    assert "fail_closed" in str(exc_info.value)
    assert repo.fallback_count >= 1

def test_tigergraph_fail_closed_policy_on_query_error():
    from agent.repository.exceptions import TigerGraphUnavailableError

    mock_conn = MagicMock()
    mock_conn.runInstalledQuery.side_effect = RuntimeError("Connection timeout to graph engine")

    repo = TigerGraphFraudRepository(fallback_policy="fail_closed")
    repo.conn = mock_conn

    with pytest.raises(TigerGraphUnavailableError) as exc_info:
        repo.get_card_baseline("CUST1001-K1", before_ts=1500000000.0)

    assert "fail_closed" in str(exc_info.value)
