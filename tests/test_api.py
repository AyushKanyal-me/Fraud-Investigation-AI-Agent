import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app

TEST_API_KEY = "test-secret-key-32-characters-long"

@pytest.fixture(autouse=True)
def setup_test_auth(monkeypatch):
    monkeypatch.setenv("API_AUTH_KEY", TEST_API_KEY)

def test_healthz_endpoint():
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "policy_version" in data

def test_repository_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/repository/health")
        assert response.status_code == 200
        data = response.json()
        assert "backend" in data

def test_metrics_endpoint():
    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_cases" in data
        assert "fraud_cases" in data

def test_get_policies_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/policies")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "R1" in data["rules"]
        assert "R10" in data["rules"]

def test_read_only_case_get():
    with TestClient(app) as client:
        response = client.get("/cases/HHG-001")
        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == "HHG-001"

def test_read_only_audit_log_get():
    with TestClient(app) as client:
        response = client.get("/cases/HHG-001/audit-log")
        assert response.status_code == 200
        data = response.json()
        assert "audit_events" in data

def test_audit_verify_endpoint():
    with TestClient(app) as client:
        response = client.get("/cases/HHG-001/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert "chain_intact" in data
        assert data["chain_intact"] is True

def test_read_only_evidence_get():
    with TestClient(app) as client:
        response = client.get("/cases/HHG-001/evidence")
        assert response.status_code == 200
        data = response.json()
        assert "evidence" in data

def test_api_auth_protection_on_investigate():
    with TestClient(app) as client:
        # Without API key -> 401 Unauthorized
        response = client.post("/api/cases/HHG-001/investigate")
        assert response.status_code == 401
        assert "Invalid or missing API Key" in response.json()["detail"]

        # With invalid API key -> 401 Unauthorized
        response = client.post("/api/cases/HHG-001/investigate", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

def test_api_auth_success_with_valid_key():
    with TestClient(app) as client:
        # With valid API key -> routes to handler and executes successfully
        response = client.post(
            "/api/cases/HHG-001/investigate",
            headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("case_id") == "HHG-001"
        assert "case" in data

def test_insecure_key_rejection(monkeypatch):
    monkeypatch.setenv("API_AUTH_KEY", "tigergraph-fraud-agent-auth-key")
    with TestClient(app) as client:
        response = client.post(
            "/api/cases/HHG-001/investigate",
            headers={"X-API-Key": "tigergraph-fraud-agent-auth-key"}
        )
        assert response.status_code == 500
        assert "insecure/placeholder" in response.json()["detail"]

def test_healthz_is_lightweight():
    with TestClient(app) as client:
        res = client.get("/healthz")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        # healthz must NOT expose heavy dataset transaction loading
        assert "dataset_transactions_loaded" not in data

