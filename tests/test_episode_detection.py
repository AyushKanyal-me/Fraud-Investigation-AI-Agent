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

def test_card_testing_episode_detection(repo):
    # Case HHG-011 (flagged txn 3583368) has card testing sequence
    txn = repo.get_transaction_detail("3583368")
    assert txn is not None
    
    episode = repo.expand_fraud_episode(txn.card_id, txn.ts_val, "3583368")
    assert "3583368" in episode.affected_txn_ids
    assert episode.exposure_usd >= txn.amount
    assert episode.metadata.get("is_card_testing") is True

def test_single_transaction_episode(repo):
    # Case HHG-001 (flagged txn 3514030) is a single out-of-region transaction
    txn = repo.get_transaction_detail("3514030")
    assert txn is not None
    
    episode = repo.expand_fraud_episode(txn.card_id, txn.ts_val, "3514030")
    assert episode.affected_txn_ids == ["3514030"]
    assert episode.exposure_usd == txn.amount
    assert episode.first_suspicious_txn_id == "3514030"
