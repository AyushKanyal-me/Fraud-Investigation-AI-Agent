"""
LangChain structured tools for TigerGraph, GraphRAG Vector Store, and Case Memory.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.tools import tool

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.tools import GraphTools
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.simulator import CustomerSimulator

def create_agent_tools(
    graph_tools: Optional[GraphTools] = None,
    vector_store: Optional[FraudVectorStore] = None,
    memory: Optional[CaseMemory] = None,
    simulator: Optional[CustomerSimulator] = None
):
    """Factory creating bound LangChain tool functions for the investigation workflow."""
    gt = graph_tools or GraphTools()
    vs = vector_store or FraudVectorStore()
    mem = memory or CaseMemory()
    sim = simulator or CustomerSimulator()

    @tool
    def get_transaction_metadata(txn_id: str) -> str:
        """Fetches full transaction record including card_id, customer_id, amount, timestamp, device, and email."""
        data = gt.get_transaction_detail(txn_id)
        return json.dumps(data, default=str)

    @tool
    def query_card_spending_baseline(card_id: str, before_ts: float) -> str:
        """Calculates 30-day spending baseline strictly prior to before_ts (preventing lookahead bias)."""
        data = gt.get_time_bounded_card_baseline(card_id=card_id, before_ts=before_ts)
        # Convert sets to lists for JSON serialization
        clean_data = {
            k: list(v) if isinstance(v, set) else v
            for k, v in data.items()
        }
        return json.dumps(clean_data, default=str)

    @tool
    def expand_fraud_episode(card_id: str, center_ts: float, flagged_txn_id: str) -> str:
        """Discovers all transactions on this card in the temporal compromise window (micro-testing or burst)."""
        affected_txns, exposure, first_txn, meta = gt.expand_fraud_episode(
            card_id=card_id, center_ts=center_ts, flagged_txn_id=flagged_txn_id
        )
        return json.dumps({
            "affected_txn_ids": affected_txns,
            "exposure_usd": exposure,
            "first_suspicious_txn_id": first_txn,
            "meta": meta
        }, default=str)

    @tool
    def query_device_and_ring_neighbors(device_info: str, center_ts: float, exclude_card_id: str = None) -> str:
        """Finds other distinct cards sharing the same hardware profile within a 7-day window."""
        neighbors = gt.get_time_bounded_device_neighbors(
            device_info=device_info, center_ts=center_ts, exclude_card_id=exclude_card_id
        )
        return json.dumps(neighbors, default=str)

    @tool
    def search_fraud_regulations_and_policy(query: str, category: Optional[str] = None) -> str:
        """Searches ChromaDB vector store for bank fraud policy rules, FinCEN SAR guidance, or closed cases."""
        results = vs.search(query=query, n_results=3, category=category)
        return json.dumps(results, default=str)

    @tool
    def search_cross_case_memory(card_id: Optional[str] = None, device_info: Optional[str] = None, email: Optional[str] = None) -> str:
        """Checks cross-case memory for prior compromised cards, repeat offender devices, or suspicious emails."""
        hits = mem.check_entity_history(card_id=card_id, device_info=device_info, email=email)
        return json.dumps(hits, default=str)

    return [
        get_transaction_metadata,
        query_card_spending_baseline,
        expand_fraud_episode,
        query_device_and_ring_neighbors,
        search_fraud_regulations_and_policy,
        search_cross_case_memory
    ], {
        "graph_tools": gt,
        "vector_store": vs,
        "memory": mem,
        "simulator": sim
    }
