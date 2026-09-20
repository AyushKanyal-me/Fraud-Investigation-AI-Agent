import os
import sys
import json
import sqlite3
import abc
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import CHECKPOINTS_DIR
from agent.checkpoints import CheckpointStore

logger = logging.getLogger("checkpoints_db")

class SQLiteCheckpointStore(CheckpointStore):
    """
    ACID-compliant SQLite checkpoint store with WAL mode enabled.
    Stores in-flight investigation states for pause/resume flows.
    """
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
            self.db_path = CHECKPOINTS_DIR / "checkpoints.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    case_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting_evidence',
                    state_json TEXT NOT NULL,
                    PRIMARY KEY (case_id, request_id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON checkpoints(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_case_id ON checkpoints(case_id);")

    def save_checkpoint(self, case_id: str, request_id: str, state_data: Dict[str, Any]) -> str:
        created_at = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state_data)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO checkpoints (case_id, request_id, created_at, status, state_json)
                VALUES (?, ?, ?, 'awaiting_evidence', ?)
                ON CONFLICT(case_id, request_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    status = excluded.status,
                    state_json = excluded.state_json;
            """, (case_id, request_id, created_at, state_json))
        return request_id

    def get_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            if request_id:
                cur = conn.execute(
                    "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE case_id = ? AND request_id = ?",
                    (case_id, request_id)
                )
            else:
                cur = conn.execute(
                    "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
                    (case_id,)
                )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "case_id": row["case_id"],
                "request_id": row["request_id"],
                "created_at": row["created_at"],
                "status": row["status"],
                "state": json.loads(row["state_json"])
            }

    def delete_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            if request_id:
                cur = conn.execute(
                    "DELETE FROM checkpoints WHERE case_id = ? AND request_id = ?",
                    (case_id, request_id)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM checkpoints WHERE case_id = ?",
                    (case_id,)
                )
            return cur.rowcount > 0

    def list_pending_checkpoints(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE status = 'awaiting_evidence' ORDER BY created_at ASC"
            )
            rows = cur.fetchall()
            return [
                {
                    "case_id": r["case_id"],
                    "request_id": r["request_id"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                    "state": json.loads(r["state_json"])
                }
                for r in rows
            ]

    def migrate_from_files(self, file_dir: Path) -> int:
        """Migrates legacy JSON checkpoint files into SQLite table."""
        count = 0
        file_dir = Path(file_dir)
        if not file_dir.exists():
            return 0
        for p in file_dir.glob("*_checkpoint.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    case_id = data.get("case_id")
                    req_id = data.get("request_id")
                    state = data.get("state", {})
                    if case_id and req_id:
                        self.save_checkpoint(case_id, req_id, state)
                        count += 1
            except Exception as e:
                logger.warning("Failed migrating checkpoint file %s: %s", p, e)
        return count


class PostgresCheckpointStore(CheckpointStore):
    """
    PostgreSQL checkpoint store implementation for production deployments.
    Falls back gracefully to SQLite if psycopg2/asyncpg is not installed or connection fails.
    """
    def __init__(self, postgres_uri: Optional[str] = None, fallback_sqlite_path: Optional[Path] = None):
        self.postgres_uri = postgres_uri or os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")
        self.fallback = SQLiteCheckpointStore(db_path=fallback_sqlite_path)
        self.use_fallback = True
        self._init_pg()

    def _init_pg(self):
        if not self.postgres_uri:
            self.use_fallback = True
            return
        try:
            import psycopg2
            import psycopg2.extras
            with psycopg2.connect(self.postgres_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS checkpoints (
                            case_id VARCHAR(100) NOT NULL,
                            request_id VARCHAR(100) NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                            status VARCHAR(50) NOT NULL DEFAULT 'awaiting_evidence',
                            state_json JSONB NOT NULL,
                            PRIMARY KEY (case_id, request_id)
                        );
                        CREATE INDEX IF NOT EXISTS idx_pg_status ON checkpoints(status);
                    """)
                conn.commit()
            self.use_fallback = False
        except Exception as e:
            logger.warning("PostgreSQL connection failed (%s), utilizing SQLite checkpoint fallback.", e)
            self.use_fallback = True

    def save_checkpoint(self, case_id: str, request_id: str, state_data: Dict[str, Any]) -> str:
        if self.use_fallback:
            return self.fallback.save_checkpoint(case_id, request_id, state_data)
        import psycopg2
        import psycopg2.extras
        created_at = datetime.now(timezone.utc)
        state_json = json.dumps(state_data)
        with psycopg2.connect(self.postgres_uri) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO checkpoints (case_id, request_id, created_at, status, state_json)
                    VALUES (%s, %s, %s, 'awaiting_evidence', %s)
                    ON CONFLICT (case_id, request_id) DO UPDATE SET
                        created_at = EXCLUDED.created_at,
                        status = EXCLUDED.status,
                        state_json = EXCLUDED.state_json;
                """, (case_id, request_id, created_at, state_json))
            conn.commit()
        return request_id

    def get_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if self.use_fallback:
            return self.fallback.get_checkpoint(case_id, request_id)
        import psycopg2
        import psycopg2.extras
        with psycopg2.connect(self.postgres_uri) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if request_id:
                    cur.execute(
                        "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE case_id = %s AND request_id = %s",
                        (case_id, request_id)
                    )
                else:
                    cur.execute(
                        "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE case_id = %s ORDER BY created_at DESC LIMIT 1",
                        (case_id,)
                    )
                row = cur.fetchone()
                if not row:
                    return None
                state = row["state_json"]
                if isinstance(state, str):
                    state = json.loads(state)
                return {
                    "case_id": row["case_id"],
                    "request_id": row["request_id"],
                    "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                    "status": row["status"],
                    "state": state
                }

    def delete_checkpoint(self, case_id: str, request_id: Optional[str] = None) -> bool:
        if self.use_fallback:
            return self.fallback.delete_checkpoint(case_id, request_id)
        import psycopg2
        with psycopg2.connect(self.postgres_uri) as conn:
            with conn.cursor() as cur:
                if request_id:
                    cur.execute("DELETE FROM checkpoints WHERE case_id = %s AND request_id = %s", (case_id, request_id))
                else:
                    cur.execute("DELETE FROM checkpoints WHERE case_id = %s", (case_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted

    def list_pending_checkpoints(self) -> List[Dict[str, Any]]:
        if self.use_fallback:
            return self.fallback.list_pending_checkpoints()
        import psycopg2
        import psycopg2.extras
        with psycopg2.connect(self.postgres_uri) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT case_id, request_id, created_at, status, state_json FROM checkpoints WHERE status = 'awaiting_evidence' ORDER BY created_at ASC"
                )
                rows = cur.fetchall()
                res = []
                for r in rows:
                    state = r["state_json"]
                    if isinstance(state, str):
                        state = json.loads(state)
                    res.append({
                        "case_id": r["case_id"],
                        "request_id": r["request_id"],
                        "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                        "status": r["status"],
                        "state": state
                    })
                return res
