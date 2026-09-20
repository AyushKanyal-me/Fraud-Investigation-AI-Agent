import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app
from config import API_AUTH_KEY

client = TestClient(app)

def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "policy_version" in data

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_cases" in data
    assert "fraud_cases" in data

def test_get_policies_endpoint():
    response = client.get("/api/policies")
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert "R1" in data["rules"]
    assert "R10" in data["rules"]

def test_read_only_case_get():
    # Test reading existing case
    response = client.get("/cases/HHG-001")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == "HHG-001"

def test_read_only_audit_log_get():
    response = client.get("/cases/HHG-001/audit-log")
    assert response.status_code == 200
    data = response.json()
    assert "audit_events" in data

def test_read_only_evidence_get():
    response = client.get("/cases/HHG-001/evidence")
    assert response.status_code == 200
    data = response.json()
    assert "evidence" in data

def test_api_auth_protection_on_investigate():
    # Without API key -> 401 Unauthorized
    response = client.post("/api/cases/HHG-001/investigate")
    assert response.status_code == 401
    assert "Invalid or missing API Key" in response.json()["detail"]

    # With invalid API key -> 401 Unauthorized
    response = client.post("/api/cases/HHG-001/investigate", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

def test_api_auth_success_with_valid_key():
    # With valid API key -> routes to handler (not 401)
    response = client.post(
        "/api/cases/HHG-001/investigate",
        headers={"X-API-Key": API_AUTH_KEY}
    )
    # The investigation executes or returns 200
    assert response.status_code in [200, 500]  # Valid auth passed
