from typing import TypedDict, List, Dict, Any, Optional

class InvestigationState(TypedDict, total=False):
    # Case metadata
    case_id: str
    opened_at: str
    trigger_type: str
    trigger_text: str
    flagged_txn_id: str
    card_id: str
    customer_id: str
    risk_score: float

    # Graph Evidence gathered
    flagged_txn: Dict[str, Any]
    card_history: List[Dict[str, Any]]
    window_txns: List[Dict[str, Any]]
    device_neighbors: List[Dict[str, Any]]
    connected_cards: List[str]
    connected_device_profiles: List[str]
    similar_cases: List[str]
    evidence_claims: List[Dict[str, Any]]

    # Step 1: Initial Assessment
    initial_verdict: str
    initial_prob: float
    initial_pattern: str
    initial_pattern_desc: str
    initial_actions: List[Dict[str, str]]
    initial_exposure_usd: float
    affected_txn_ids: List[str]
    first_suspicious_txn_id: str

    # Step 2: Evidence Request & Simulation
    evidence_requests: List[Dict[str, Any]]
    simulated_reply: str

    # Step 3: Final Assessment & Policy
    final_verdict: str
    final_prob: float
    final_pattern: str
    final_pattern_desc: str
    final_actions: List[Dict[str, str]]
    what_changed: str
    final_exposure_usd: float
    status: str

    # SAR Report
    sar_file: bool
    sar_reason: str
    sar_narrative: str
    sar_subjects: List[str]
    sar_amount: float
    sar_dates: List[str]

    # Meta
    summary: str
    stop_reason: str
    written_to_graph: bool
    graph_case_id: str
    tool_calls: int
    tokens: int
    latency_s: float
