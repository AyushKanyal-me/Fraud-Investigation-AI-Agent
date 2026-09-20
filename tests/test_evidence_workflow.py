import pytest
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app
from agent.checkpoints import get_checkpoint_store

def test_evidence_submission_and_resume_endpoint():
    auth_key = os.getenv("API_AUTH_KEY", "test-secret-key-32-characters-long")
    checkpoint_store = get_checkpoint_store()
    case_id = "HHG-001"
    request_id = "test-evidence-req-001"

    with TestClient(app) as client:
        # 1. Save an in-flight checkpoint
        checkpoint_store.save_checkpoint(case_id, request_id, {"step": 4, "pending": True})
        assert checkpoint_store.get_checkpoint(case_id) is not None

        # 2. Check checkpoint status via GET
        get_res = client.get(f"/cases/{case_id}/checkpoints")
        assert get_res.status_code == 200
        assert get_res.json()["status"] == "awaiting_evidence"

        # 3. Submit external evidence to resume workflow
        submit_payload = {
            "request_id": request_id,
            "response_text": "Customer confirmed they received an alert and stated: I did not authorize transaction 3514030 ($77.07).",
            "source": "customer_portal",
            "actor_id": "cardholder_web_portal"
        }

        res = client.post(
            f"/cases/{case_id}/evidence/submit",
            json=submit_payload,
            headers={"X-API-Key": auth_key}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["case_id"] == case_id
        assert data["case"]["verdict"] == "fraud"
        
        # Verify provenance tag in evidence requests
        ev_reqs = data["evidence_requests"]
        assert len(ev_reqs) > 0
        assert ev_reqs[0]["provenance"]["source"] == "customer_portal"
        assert ev_reqs[0]["provenance"]["actor_id"] == "cardholder_web_portal"

        # 4. Check that checkpoint was cleaned up
        assert checkpoint_store.get_checkpoint(case_id) is None
