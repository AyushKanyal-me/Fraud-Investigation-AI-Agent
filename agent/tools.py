import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from rag.vector_store import FraudVectorStore
from agent.card_identity import get_canonical_card_mapper
from agent.repository.factory import get_fraud_repository
from agent.repository.base import FraudDataRepository

class GraphTools:
    """
    High-level Graph Analytics facade delegating data retrieval to the FraudDataRepository interface.
    Provides backward-compatible APIs for the LangGraph state machine.
    """
    def __init__(self, vector_store: Optional[FraudVectorStore] = None, repository: Optional[FraudDataRepository] = None):
        self.vector_store = vector_store or FraudVectorStore()
        self.card_mapper = get_canonical_card_mapper()
        self.repo = repository or get_fraud_repository()

    @property
    def conn(self):
        return getattr(self.repo, "conn", None)

    @property
    def is_data_loaded(self) -> bool:
        """Returns True if repository data is already loaded in memory, without forcing a load."""
        if hasattr(self.repo, "is_loaded"):
            return bool(getattr(self.repo, "is_loaded", False))
        df = getattr(self.repo, "df_txn", None)
        return df is not None and len(df) > 0

    @property
    def loaded_txn_count(self) -> int:
        """Returns count of loaded transactions if already in memory, without forcing a load."""
        df = getattr(self.repo, "df_txn", None)
        return len(df) if df is not None else 0

    @property
    def df_txn(self):
        if hasattr(self.repo, "_ensure_loaded"):
            self.repo._ensure_loaded()
        df = getattr(self.repo, "df_txn", None)
        return df if df is not None else pd.DataFrame()

    @property
    def df_id(self):
        if hasattr(self.repo, "_ensure_loaded"):
            self.repo._ensure_loaded()
        return getattr(self.repo, "df_id", None)

    @property
    def df_closed(self):
        if hasattr(self.repo, "_ensure_loaded"):
            self.repo._ensure_loaded()
        return getattr(self.repo, "df_closed", None)


    def get_transaction_detail(self, txn_id: str) -> Dict[str, Any]:
        """Fetches complete transaction record including identity metadata."""
        rec = self.repo.get_transaction_detail(str(txn_id))
        if rec:
            return rec.to_dict()
        return {}

    def get_time_bounded_card_baseline(self, card_id: str, before_ts: float, lookback_sec: float = 30 * 86400) -> Dict[str, Any]:
        """
        Calculates spending baseline strictly prior to before_ts (preventing lookahead bias).
        """
        base = self.repo.get_card_baseline(card_id, before_ts, lookback_sec)
        return base.to_dict()

    def expand_fraud_episode(self, card_id: str, center_ts: float, flagged_txn_id: str, window_sec: float = 86400) -> Tuple[List[str], float, str, Dict[str, Any]]:
        """
        Temporal Episode Expansion:
        Discovers all transactions on this card within time window [center_ts - window_sec, center_ts + 3600]
        belonging to the same compromise episode.
        """
        ep = self.repo.expand_fraud_episode(card_id, center_ts, flagged_txn_id, window_sec)
        return ep.affected_txn_ids, ep.exposure_usd, ep.first_suspicious_txn_id, ep.metadata

    def get_time_bounded_device_neighbors(self, device_info: str, center_ts: float, window_sec: float = 7 * 86400, exclude_card_id: str = None) -> List[Dict[str, Any]]:
        """
        Finds other distinct cards that used the same specific DeviceInfo within a 7-day window of center_ts.
        """
        neighbors = self.repo.get_device_neighbors(device_info, center_ts, window_sec, exclude_card_id=exclude_card_id)
        # Format for backward-compatibility as list of transaction-like record dicts
        res = []
        for n in neighbors:
            res.append({
                "TransactionID": f"TXN_{n.card_id}",
                "card_id": n.card_id,
                "customer_id": n.customer_id,
                "TransactionAmt": n.total_amount,
                "ts_val": center_ts,
                "device_info": n.device_info
            })
        return res[:15]

    def find_similar_closed_cases(self, card_id: str = None, customer_id: str = None, pattern: str = None, limit: int = 5) -> List[str]:
        """Hybrid search for relevant historical closed cases from closed_cases_history."""
        matched = []
        repo_cases = self.repo.get_similar_closed_cases(pattern=pattern, customer_id=customer_id, top_k=limit)
        for rc in repo_cases:
            matched.append(rc.case_id)

        # Semantic search from Vector Store
        if pattern and pattern != "none":
            vector_res = self.vector_store.search(f"{pattern} fraud investigation case", n_results=3, category="closed_case")
            for vr in vector_res:
                cid = vr.get("metadata", {}).get("case_id")
                if cid:
                    matched.append(cid)

        return list(dict.fromkeys(matched))[:limit]

    def write_case_to_graph(self, case_id: str, case_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Persists full investigated case into the graph store and returns receipt.
        """
        success = self.repo.persist_case_graph(case_id, case_data)
        receipt = f"TG-RECEIPT-{case_id}" if success else f"PERSIST-LOCAL-{case_id}"
        return success, receipt
