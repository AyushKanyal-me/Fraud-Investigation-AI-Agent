import pytest
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.checkpoints_db import SQLiteCheckpointStore, PostgresCheckpointStore

def test_sqlite_checkpoint_crud_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_checkpoints.db"
    store = SQLiteCheckpointStore(db_path=db_file)
    
    case_id = "HHG-SQLITE-001"
    req_id = "req-abc-123"
    state = {"stage": "evidence_collection", "prompt": "Did you authorize txn 101?"}

    # Save
    ret_req_id = store.save_checkpoint(case_id, req_id, state)
    assert ret_req_id == req_id

    # Get by case_id
    cp = store.get_checkpoint(case_id)
    assert cp is not None
    assert cp["case_id"] == case_id
    assert cp["request_id"] == req_id
    assert cp["state"] == state
    assert cp["status"] == "awaiting_evidence"

    # List pending
    pending = store.list_pending_checkpoints()
    assert len(pending) == 1
    assert pending[0]["case_id"] == case_id

    # Update on conflict
    updated_state = {"stage": "evidence_collection", "prompt": "Updated question"}
    store.save_checkpoint(case_id, req_id, updated_state)
    cp_updated = store.get_checkpoint(case_id, req_id)
    assert cp_updated["state"]["prompt"] == "Updated question"

    # Delete
    deleted = store.delete_checkpoint(case_id, req_id)
    assert deleted is True
    assert store.get_checkpoint(case_id) is None
    assert len(store.list_pending_checkpoints()) == 0

def test_sqlite_migration_from_files(tmp_path: Path):
    # Create mock legacy checkpoint JSON files
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    
    cp1 = {"case_id": "CASE-1", "request_id": "req-1", "state": {"val": 1}}
    cp2 = {"case_id": "CASE-2", "request_id": "req-2", "state": {"val": 2}}
    
    (legacy_dir / "CASE-1_checkpoint.json").write_text(json.dumps(cp1))
    (legacy_dir / "CASE-2_checkpoint.json").write_text(json.dumps(cp2))

    # Migrate to SQLite
    db_file = tmp_path / "migrated.db"
    store = SQLiteCheckpointStore(db_path=db_file)
    migrated_count = store.migrate_from_files(legacy_dir)

    assert migrated_count == 2
    assert store.get_checkpoint("CASE-1") is not None
    assert store.get_checkpoint("CASE-2") is not None

def test_postgres_checkpoint_fallback_when_unreachable(tmp_path: Path):
    db_file = tmp_path / "pg_fallback.db"
    # Provide invalid postgres URI to verify seamless fallback to SQLite
    store = PostgresCheckpointStore(
        postgres_uri="postgresql://fake_user:fake_pass@localhost:54329/fake_db",
        fallback_sqlite_path=db_file
    )
    assert store.use_fallback is True

    # Check that fallback works for all operations
    store.save_checkpoint("CASE-FALLBACK", "req-fb-1", {"step": "test"})
    cp = store.get_checkpoint("CASE-FALLBACK")
    assert cp is not None
    assert cp["request_id"] == "req-fb-1"
    
    pending = store.list_pending_checkpoints()
    assert len(pending) >= 1

    deleted = store.delete_checkpoint("CASE-FALLBACK")
    assert deleted is True
