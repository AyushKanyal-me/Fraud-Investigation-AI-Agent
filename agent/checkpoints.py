import os
import sys
import json
import abc
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import CHECKPOINTS_DIR
from agent.persistence import atomic_write_json

class CheckpointStore(abc.ABC):
    """
    Abstract interface for persisting and resuming in-flight investigation states.
    """
    @abc.abstractmethod
    def save_checkpoint(self, case_id: str, request_id: str, state_data: Dict[str, Any]) -> str:
        """Saves a state checkpoint associated with an evidence request."""
        pass

    @abc.abstractmethod
    def get_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the active state checkpoint for a case or request."""
        pass

    @abc.abstractmethod
    def delete_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> bool:
        """Deletes a completed checkpoint."""
        pass

    @abc.abstractmethod
    def list_pending_checkpoints(self) -> List[Dict[str, Any]]:
        """Lists all cases currently awaiting evidence."""
        pass

class FileCheckpointStore(CheckpointStore):
    """
    Durable, file-backed checkpoint store that persists workflow state to disk atomically.
    """
    def __init__(self, checkpoints_dir: Optional[Path] = None):
        self.checkpoints_dir = Path(checkpoints_dir) if checkpoints_dir else CHECKPOINTS_DIR
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, case_id: str) -> Path:
        return self.checkpoints_dir / f"{case_id}_checkpoint.json"

    def save_checkpoint(self, case_id: str, request_id: str, state_data: Dict[str, Any]) -> str:
        checkpoint_payload = {
            "case_id": case_id,
            "request_id": request_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "awaiting_evidence",
            "state": state_data
        }
        file_path = self._get_path(case_id)
        atomic_write_json(file_path, checkpoint_payload)
        return request_id

    def get_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        file_path = self._get_path(case_id)
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if request_id and data.get("request_id") != request_id:
                return None
            return data

    def delete_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> bool:
        file_path = self._get_path(case_id)
        if not file_path.exists():
            return False
        if request_id:
            data = self.get_checkpoint(case_id)
            if data and data.get("request_id") != request_id:
                return False
        try:
            os.remove(file_path)
            return True
        except Exception:
            return False

    def list_pending_checkpoints(self) -> List[Dict[str, Any]]:
        pending = []
        for p in self.checkpoints_dir.glob("*_checkpoint.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    pending.append(json.load(f))
            except Exception:
                continue
        return pending

_checkpoint_store = None

def get_checkpoint_store(backend: Optional[str] = None) -> CheckpointStore:
    global _checkpoint_store
    if _checkpoint_store is None:
        target_backend = backend or os.getenv("CHECKPOINT_BACKEND", "sqlite").lower()
        if target_backend == "postgres":
            from agent.checkpoints_db import PostgresCheckpointStore
            _checkpoint_store = PostgresCheckpointStore()
        elif target_backend == "file":
            _checkpoint_store = FileCheckpointStore()
        else:
            from agent.checkpoints_db import SQLiteCheckpointStore
            _checkpoint_store = SQLiteCheckpointStore()
    return _checkpoint_store

