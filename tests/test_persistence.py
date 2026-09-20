import pytest
import os
import sys
import tempfile
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.persistence import atomic_write_json, AuditLogger, InvestigationPersistenceManager
from agent.checkpoints import FileCheckpointStore

def test_atomic_write_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "sub" / "test.json"
        data = {"key": "value", "count": 42}
        atomic_write_json(tmp_path, data)

        assert tmp_path.exists()
        with open(tmp_path, "r") as f:
            loaded = json.load(f)
        assert loaded == data

def test_audit_logger():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = AuditLogger(log_dir=Path(tmpdir))
        case_id = "HHG-001"
        
        event1 = logger.log_event(
            case_id=case_id,
            event_type="INITIATED",
            actor="test_user",
            details={"step": 1}
        )
        assert event1["case_id"] == case_id
        assert event1["event_type"] == "INITIATED"

        event2 = logger.log_event(
            case_id=case_id,
            event_type="POLICY_EVALUATED",
            actor="policy_engine",
            details={"verdict": "fraud"}
        )

        trail = logger.get_audit_trail(case_id)
        assert len(trail) == 2
        assert trail[0]["event_type"] == "INITIATED"
        assert trail[1]["event_type"] == "POLICY_EVALUATED"

def test_investigation_persistence_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        cases_dir = Path(tmpdir) / "cases"
        answers_dir = Path(tmpdir) / "answers"
        mgr = InvestigationPersistenceManager(cases_dir=cases_dir, answers_dir=answers_dir)

        case_data = {
            "case_id": "HHG-001",
            "case": {
                "status": "closed_fraud",
                "verdict": "fraud",
                "exposure_usd": 150.0
            }
        }
        
        # Save state
        case_path = mgr.persist_case_state("HHG-001", case_data, actor="analyst")
        assert case_path.exists()
        
        # Save answer
        ans_path = mgr.persist_answer_artifact("HHG-001", case_data)
        assert ans_path.exists()

        # Load state
        loaded = mgr.get_case_state("HHG-001")
        assert loaded is not None
        assert loaded["case_id"] == "HHG-001"

        # Check audit trail
        trail = mgr.get_audit_trail("HHG-001")
        assert len(trail) >= 1
        assert trail[-1]["event_type"] == "CASE_STATE_SAVED"

def test_file_checkpoint_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileCheckpointStore(checkpoints_dir=Path(tmpdir))
        case_id = "HHG-002"
        request_id = "req-12345"
        state = {"step": 4, "pending_question": "Did you make this purchase?"}

        # Save checkpoint
        saved_req_id = store.save_checkpoint(case_id, request_id, state)
        assert saved_req_id == request_id

        # Retrieve checkpoint
        cp = store.get_checkpoint(case_id)
        assert cp is not None
        assert cp["case_id"] == case_id
        assert cp["request_id"] == request_id
        assert cp["status"] == "awaiting_evidence"
        assert cp["state"] == state

        # List pending
        pending = store.list_pending_checkpoints()
        assert len(pending) == 1
        assert pending[0]["case_id"] == case_id

        # Delete checkpoint
        deleted = store.delete_checkpoint(case_id, request_id=request_id)
        assert deleted is True
        assert store.get_checkpoint(case_id) is None
        assert len(store.list_pending_checkpoints()) == 0
