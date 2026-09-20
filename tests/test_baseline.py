import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.repository.local import LocalFraudRepository

@pytest.fixture
def repo():
    return LocalFraudRepository()

def test_baseline_lookahead_bias_prevention(repo):
    # Retrieve transaction 3514030
    txn = repo.get_transaction_detail("3514030")
    assert txn is not None
    
    # Calculate baseline strictly before txn.ts_val with 30-day lookback
    lookback_sec = 30 * 86400
    baseline = repo.get_card_baseline(txn.card_id, before_ts=txn.ts_val, lookback_sec=lookback_sec)
    
    # Verify that only transactions in that 30-day lookback window strictly before this timestamp were counted
    window_txns = repo.df_txn[
        (repo.df_txn["card_id"] == txn.card_id) &
        (repo.df_txn["ts_val"] < txn.ts_val) &
        (repo.df_txn["ts_val"] >= txn.ts_val - lookback_sec)
    ]
    assert baseline.txn_count == len(window_txns)
    if baseline.txn_count > 0:
        assert baseline.avg_amount > 0.0

def test_empty_baseline_for_new_card(repo):
    # Non-existent card ID should return zeroed baseline
    baseline = repo.get_card_baseline("NON_EXISTENT_CARD_K99", before_ts=1000000)
    assert baseline.txn_count == 0
    assert baseline.avg_amount == 0.0
    assert baseline.max_amount == 0.0
    assert len(baseline.known_devices) == 0
