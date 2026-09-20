import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.repository.local import LocalFraudRepository
from agent.repository.factory import get_fraud_repository

@pytest.fixture
def local_repo():
    return LocalFraudRepository()

def test_get_transaction_detail(local_repo):
    # Test lookup of known benchmark transaction 3514030
    rec = local_repo.get_transaction_detail("3514030")
    assert rec is not None
    assert rec.transaction_id == "3514030"
    assert rec.card_id == "C12382-K1"
    assert rec.customer_id == "C12382"
    assert rec.amount == 77.07

def test_get_nonexistent_transaction(local_repo):
    rec = local_repo.get_transaction_detail("NON_EXISTENT_TXN_9999999")
    assert rec is None

def test_get_card_baseline(local_repo):
    # Card C12382-K1 before transaction 3514030
    txn = local_repo.get_transaction_detail("3514030")
    assert txn is not None
    baseline = local_repo.get_card_baseline(txn.card_id, txn.ts_val)
    
    assert baseline.txn_count >= 0
    if baseline.txn_count > 0:
        assert baseline.avg_amount > 0.0

def test_expand_fraud_episode(local_repo):
    # Card testing case HHG-011 (flagged txn 3583368)
    txn = local_repo.get_transaction_detail("3583368")
    assert txn is not None
    
    episode = local_repo.expand_fraud_episode(txn.card_id, txn.ts_val, "3583368")
    assert len(episode.affected_txn_ids) >= 1
    assert episode.exposure_usd >= txn.amount

def test_get_device_neighbors(local_repo):
    # Case HHG-014 (shared device query)
    txn = local_repo.get_transaction_detail("3478561")
    assert txn is not None
    if txn.device_info and txn.device_info != "unknown":
        neighbors = local_repo.get_device_neighbors(txn.device_info, txn.ts_val, exclude_card_id=txn.card_id)
        assert isinstance(neighbors, list)

def test_get_similar_closed_cases(local_repo):
    records = local_repo.get_similar_closed_cases(pattern="card_testing", top_k=3)
    assert len(records) > 0
    assert records[0].pattern == "card_testing"

def test_repository_factory():
    repo = get_fraud_repository("local")
    assert isinstance(repo, LocalFraudRepository)

def test_repository_lazy_loading():
    # Instantiate without calling any query
    repo = LocalFraudRepository()
    # Prior to querying, _ensure_loaded has not been invoked if class cache wasn't already primed
    # When query is called, it loads seamlessly
    rec = repo.get_transaction_detail("3514030")
    assert rec is not None
    assert repo.df_txn is not None
