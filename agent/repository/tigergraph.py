import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME,
    TG_SECRET, TG_API_TOKEN
)
from agent.repository.base import (
    FraudDataRepository,
    TransactionRecord,
    CardBaseline,
    EpisodeWindow,
    DeviceNeighbor,
    ClosedCaseRecord
)
from agent.repository.local import LocalFraudRepository

class TigerGraphFraudRepository(FraudDataRepository):
    """
    TigerGraph-backed implementation of FraudDataRepository using pyTigerGraph / GSQL REST queries.
    Maintains semantic parity with LocalFraudRepository while executing graph-native traversals.
    """
    def __init__(self, fallback_local: Optional[LocalFraudRepository] = None):
        self.conn = None
        self.fallback_local = fallback_local or LocalFraudRepository()
        self._init_tg()

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
            self.conn = None

    def is_connected(self) -> bool:
        return self.conn is not None

    def get_transaction_detail(self, transaction_id: str) -> Optional[TransactionRecord]:
        if not self.conn:
            return self.fallback_local.get_transaction_detail(transaction_id)
        try:
            res = self.conn.runInstalledQuery("transaction_detail", {"t": str(transaction_id)})
            if res and len(res) > 0:
                txn_data = res[0].get("TxnSet", [])
                if txn_data:
                    attrs = txn_data[0].get("attributes", {})
                    return TransactionRecord(
                        transaction_id=str(transaction_id),
                        card_id=str(attrs.get("card_id", "")),
                        customer_id=str(attrs.get("customer_id", "")),
                        amount=float(attrs.get("amount", 0.0)),
                        ts_val=float(attrs.get("ts", 0.0)),
                        channel=str(attrs.get("channel", "online")),
                        risk_score=float(attrs.get("risk_score", 0.0)),
                        product_cd=str(attrs.get("ProductCD", "W")),
                        addr1=str(attrs.get("addr1")) if attrs.get("addr1") is not None else None,
                        addr2=str(attrs.get("addr2")) if attrs.get("addr2") is not None else None,
                        p_emaildomain=attrs.get("P_emaildomain"),
                        r_emaildomain=attrs.get("R_emaildomain"),
                        device_type=attrs.get("DeviceType", "unknown"),
                        device_info=attrs.get("DeviceInfo", "unknown"),
                        raw_data=attrs
                    )
        except Exception:
            pass
        return self.fallback_local.get_transaction_detail(transaction_id)

    def get_card_baseline(self, card_id: str, before_ts: float, lookback_sec: float = 30 * 86400) -> CardBaseline:
        if not self.conn:
            return self.fallback_local.get_card_baseline(card_id, before_ts, lookback_sec)
        try:
            res = self.conn.runInstalledQuery("card_history", {
                "c": str(card_id),
                "before_ts": int(before_ts),
                "lookback_sec": int(lookback_sec)
            })
            if res and len(res) > 0:
                stats = res[0].get("Stats", {})
                if stats:
                    return CardBaseline(
                        txn_count=int(stats.get("txn_count", 0)),
                        avg_amount=float(stats.get("avg_amount", 0.0)),
                        std_amount=float(stats.get("std_amount", 0.0)),
                        max_amount=float(stats.get("max_amount", 0.0)),
                        known_devices=set(stats.get("devices", [])),
                        known_emails=set(stats.get("emails", [])),
                        primary_addr1=stats.get("primary_addr1")
                    )
        except Exception:
            pass
        return self.fallback_local.get_card_baseline(card_id, before_ts, lookback_sec)

    def expand_fraud_episode(self, card_id: str, center_ts: float, flagged_txn_id: str, window_sec: float = 86400) -> EpisodeWindow:
        if not self.conn:
            return self.fallback_local.expand_fraud_episode(card_id, center_ts, flagged_txn_id, window_sec)
        try:
            res = self.conn.runInstalledQuery("card_testing_detection", {
                "c": str(card_id),
                "center_ts": int(center_ts),
                "window_sec": int(window_sec)
            })
            if res and len(res) > 0:
                data = res[0]
                txns = [str(t.get("v_id")) for t in data.get("EpisodeTxns", [])]
                if txns:
                    return EpisodeWindow(
                        affected_txn_ids=txns,
                        exposure_usd=float(data.get("TotalExposure", 0.0)),
                        first_suspicious_txn_id=txns[0],
                        metadata={
                            "is_card_testing": bool(data.get("IsCardTesting", False)),
                            "testing_cleared_gt_100": bool(data.get("ClearedGt100", False))
                        }
                    )
        except Exception:
            pass
        return self.fallback_local.expand_fraud_episode(card_id, center_ts, flagged_txn_id, window_sec)

    def get_device_neighbors(self, device_info: str, center_ts: float, window_sec: float = 7 * 86400, exclude_card_id: Optional[str] = None) -> List[DeviceNeighbor]:
        if not self.conn:
            return self.fallback_local.get_device_neighbors(device_info, center_ts, window_sec, exclude_card_id)
        try:
            res = self.conn.runInstalledQuery("device_neighbors", {"dev": str(device_info)})
            if res and len(res) > 0:
                cards = res[0].get("Cards", [])
                neighbors = []
                for c in cards:
                    cid = str(c.get("v_id"))
                    if exclude_card_id and cid == exclude_card_id:
                        continue
                    neighbors.append(DeviceNeighbor(
                        card_id=cid,
                        customer_id=str(c.get("attributes", {}).get("customer_id", "")),
                        txn_count=int(c.get("attributes", {}).get("total_txns", 1)),
                        total_amount=float(c.get("attributes", {}).get("total_amt", 0.0)),
                        device_info=device_info
                    ))
                if neighbors:
                    return neighbors
        except Exception:
            pass
        return self.fallback_local.get_device_neighbors(device_info, center_ts, window_sec, exclude_card_id)

    def get_similar_closed_cases(self, pattern: Optional[str] = None, customer_id: Optional[str] = None, top_k: int = 3) -> List[ClosedCaseRecord]:
        if not self.conn:
            return self.fallback_local.get_similar_closed_cases(pattern, customer_id, top_k)
        try:
            res = self.conn.runInstalledQuery("similar_closed_cases", {"pattern_filter": pattern or ""})
            if res and len(res) > 0:
                cases = res[0].get("SimilarCases", [])
                records = []
                for c in cases[:top_k]:
                    attrs = c.get("attributes", {})
                    records.append(ClosedCaseRecord(
                        case_id=str(c.get("v_id")),
                        customer_id=str(attrs.get("customer_id", "")),
                        card_id=str(attrs.get("card_id", "")),
                        outcome=str(attrs.get("outcome", "")),
                        pattern=str(attrs.get("pattern", "")),
                        exposure_usd=float(attrs.get("exposure_usd", 0.0)),
                        actions_taken=str(attrs.get("actions_taken", "")),
                        report_filed=bool(attrs.get("sar_filed", False)),
                        analyst_notes=str(attrs.get("analyst_notes", ""))
                    ))
                if records:
                    return records
        except Exception:
            pass
        return self.fallback_local.get_similar_closed_cases(pattern, customer_id, top_k)

    def persist_case_graph(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        if not self.conn:
            return self.fallback_local.persist_case_graph(case_id, case_data)
        try:
            c_obj = case_data.get("case", {})
            self.conn.runInstalledQuery("write_case", {
                "case_id": str(case_id),
                "status": str(c_obj.get("status", "closed_fraud")),
                "verdict": str(c_obj.get("verdict", "fraud")),
                "pattern": str(c_obj.get("pattern", "none")),
                "prob": float(c_obj.get("fraud_probability", 0.0)),
                "exposure": float(c_obj.get("exposure_usd", 0.0))
            })
            return True
        except Exception:
            return self.fallback_local.persist_case_graph(case_id, case_data)
