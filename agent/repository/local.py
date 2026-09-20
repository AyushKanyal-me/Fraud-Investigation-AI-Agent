import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import DATASET_DIR
from agent.card_identity import get_canonical_card_mapper
from agent.repository.base import (
    FraudDataRepository,
    TransactionRecord,
    CardBaseline,
    EpisodeWindow,
    DeviceNeighbor,
    ClosedCaseRecord
)

class LocalFraudRepository(FraudDataRepository):
    """
    In-memory / Local Pandas-backed implementation of FraudDataRepository with shared dataset caching.
    """
    _df_txn = None
    _df_txn_by_id = None
    _df_id = None
    _df_closed = None

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir else DATASET_DIR
        self.card_mapper = get_canonical_card_mapper()
        self._load_indices()

    def _load_indices(self):
        if LocalFraudRepository._df_txn is not None:
            self.df_txn = LocalFraudRepository._df_txn
            self.df_txn_by_id = LocalFraudRepository._df_txn_by_id
            self.df_id = LocalFraudRepository._df_id
            self.df_closed = LocalFraudRepository._df_closed
            return

        txn_path = self.dataset_dir / "transactions.csv"
        if not txn_path.exists():
            fixture_path = BASE_DIR / "tests" / "fixtures" / "sample_transactions.csv"
            if fixture_path.exists():
                txn_path = fixture_path

        id_path = self.dataset_dir / "identity.csv"
        closed_path = self.dataset_dir / "closed_cases_history.csv"

        df_id = None
        if id_path.exists():
            df_id = pd.read_csv(id_path, dtype={"TransactionID": str})
            df_id.set_index("TransactionID", inplace=True)

        df_closed = None
        if closed_path.exists():
            df_closed = pd.read_csv(closed_path, dtype=str)

        if txn_path.exists():
            df_txn = pd.read_csv(
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
        else:
            df_txn = pd.DataFrame(columns=[
                "TransactionID", "customer_id", "ProductCD", "P_emaildomain", "R_emaildomain",
                "card1", "card2", "card3", "card4", "card5", "card6",
                "addr1", "addr2", "dist1", "dist2", "TransactionAmt", "TransactionDT", "risk_score"
            ])

        df_txn = df_txn.copy()

        # Parse numeric timestamp
        if "TransactionDT" in df_txn.columns:
            df_txn["ts_val"] = df_txn["TransactionDT"].fillna(0.0).astype(float)
        else:
            df_txn["ts_val"] = pd.to_datetime(df_txn["ts"], errors="coerce").astype("int64") // 10**9

        # Canonical Card Mapping
        tuples = list(zip(
            df_txn["customer_id"].fillna("CUST_UNK"),
            df_txn["card1"].fillna("-1").astype(str),
            df_txn["card2"].fillna("-1").astype(str),
            df_txn["card3"].fillna("-1").astype(str),
            df_txn["card4"].fillna("unk").astype(str),
            df_txn["card5"].fillna("-1").astype(str),
            df_txn["card6"].fillna("unk").astype(str)
        ))
        df_txn["card_id"] = [
            self.card_mapper.tuple_to_card.get(t, f"{t[0]}-K1")
            for t in tuples
        ]

        # Merge Identity Metadata
        if df_id is not None:
            id_cols = [c for c in ["DeviceType", "DeviceInfo", "id_31", "id_30", "id_33"] if c in df_id.columns]
            df_txn = df_txn.join(df_id[id_cols], on="TransactionID")
        else:
            df_txn["DeviceType"] = "unknown"
            df_txn["DeviceInfo"] = "unknown"

        df_txn["DeviceType"] = df_txn.get("DeviceType", pd.Series(["unknown"]*len(df_txn))).fillna("unknown")
        df_txn["DeviceInfo"] = df_txn.get("DeviceInfo", pd.Series(["unknown"]*len(df_txn))).fillna("unknown")

        df_txn_by_id = df_txn.set_index("TransactionID")

        LocalFraudRepository._df_txn = df_txn
        LocalFraudRepository._df_txn_by_id = df_txn_by_id
        LocalFraudRepository._df_id = df_id
        LocalFraudRepository._df_closed = df_closed

        self.df_txn = df_txn
        self.df_txn_by_id = df_txn_by_id
        self.df_id = df_id
        self.df_closed = df_closed

    def get_transaction_detail(self, transaction_id: str) -> Optional[TransactionRecord]:
        tid_str = str(transaction_id)
        if tid_str not in self.df_txn_by_id.index:
            return None
        
        row = self.df_txn_by_id.loc[tid_str]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        row_dict = row.to_dict()
        return TransactionRecord(
            transaction_id=tid_str,
            card_id=str(row_dict.get("card_id", "")),
            customer_id=str(row_dict.get("customer_id", "")),
            amount=float(row_dict.get("TransactionAmt", 0.0)),
            ts_val=float(row_dict.get("ts_val", 0.0)),
            channel=str(row_dict.get("channel", "online")),
            risk_score=float(row_dict.get("risk_score", 0.0)) if pd.notna(row_dict.get("risk_score")) else 0.0,
            product_cd=str(row_dict.get("ProductCD", "W")),
            card1=str(row_dict.get("card1", "-1")),
            card2=str(row_dict.get("card2", "-1")),
            card3=str(row_dict.get("card3", "-1")),
            card4=str(row_dict.get("card4", "unk")),
            card5=str(row_dict.get("card5", "-1")),
            card6=str(row_dict.get("card6", "unk")),
            addr1=str(row_dict.get("addr1")) if pd.notna(row_dict.get("addr1")) else None,
            addr2=str(row_dict.get("addr2")) if pd.notna(row_dict.get("addr2")) else None,
            dist1=str(row_dict.get("dist1")) if pd.notna(row_dict.get("dist1")) else None,
            dist2=str(row_dict.get("dist2")) if pd.notna(row_dict.get("dist2")) else None,
            p_emaildomain=str(row_dict.get("P_emaildomain")) if pd.notna(row_dict.get("P_emaildomain")) else None,
            r_emaildomain=str(row_dict.get("R_emaildomain")) if pd.notna(row_dict.get("R_emaildomain")) else None,
            device_type=str(row_dict.get("DeviceType", "unknown")),
            device_info=str(row_dict.get("DeviceInfo", "unknown")),
            id_30=str(row_dict.get("id_30")) if pd.notna(row_dict.get("id_30")) else None,
            id_31=str(row_dict.get("id_31")) if pd.notna(row_dict.get("id_31")) else None,
            id_33=str(row_dict.get("id_33")) if pd.notna(row_dict.get("id_33")) else None,
            raw_data=row_dict
        )

    def get_card_baseline(self, card_id: str, before_ts: float, lookback_sec: float = 30 * 86400) -> CardBaseline:
        matches = self.df_txn[
            (self.df_txn["card_id"] == card_id) &
            (self.df_txn["ts_val"] < before_ts) &
            (self.df_txn["ts_val"] >= before_ts - lookback_sec)
        ]
        
        if matches.empty:
            matches = self.df_txn[
                (self.df_txn["card_id"] == card_id) &
                (self.df_txn["ts_val"] < before_ts)
            ]

        if matches.empty:
            return CardBaseline()

        amts = matches["TransactionAmt"].dropna().tolist()
        devices = set(matches["DeviceInfo"].dropna().unique()) - {"unknown"}
        emails = set(matches["P_emaildomain"].dropna().unique()) - {"unknown"}
        
        addr1_counts = matches["addr1"].dropna().value_counts()
        primary_addr1 = str(addr1_counts.index[0]) if not addr1_counts.empty else None

        amt_counts = matches["TransactionAmt"].value_counts()
        recurring = [float(amt) for amt, cnt in amt_counts.items() if cnt >= 2]

        return CardBaseline(
            txn_count=len(matches),
            avg_amount=float(np.mean(amts)) if amts else 0.0,
            std_amount=float(np.std(amts)) if len(amts) > 1 else 0.0,
            max_amount=float(np.max(amts)) if amts else 0.0,
            known_devices=devices,
            known_emails=emails,
            primary_addr1=primary_addr1,
            recurring_amounts=recurring
        )

    def expand_fraud_episode(self, card_id: str, center_ts: float, flagged_txn_id: str, window_sec: float = 86400) -> EpisodeWindow:
        window_df = self.df_txn[
            (self.df_txn["card_id"] == card_id) &
            (self.df_txn["ts_val"] >= center_ts - window_sec) &
            (self.df_txn["ts_val"] <= center_ts + 3600)
        ].sort_values(by="ts_val")

        if window_df.empty:
            flagged = self.get_transaction_detail(flagged_txn_id)
            amt = flagged.amount if flagged else 0.0
            return EpisodeWindow(
                affected_txn_ids=[flagged_txn_id],
                exposure_usd=amt,
                first_suspicious_txn_id=flagged_txn_id,
                metadata={"is_card_testing": False, "testing_cleared_gt_100": False}
            )

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
        if is_card_testing:
            testing_cleared_gt_100 = any(larger_txns["TransactionAmt"] >= 100.0)
            episode_txns = sorted(list(set(small_txns["TransactionID"].tolist() + larger_txns["TransactionID"].tolist() + [flagged_txn_id])))
            total_exp = float(window_df[window_df["TransactionID"].isin(episode_txns)]["TransactionAmt"].sum())
            first_txn = episode_txns[0]
            return EpisodeWindow(
                affected_txn_ids=episode_txns,
                exposure_usd=total_exp,
                first_suspicious_txn_id=first_txn,
                metadata={
                    "is_card_testing": True,
                    "testing_cleared_gt_100": testing_cleared_gt_100,
                    "small_txn_count": len(small_txns)
                }
            )

        flagged_rec = self.get_transaction_detail(flagged_txn_id)
        amt = flagged_rec.amount if flagged_rec else 0.0
        return EpisodeWindow(
            affected_txn_ids=[flagged_txn_id],
            exposure_usd=amt,
            first_suspicious_txn_id=flagged_txn_id,
            metadata={"is_card_testing": False, "testing_cleared_gt_100": False}
        )

    def get_device_neighbors(self, device_info: str, center_ts: float, window_sec: float = 7 * 86400, exclude_card_id: Optional[str] = None) -> List[DeviceNeighbor]:
        if not device_info or device_info.lower() in ["unknown", "windows", "ios device", "none", "nan", "other"]:
            return []

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

        neighbors: List[DeviceNeighbor] = []
        for (cid, cust_id), grp in matches.groupby(["card_id", "customer_id"]):
            neighbors.append(DeviceNeighbor(
                card_id=str(cid),
                customer_id=str(cust_id),
                txn_count=len(grp),
                total_amount=float(grp["TransactionAmt"].sum()),
                device_info=device_info,
                device_type=str(grp["DeviceType"].iloc[0]) if "DeviceType" in grp.columns else "unknown"
            ))
        return neighbors

    def get_similar_closed_cases(self, pattern: Optional[str] = None, customer_id: Optional[str] = None, top_k: int = 3) -> List[ClosedCaseRecord]:
        if self.df_closed is None or self.df_closed.empty:
            return []

        df_filtered = self.df_closed
        if pattern and pattern != "none":
            pattern_matches = df_filtered[df_filtered["pattern"] == pattern]
            if not pattern_matches.empty:
                df_filtered = pattern_matches

        records: List[ClosedCaseRecord] = []
        for _, row in df_filtered.head(top_k).iterrows():
            records.append(ClosedCaseRecord(
                case_id=str(row.get("case_id", "")),
                customer_id=str(row.get("customer_id", "")),
                card_id=str(row.get("card_id", "")),
                outcome=str(row.get("outcome", "")),
                pattern=str(row.get("pattern", "")),
                exposure_usd=float(row.get("exposure_usd", 0.0)) if pd.notna(row.get("exposure_usd")) else 0.0,
                actions_taken=str(row.get("actions_taken", "")),
                report_filed=str(row.get("report_filed", "")).lower() in ("true", "1", "yes"),
                analyst_notes=str(row.get("analyst_notes", ""))
            ))
        return records

    def persist_case_graph(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        return True
