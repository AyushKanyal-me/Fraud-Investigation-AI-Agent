import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.repository.local import LocalFraudRepository
from agent.claim_validator import ModelClaimValidator

@pytest.fixture
def claim_validator():
    repo = LocalFraudRepository()
    return ModelClaimValidator(repository=repo)

def test_validate_real_transactions(claim_validator):
    # Benchmark transaction 3514030 exists
    valid, invalid = claim_validator.validate_cited_transactions(["3514030"])
    assert len(valid) == 1
    assert valid[0] == "3514030"
    assert len(invalid) == 0

def test_reject_hallucinated_transactions(claim_validator):
    fake_id = "FAKE_TXN_9999999"
    valid, invalid = claim_validator.validate_cited_transactions([fake_id])
    assert len(valid) == 0
    assert len(invalid) == 1
    assert invalid[0] == fake_id

def test_validate_amount_claims(claim_validator):
    # Within 5% tolerance
    assert claim_validator.validate_amount_claim(100.0, 102.0) is True
    # Exceeding tolerance
    assert claim_validator.validate_amount_claim(100.0, 150.0) is False

def test_sanitize_evidence_claims(claim_validator):
    claims = [
        {
            "claim": "Customer reported suspicious activity",
            "source": "customer",
            "ref": "req-1",
            "entity_ids": ["3514030", "HALLUCINATED_ID_8888"]
        }
    ]
    sanitized = claim_validator.sanitize_evidence_claims(claims)
    assert len(sanitized) == 1
    assert "3514030" in sanitized[0]["entity_ids"]
    assert "HALLUCINATED_ID_8888" not in sanitized[0]["entity_ids"]
