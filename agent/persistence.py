import os
import sys
import json
import uuid
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import ANSWERS_DIR, CASES_DIR, AUDIT_LOG_DIR

def atomic_write_json(file_path: Path, data: Dict[str, Any], indent: int = 2) -> None:
    """
    Atomically writes a JSON object to disk by first writing to a temporary file 
    in the target directory and then performing an atomic os.replace.
    Prevents partial/corrupted writes during sudden process terminations.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create temp file in the same directory to ensure same filesystem for atomic rename
    temp_dir = file_path.parent
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, suffix=".tmp") as f:
            json.dump(data, f, indent=indent)
            temp_file = Path(f.name)
        os.replace(temp_file, file_path)
    except Exception as e:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise IOError(f"Failed atomic write to {file_path}: {e}")

class AuditLogger:
    """
    Structured, append-only audit logger for investigation events and policy decisions.
    """
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = Path(log_dir) if log_dir else AUDIT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        case_id: str,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Appends an immutable audit record for a given case.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        record = {
            "event_id": event_id,
            "case_id": case_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "actor": actor,
            "details": details,
            "provenance": provenance or {}
        }
        
        case_log_file = self.log_dir / f"{case_id}_audit.jsonl"
        with open(case_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        return record

    def get_audit_trail(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all audit events for a given case in chronological order.
        """
        case_log_file = self.log_dir / f"{case_id}_audit.jsonl"
        if not case_log_file.exists():
            return []
        
        events = []
        with open(case_log_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        events.append(json.loads(line_str))
                    except json.JSONDecodeError:
                        continue
        return events

class InvestigationPersistenceManager:
    """
    Manages persistence of internal investigation state (cases/) 
    and deliverable benchmark outputs (answers/).
    """
    def __init__(self, cases_dir: Optional[Path] = None, answers_dir: Optional[Path] = None):
        self.cases_dir = Path(cases_dir) if cases_dir else CASES_DIR
        self.answers_dir = Path(answers_dir) if answers_dir else ANSWERS_DIR
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.answers_dir.mkdir(parents=True, exist_ok=True)
        self.audit_logger = AuditLogger()

    def persist_case_state(self, case_id: str, case_data: Dict[str, Any], actor: str = "agent") -> Path:
        """
        Persists internal investigation state atomically into cases/<case_id>.json
        """
        case_file = self.cases_dir / f"{case_id}.json"
        atomic_write_json(case_file, case_data)
        
        self.audit_logger.log_event(
            case_id=case_id,
            event_type="CASE_STATE_SAVED",
            actor=actor,
            details={
                "status": case_data.get("case", {}).get("status"),
                "verdict": case_data.get("case", {}).get("verdict"),
                "exposure_usd": case_data.get("case", {}).get("exposure_usd")
            }
        )
        return case_file

    def persist_answer_artifact(self, case_id: str, case_data: Dict[str, Any]) -> Path:
        """
        Persists deliverable benchmark JSON into answers/<case_id>.json
        """
        answer_file = self.answers_dir / f"{case_id}.json"
        atomic_write_json(answer_file, case_data)
        return answer_file

    def get_case_state(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads internal investigation state for a given case.
        """
        case_file = self.cases_dir / f"{case_id}.json"
        if not case_file.exists():
            return None
        with open(case_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_audit_trail(self, case_id: str) -> List[Dict[str, Any]]:
        return self.audit_logger.get_audit_trail(case_id)

_persistence_mgr = None

def get_persistence_manager() -> InvestigationPersistenceManager:
    global _persistence_mgr
    if _persistence_mgr is None:
        _persistence_mgr = InvestigationPersistenceManager()
    return _persistence_mgr
