import abc
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple

@dataclass
class TransactionRecord:
    transaction_id: str
    card_id: str
    customer_id: str
    amount: float
    ts_val: float
    channel: str = "online"
    risk_score: float = 0.0
    product_cd: str = "W"
    card1: str = "-1"
    card2: str = "-1"
    card3: str = "-1"
    card4: str = "unk"
    card5: str = "-1"
    card6: str = "unk"
    addr1: Optional[str] = None
    addr2: Optional[str] = None
    dist1: Optional[str] = None
    dist2: Optional[str] = None
    p_emaildomain: Optional[str] = None
    r_emaildomain: Optional[str] = None
    device_type: Optional[str] = "unknown"
    device_info: Optional[str] = "unknown"
    id_30: Optional[str] = None  # OS
    id_31: Optional[str] = None  # Browser
    id_33: Optional[str] = None  # Screen resolution
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "TransactionID": self.transaction_id,
            "card_id": self.card_id,
            "customer_id": self.customer_id,
            "TransactionAmt": self.amount,
            "ts_val": self.ts_val,
            "channel": self.channel,
            "risk_score": self.risk_score,
            "ProductCD": self.product_cd,
            "card1": self.card1,
            "card2": self.card2,
            "card3": self.card3,
            "card4": self.card4,
            "card5": self.card5,
            "card6": self.card6,
            "addr1": self.addr1,
            "addr2": self.addr2,
            "dist1": self.dist1,
            "dist2": self.dist2,
            "P_emaildomain": self.p_emaildomain,
            "R_emaildomain": self.r_emaildomain,
            "DeviceType": self.device_type,
            "DeviceInfo": self.device_info,
            "id_30": self.id_30,
            "id_31": self.id_31,
            "id_33": self.id_33
        }
        if self.raw_data:
            for k, v in self.raw_data.items():
                if k not in d:
                    d[k] = v
        return d

@dataclass
class CardBaseline:
    txn_count: int = 0
    avg_amount: float = 0.0
    std_amount: float = 0.0
    max_amount: float = 0.0
    known_devices: Set[str] = field(default_factory=set)
    known_emails: Set[str] = field(default_factory=set)
    primary_addr1: Optional[str] = None
    primary_addr2: Optional[str] = None
    recurring_amounts: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_count": self.txn_count,
            "avg_amount": self.avg_amount,
            "std_amount": self.std_amount,
            "max_amount": self.max_amount,
            "known_devices": self.known_devices,
            "known_emails": self.known_emails,
            "primary_addr1": self.primary_addr1,
            "primary_addr2": self.primary_addr2,
            "recurring_amounts": self.recurring_amounts
        }

@dataclass
class EpisodeWindow:
    affected_txn_ids: List[str]
    exposure_usd: float
    first_suspicious_txn_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeviceNeighbor:
    card_id: str
    customer_id: str
    txn_count: int
    total_amount: float
    device_info: str
    device_type: str = "unknown"

@dataclass
class ClosedCaseRecord:
    case_id: str
    customer_id: str
    card_id: str
    outcome: str
    pattern: str
    exposure_usd: float
    actions_taken: str
    report_filed: bool
    analyst_notes: str

class FraudDataRepository(abc.ABC):
    """
    Abstract Data Repository interface decoupling business logic from storage backends.
    """
    @abc.abstractmethod
    def get_transaction_detail(self, transaction_id: str) -> Optional[TransactionRecord]:
        """Fetches complete transaction record by ID."""
        pass

    @abc.abstractmethod
    def get_card_baseline(self, card_id: str, before_ts: float, lookback_sec: float = 30 * 86400) -> CardBaseline:
        """Calculates spending baseline strictly prior to before_ts."""
        pass

    @abc.abstractmethod
    def expand_fraud_episode(self, card_id: str, center_ts: float, flagged_txn_id: str, window_sec: float = 86400) -> EpisodeWindow:
        """Discovers transactions belonging to the same compromise episode."""
        pass

    @abc.abstractmethod
    def get_device_neighbors(self, device_info: str, center_ts: float, window_sec: float = 7 * 86400, exclude_card_id: Optional[str] = None) -> List[DeviceNeighbor]:
        """Finds other cards sharing the same hardware profile within a time window."""
        pass

    @abc.abstractmethod
    def get_similar_closed_cases(self, pattern: Optional[str] = None, customer_id: Optional[str] = None, top_k: int = 3) -> List[ClosedCaseRecord]:
        """Retrieves similar historical closed cases."""
        pass

    @abc.abstractmethod
    def persist_case_graph(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        """Persists a closed/investigated case into the graph store."""
        pass
