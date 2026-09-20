import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME, DATASET_DIR
)
from rag.vector_store import FraudVectorStore
from agent.card_identity import get_canonical_card_mapper

class GraphTools:
    def __init__(self, vector_store: Optional[FraudVectorStore] = None):
        self.vector_store = vector_store or FraudVectorStore()
        self.card_mapper = get_canonical_card_mapper()
        self.conn = None
        self._init_tg()
        self._load_dataset_indices()

    def _init_tg(self):
        try:
            import pyTigerGraph as tg
            self.conn = tg.TigerGraphConnection(
                host=TG_HOST,
                restppPort=TG_RESTPP_PORT,
                gsPort=TG_GS_PORT,
                username=TG_USERNAME,
                password=TG_PASSWORD,
                graphname=TG_GRAPH_NAME
            )
            try:
                secret = self.conn.createSecret()
                self.conn.getToken(secret)
            except Exception:
                pass
        except Exception as e:
            print(f"[!] Graph connection notice: {e}")
            self.conn = None

    def _load_dataset_indices(self):
        """Loads and pre-indexes transactions, identity, and closed cases with canonical card mapping."""
        print("[*] Initializing GraphTools indices with canonical card mapping...")
        txn_path = DATASET_DIR / "transactions.csv"
        id_path = DATASET_DIR / "identity.csv"
        closed_path = DATASET_DIR / "closed_cases_history.csv"

        self.df_id = None
        if id_path.exists():
            self.df_id = pd.read_csv(id_path, dtype={"TransactionID": str})
            self.df_id.set_index("TransactionID", inplace=True)

        self.df_closed = None
        if closed_path.exists():
            self.df_closed = pd.read_csv(closed_path, dtype=str)

        self.df_txn = pd.read_csv(
            txn_path,
            dtype={
                "TransactionID": str,
                "customer_id": str,
                "ProductCD": str,
                "P_emaildomain": str,
                "R_emaildomain": str,
                "card1": str, "card2": str, "card3": str, "card4": str, "card5": str, "card6": str,
                "addr1": str, "addr2": str, "dist1": str, "dist2": str,
                "TransactionAmt": float, "TransactionDT": float, "risk_score": float
            }
        )

        # Avoid fragmentation by copying the base dataframe
        self.df_txn = self.df_txn.copy()

        # Parse numeric timestamp
        if "TransactionDT" in self.df_txn.columns:
            self.df_txn["ts_val"] = self.df_txn["TransactionDT"].fillna(0.0).astype(float)
        else:
            self.df_txn["ts_val"] = pd.to_datetime(self.df_txn["ts"], errors="coerce").astype("int64") // 10**9

        # Fast Canonical Card Mapping
        tuples = list(zip(
            self.df_txn["customer_id"].fillna("CUST_UNK"),
            self.df_txn["card1"].fillna("-1").astype(str),
            self.df_txn["card2"].fillna("-1").astype(str),
            self.df_txn["card3"].fillna("-1").astype(str),
            self.df_txn["card4"].fillna("unk").astype(str),
            self.df_txn["card5"].fillna("-1").astype(str),
            self.df_txn["card6"].fillna("unk").astype(str)
        ))
        self.df_txn["card_id"] = [
            self.card_mapper.tuple_to_card.get(t, f"{t[0]}-K1")
            for t in tuples
        ]

        # Merge Identity Metadata into dataframe
        if self.df_id is not None:
            self.df_txn = self.df_txn.join(self.df_id[["DeviceType", "DeviceInfo", "id_31", "id_30", "id_33"]], on="TransactionID")
        else:
            self.df_txn["DeviceType"] = "unknown"
            self.df_txn["DeviceInfo"] = "unknown"

        self.df_txn["DeviceType"] = self.df_txn["DeviceType"].fillna("unknown")
        self.df_txn["DeviceInfo"] = self.df_txn["DeviceInfo"].fillna("unknown")

        self.df_txn_by_id = self.df_txn.set_index("TransactionID")
        print(f"[+] GraphTools indices loaded: {len(self.df_txn)} transactions indexed by canonical Card ID.")

    def get_transaction_detail(self, txn_id: str) -> Dict[str, Any]:
        """Fetches complete transaction record including identity metadata."""
        if str(txn_id) in self.df_txn_by_id.index:
            row = self.df_txn_by_id.loc[str(txn_id)]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return row.to_dict()
        return {}

    def get_time_bounded_card_baseline(self, card_id: str, before_ts: float, lookback_sec: float = 30 * 86400) -> Dict[str, Any]:
        """
        Calculates spending baseline strictly prior to before_ts (preventing lookahead bias).
        """
        matches = self.df_txn[
            (self.df_txn["card_id"] == card_id) &
            (self.df_txn["ts_val"] < before_ts) &
            (self.df_txn["ts_val"] >= before_ts - lookback_sec)
        ]
        
        if matches.empty:
            # Fallback to any prior transaction if 30-day window is sparse
            matches = self.df_txn[
                (self.df_txn["card_id"] == card_id) &
                (self.df_txn["ts_val"] < before_ts)
            ]

        if matches.empty:
            return {
                "txn_count": 0,
                "avg_amount": 0.0,
                "max_amount": 0.0,
                "known_devices": set(),
                "known_emails": set(),
                "primary_addr1": None,
                "primary_addr2": None,
                "recurring_amounts": []
            }

        amts = matches["TransactionAmt"].dropna().tolist()
        devices = set(matches["DeviceInfo"].dropna().unique()) - {"unknown"}
        emails = set(matches["P_emaildomain"].dropna().unique()) - {"unknown"}
        
        # Primary billing address
        addr1_counts = matches["addr1"].dropna().value_counts()
        primary_addr1 = addr1_counts.index[0] if not addr1_counts.empty else None

        # Check for recurring monthly charges (amounts appearing 2+ times with similar values)
        amt_counts = matches["TransactionAmt"].value_counts()
        recurring = [float(amt) for amt, cnt in amt_counts.items() if cnt >= 2]

        return {
            "txn_count": len(matches),
            "avg_amount": float(np.mean(amts)) if amts else 0.0,
            "std_amount": float(np.std(amts)) if len(amts) > 1 else 0.0,
            "max_amount": float(np.max(amts)) if amts else 0.0,
            "known_devices": devices,
            "known_emails": emails,
            "primary_addr1": primary_addr1,
            "recurring_amounts": recurring
        }

    def expand_fraud_episode(self, card_id: str, center_ts: float, flagged_txn_id: str, window_sec: float = 86400) -> Tuple[List[str], float, str, Dict[str, Any]]:
        """
        Temporal Episode Expansion:
        Discovers all transactions on this card within time window [center_ts - window_sec, center_ts + 3600]
        belonging to the same compromise episode (card testing sequence, high velocity, or spike).
        """
        window_df = self.df_txn[
            (self.df_txn["card_id"] == card_id) &
            (self.df_txn["ts_val"] >= center_ts - window_sec) &
            (self.df_txn["ts_val"] <= center_ts + 3600)
        ].sort_values(by="ts_val")

        if window_df.empty:
            flagged = self.get_transaction_detail(flagged_txn_id)
            amt = float(flagged.get("TransactionAmt", 0.0))
            return [flagged_txn_id], amt, flagged_txn_id, {"is_card_testing": False, "testing_cleared_gt_100": False}

        # 1. Check for Card Testing Sequence: >=3 small authorizations (<$15) within 1 hour followed by larger purchase
        small_txns = window_df[
            (window_df["TransactionAmt"] < 15.0) &
            (window_df["ts_val"] >= center_ts - 3600) &
            (window_df["ts_val"] <= center_ts + 3600)
        ]
        larger_txns = window_df[
            (window_df["TransactionAmt"] >= 15.0) &
            (window_df["ts_val"] >= center_ts - 3600) &
            (window_df["ts_val"] <= center_ts + 3600)
        ]

        is_card_testing = len(small_txns) >= 3 and len(larger_txns) >= 1
        testing_cleared_gt_100 = False
        if is_card_testing:
            testing_cleared_gt_100 = any(larger_txns["TransactionAmt"] >= 100.0)
            episode_txns = sorted(list(set(small_txns["TransactionID"].tolist() + larger_txns["TransactionID"].tolist() + [flagged_txn_id])))
            total_exp = float(window_df[window_df["TransactionID"].isin(episode_txns)]["TransactionAmt"].sum())
            first_txn = episode_txns[0]
            return episode_txns, total_exp, first_txn, {
                "is_card_testing": True,
                "testing_cleared_gt_100": testing_cleared_gt_100,
                "small_txn_count": len(small_txns)
            }

        # Default episode: flagged transaction
        flagged_row = self.get_transaction_detail(flagged_txn_id)
        amt = float(flagged_row.get("TransactionAmt", 0.0))
        return [flagged_txn_id], amt, flagged_txn_id, {"is_card_testing": False, "testing_cleared_gt_100": False}

    def get_time_bounded_device_neighbors(self, device_info: str, center_ts: float, window_sec: float = 7 * 86400, exclude_card_id: str = None) -> List[Dict[str, Any]]:
        """
        Finds other distinct cards that used the same specific DeviceInfo within a 7-day window of center_ts.
        Filters out generic desktop browser engines (e.g. 'Trident/7.0', 'rv:11.0', 'Windows') that are not true hardware profiles.
        """
        if not device_info or device_info.lower() in ["unknown", "windows", "ios device", "none", "nan", "other"]:
            return []

        # Filter out generic desktop browser strings
        dev_lower = device_info.lower()
        if "trident" in dev_lower or dev_lower.startswith("rv:") or dev_lower.startswith("windows") or dev_lower.startswith("macos"):
            return []

        matches = self.df_txn[
            (self.df_txn["DeviceInfo"] == device_info) &
            (self.df_txn["ts_val"] >= center_ts - window_sec) &
            (self.df_txn["ts_val"] <= center_ts + window_sec)
        ]

        if exclude_card_id:
            matches = matches[matches["card_id"] != exclude_card_id]

        if matches.empty:
            return []

        # Return distinct cards with their transaction proximity
        unique_cards = matches.drop_duplicates(subset=["card_id"]).sort_values(by="ts_val")
        return unique_cards[["TransactionID", "card_id", "customer_id", "TransactionAmt", "ts_val"]].head(15).to_dict(orient="records")

    def find_similar_closed_cases(self, card_id: str = None, customer_id: str = None, pattern: str = None, limit: int = 5) -> List[str]:
        """Hybrid search for relevant historical closed cases from closed_cases_history."""
        if self.df_closed is None:
            return []

        matched = []
        if card_id:
            c_matches = self.df_closed[self.df_closed["card_id"] == card_id]["case_id"].tolist()
            matched.extend(c_matches)
        if customer_id:
            cust_matches = self.df_closed[self.df_closed["customer_id"] == customer_id]["case_id"].tolist()
            matched.extend(cust_matches)
        if pattern and pattern != "none":
            pat_matches = self.df_closed[self.df_closed["pattern"] == pattern]["case_id"].head(3).tolist()
            matched.extend(pat_matches)

        # Semantic search from Vector Store
        if pattern:
            vector_res = self.vector_store.search(f"{pattern} fraud investigation case", n_results=3, category="closed_case")
            for vr in vector_res:
                cid = vr.get("metadata", {}).get("case_id")
                if cid:
                    matched.append(cid)

        # Deduplicate preserving order
        return list(dict.fromkeys(matched))[:limit]

    def write_case_to_graph(self, case_id: str, case_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Persists full investigated case into TigerGraph and returns receipt.
        """
        if not self.conn:
            return False, "TigerGraph connection unavailable"

        try:
            c_obj = case_data.get("case", {})
            card_id = str(case_data.get("case", {}).get("connected_card_ids", [""]))[0] if case_data.get("case", {}).get("connected_card_ids") else ""
            
            # Upsert FraudCase vertex
            self.conn.upsertVertex("FraudCase", case_id, {
                "opened_at": str(case_data.get("opened_at", "")),
                "closed_at": str(c_obj.get("closed_at", "")),
                "outcome": str(c_obj.get("verdict", "uncertain")),
                "pattern": str(c_obj.get("pattern", "none")),
                "fraud_probability": float(c_obj.get("fraud_probability", 0.0)),
                "exposure_usd": float(c_obj.get("exposure_usd", 0.0)),
                "actions_taken": json.dumps([a.get("action") for a in case_data.get("next_best_actions", {}).get("final", [])]),
                "sar_filed": bool(case_data.get("sar", {}).get("file", False)),
                "analyst_notes": str(c_obj.get("summary", "")),
                "trigger_type": str(case_data.get("trigger_type", "")),
                "trigger_text": str(case_data.get("trigger_text", "")),
                "first_fraud_txn_id": str(c_obj.get("first_suspicious_txn_id", ""))
            })

            # Link INVOLVES_TXN for affected transactions
            affected_txns = c_obj.get("affected_txn_ids", [])
            if affected_txns:
                txn_edges = [(case_id, tid, {}) for tid in affected_txns]
                self.conn.upsertEdges("FraudCase", "INVOLVES_TXN", "Transaction", txn_edges)

            # Link INVOLVES_CARD
            involves_cards = [case_data.get("card_id")] if case_data.get("card_id") else []
            if involves_cards:
                card_edges = [(case_id, cid, {}) for cid in involves_cards]
                self.conn.upsertEdges("FraudCase", "INVOLVES_CARD", "Card", card_edges)

            return True, f"TG-RECEIPT-{case_id}"
        except Exception as e:
            print(f"[!] Error writing case {case_id} to TigerGraph: {e}")
            return False, f"Error: {e}"
