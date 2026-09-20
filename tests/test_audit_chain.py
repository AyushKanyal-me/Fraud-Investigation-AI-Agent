import json
import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.persistence import AuditLogger

def test_audit_chain_sequential_and_integrity(tmp_path: Path):
    logger = AuditLogger(log_dir=tmp_path)
    case_id = "HHG-TEST-001"

    # Log 5 events
    logger.log_event(case_id, "ALERT_RECEIVED", "system", {"alert_score": 0.85})
    logger.log_event(case_id, "BASELINE_QUERIED", "agent", {"avg_amount": 120.0})
    logger.log_event(case_id, "EVIDENCE_REQUESTED", "agent", {"channel": "sms"})
    logger.log_event(case_id, "CUSTOMER_REPLIED", "customer", {"confirmed": False})
    logger.log_event(case_id, "POLICY_EVALUATED", "policy_engine", {"verdict": "fraud", "action": "BLOCK_CARD"})

    # Check chain integrity
    is_valid, errors = logger.verify_chain_integrity(case_id)
    assert is_valid is True
    assert len(errors) == 0

    # Read events to check genesis and prev_hash linkage
    trail = logger.get_audit_trail(case_id)
    assert len(trail) == 5
    assert trail[0]["prev_hash"] == "GENESIS"
    for i in range(1, len(trail)):
        assert trail[i]["prev_hash"] == trail[i - 1]["record_hash"]

def test_audit_chain_tamper_detection(tmp_path: Path):
    logger = AuditLogger(log_dir=tmp_path)
    case_id = "HHG-TAMPER-001"

    logger.log_event(case_id, "EVENT_1", "agent", {"val": 1})
    logger.log_event(case_id, "EVENT_2", "agent", {"val": 2})
    logger.log_event(case_id, "EVENT_3", "agent", {"val": 3})

    # Tamper with event 2 in the log file
    log_file = tmp_path / f"{case_id}_audit.jsonl"
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    record_1 = json.loads(lines[1])
    record_1["details"]["val"] = 999  # modify content
    lines[1] = json.dumps(record_1)
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Verify tampering is caught
    is_valid, errors = logger.verify_chain_integrity(case_id)
    assert is_valid is False
    assert any("Tampered content" in err for err in errors)

def test_audit_chain_deletion_detection(tmp_path: Path):
    logger = AuditLogger(log_dir=tmp_path)
    case_id = "HHG-DELETE-001"

    logger.log_event(case_id, "EVENT_1", "agent", {"val": 1})
    logger.log_event(case_id, "EVENT_2", "agent", {"val": 2})
    logger.log_event(case_id, "EVENT_3", "agent", {"val": 3})

    # Delete event 2
    log_file = tmp_path / f"{case_id}_audit.jsonl"
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    del lines[1]
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Verify link breakage is caught
    is_valid, errors = logger.verify_chain_integrity(case_id)
    assert is_valid is False
    assert any("Broken hash link" in err for err in errors)
