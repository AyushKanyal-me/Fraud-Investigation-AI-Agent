"""
FastAPI Server for TigerGraph Agentic Fraud Investigation System.
Exposes REST endpoints for the Frontend UI dashboard, graph visualizer, and LangGraph live runner.
"""

import os
import sys
import json
import time
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import DATASET_DIR, ANSWERS_DIR, POLICY_RULES, ACTION_TYPES, APPROVAL_ROUTES
from agent.tools import GraphTools
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.workflow import FraudInvestigationWorkflow

# Initialize FastAPI App
app = FastAPI(
    title="TigerGraph Agentic Fraud Investigation API",
    description="Backend API powering the Agentic Fraud Investigation UI, Graph Visualizer, and Policy Engine.",
    version="2.0.0"
)

# Enable CORS for Frontend Development (supports React, Next.js, Vite, Vue, Angular)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Singletons
vector_store = FraudVectorStore()
memory = CaseMemory()
tools = GraphTools(vector_store=vector_store)
workflow = FraudInvestigationWorkflow(tools=tools, memory=memory, vector_store=vector_store)

# Pydantic Schemas
class CustomInvestigateRequest(BaseModel):
    case_id: str
    opened_at: Optional[str] = "2016-12-30 12:00:00"
    trigger_type: str = "risk_score"  # "risk_score" | "customer_report" | "analyst_request"
    trigger_text: Optional[str] = "Real-time model risk threshold exceeded"
    flagged_txn_id: str
    card_id: Optional[str] = ""
    customer_id: Optional[str] = ""
    risk_score: Optional[float] = 0.85

# -------------------------------------------------------------
# 1. Health & System Metrics
# -------------------------------------------------------------
@app.get("/api/health", tags=["System"])
def get_health():
    """Returns server and subsystem health status."""
    return {
        "status": "healthy",
        "agent_engine": "LangGraph StateGraph 2.0",
        "vector_store_docs": vector_store.collection.count() if vector_store.collection else len(vector_store.documents),
        "memory_cases_count": len(memory.cases),
        "tigergraph_connected": tools.conn is not None,
        "dataset_transactions_loaded": len(tools.df_txn) if hasattr(tools, "df_txn") else 0
    }

@app.get("/api/stats", tags=["Dashboard"])
def get_dashboard_stats():
    """Aggregates high-level statistics across all investigated cases."""
    answers = []
    if ANSWERS_DIR.exists():
        for p in ANSWERS_DIR.glob("*.json"):
            try:
                with open(p, "r") as f:
                    answers.append(json.load(f))
            except Exception:
                pass

    total = len(answers)
    fraud_count = sum(1 for a in answers if a.get("case", {}).get("verdict") == "fraud")
    legit_count = sum(1 for a in answers if a.get("case", {}).get("verdict") == "legitimate")
    uncertain_count = sum(1 for a in answers if a.get("case", {}).get("verdict") == "uncertain")
    sar_count = sum(1 for a in answers if a.get("sar", {}).get("file") is True)
    total_exposure = sum(float(a.get("case", {}).get("exposure_usd", 0.0)) for a in answers)
    avg_latency = (
        round(sum(float(a.get("latency_s", 0.0)) for a in answers) / total, 2)
        if total > 0 else 0.0
    )

    return {
        "total_cases": total,
        "fraud_cases": fraud_count,
        "legitimate_cases": legit_count,
        "uncertain_cases": uncertain_count,
        "sars_filed": sar_count,
        "total_exposure_usd": round(total_exposure, 2),
        "average_latency_s": avg_latency
    }

# -------------------------------------------------------------
# 2. Case Listing & Detail
# -------------------------------------------------------------
@app.get("/api/cases", tags=["Cases"])
def list_cases(status: Optional[str] = Query(None, description="Filter by status: fraud, legitimate, uncertain")):
    """Returns the list of all cases in the case pack with their investigated summaries."""
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    df_cases = pd.read_csv(case_pack_file)
    case_list = []

    for _, row in df_cases.iterrows():
        cid = str(row["case_id"])
        ans_file = ANSWERS_DIR / f"{cid}.json"
        
        investigated = False
        verdict = "uninvestigated"
        prob = None
        pattern = "unknown"
        exposure = 0.0
        sar_file = False
        summary = ""

        if ans_file.exists():
            try:
                with open(ans_file, "r") as f:
                    cdata = json.load(f)
                    c_obj = cdata.get("case", {})
                    investigated = True
                    verdict = c_obj.get("verdict", "uncertain")
                    prob = c_obj.get("fraud_probability")
                    pattern = c_obj.get("pattern", "none")
                    exposure = c_obj.get("exposure_usd", 0.0)
                    summary = c_obj.get("summary", "")
                    sar_file = cdata.get("sar", {}).get("file", False)
            except Exception:
                pass

        if status and status.lower() != "all" and verdict != status.lower():
            continue

        case_list.append({
            "case_id": cid,
            "opened_at": str(row["opened_at"]),
            "trigger_type": str(row["trigger_type"]),
            "trigger_text": str(row["trigger_text"]),
            "flagged_txn_id": str(row["flagged_txn_id"]),
            "card_id": str(row.get("card_id", "")),
            "customer_id": str(row.get("customer_id", "")),
            "risk_score": float(row["risk_score"]) if pd.notna(row.get("risk_score")) else None,
            "investigated": investigated,
            "verdict": verdict,
            "fraud_probability": prob,
            "pattern": pattern,
            "exposure_usd": exposure,
            "sar_filed": sar_file,
            "summary": summary
        })

    return case_list

@app.get("/api/cases/{case_id}", tags=["Cases"])
def get_case_detail(case_id: str):
    """Returns the full investigation JSON payload for a given case_id."""
    ans_file = ANSWERS_DIR / f"{case_id}.json"
    if ans_file.exists():
        with open(ans_file, "r") as f:
            return json.load(f)

    # If not yet saved, try finding in case_pack and running
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if case_pack_file.exists():
        df_cases = pd.read_csv(case_pack_file)
        matches = df_cases[df_cases["case_id"] == case_id]
        if not matches.empty:
            result = workflow.run_investigation(matches.iloc[0].to_dict())
            with open(ans_file, "w") as f:
                json.dump(result, f, indent=2)
            return result

    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

# -------------------------------------------------------------
# 3. Live Investigation Endpoints
# -------------------------------------------------------------
@app.post("/api/cases/{case_id}/investigate", tags=["Investigation"])
def trigger_investigation(case_id: str):
    """Triggers live LangGraph investigation for a case and updates the answer artifacts."""
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    df_cases = pd.read_csv(case_pack_file)
    matches = df_cases[df_cases["case_id"] == case_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")

    case_row = matches.iloc[0].to_dict()
    result = workflow.run_investigation(case_row)

    # Save to disk
    ans_file = ANSWERS_DIR / f"{case_id}.json"
    cases_file = BASE_DIR / "cases" / f"{case_id}.json"
    with open(ans_file, "w") as f:
        json.dump(result, f, indent=2)
    with open(cases_file, "w") as f:
        json.dump(result, f, indent=2)

    return result

@app.post("/api/investigate/custom", tags=["Investigation"])
def investigate_custom_transaction(req: CustomInvestigateRequest):
    """Investigates an arbitrary transaction or alert payload using the full LangGraph pipeline."""
    case_dict = req.dict()
    result = workflow.run_investigation(case_dict)
    return result

# -------------------------------------------------------------
# 4. Interactive Graph Visualizer Subgraph (Cytoscape / D3 format)
# -------------------------------------------------------------
@app.get("/api/graph/{case_id}", tags=["Graph Visualizer"])
def get_case_subgraph(case_id: str):
    """
    Returns node-link graph data (nodes & edges) for interactive rendering in the frontend.
    Compatible with Cytoscape.js, Vis.js, D3.js, and ECharts.
    """
    ans_file = ANSWERS_DIR / f"{case_id}.json"
    if not ans_file.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    with open(ans_file, "r") as f:
        case_data = json.load(f)

    c_obj = case_data.get("case", {})
    verdict = c_obj.get("verdict", "uncertain")
    flagged_txn_id = ""
    
    # Lookup case pack for base metadata
    case_pack_file = DATASET_DIR / "case_pack.csv"
    customer_id = ""
    card_id = ""
    if case_pack_file.exists():
        df_cp = pd.read_csv(case_pack_file)
        cp_row = df_cp[df_cp["case_id"] == case_id]
        if not cp_row.empty:
            flagged_txn_id = str(cp_row.iloc[0]["flagged_txn_id"])
            customer_id = str(cp_row.iloc[0].get("customer_id", ""))
            card_id = str(cp_row.iloc[0].get("card_id", ""))

    txn_meta = tools.get_transaction_detail(flagged_txn_id) if flagged_txn_id else {}
    if not card_id and txn_meta.get("card_id"):
        card_id = txn_meta["card_id"]
    if not customer_id and txn_meta.get("customer_id"):
        customer_id = txn_meta["customer_id"]

    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(node_id: str, label: str, node_type: str, properties: Dict[str, Any] = None):
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            nodes.append({
                "id": node_id,
                "label": label,
                "type": node_type,
                "data": properties or {}
            })

    def add_edge(source: str, target: str, label: str, properties: Dict[str, Any] = None):
        edges.append({
            "id": f"e_{source}_{target}_{label}",
            "source": source,
            "target": target,
            "label": label,
            "data": properties or {}
        })

    # 1. FraudCase Node
    case_node_id = f"CASE-{case_id}"
    add_node(case_node_id, f"Case {case_id}", "FraudCase", {
        "verdict": verdict,
        "pattern": c_obj.get("pattern"),
        "exposure_usd": c_obj.get("exposure_usd", 0.0),
        "status": c_obj.get("status")
    })

    # 2. Customer Node
    if customer_id:
        add_node(customer_id, f"Customer {customer_id}", "Customer")
        add_edge(case_node_id, customer_id, "INVOLVES_CUSTOMER")

    # 3. Primary Card Node
    if card_id:
        add_node(card_id, f"Card {card_id}", "Card", {"is_primary": True})
        add_edge(case_node_id, card_id, "INVOLVES_CARD")
        if customer_id:
            add_edge(customer_id, card_id, "OWNS")

    # 4. Affected & Flagged Transaction Nodes
    affected_txns = c_obj.get("affected_txn_ids", [])
    if not affected_txns and flagged_txn_id:
        affected_txns = [flagged_txn_id]

    for tid in affected_txns[:10]:
        t_data = tools.get_transaction_detail(tid)
        amt = float(t_data.get("TransactionAmt", 0.0))
        is_flagged = (tid == flagged_txn_id)
        
        t_node_id = f"TXN-{tid}"
        add_node(t_node_id, f"Txn {tid} (${amt:.2f})", "Transaction", {
            "amount": amt,
            "is_flagged": is_flagged,
            "product_cd": t_data.get("ProductCD")
        })
        add_edge(case_node_id, t_node_id, "INVOLVES_TXN")
        if card_id:
            add_edge(card_id, t_node_id, "MADE")

        # Device node link
        dev_info = str(t_data.get("DeviceInfo", "unknown"))
        if dev_info != "unknown":
            dev_node_id = f"DEV-{dev_info}"
            add_node(dev_node_id, dev_info, "Device", {"device_type": t_data.get("DeviceType")})
            add_edge(t_node_id, dev_node_id, "USED_DEVICE")

    # 5. Connected Cards (Ring Nodes)
    connected_cards = c_obj.get("connected_card_ids", [])
    for cc_id in connected_cards[:6]:
        add_node(cc_id, f"Ring Card {cc_id}", "Card", {"is_connected_ring": True})
        add_edge(case_node_id, cc_id, "CONNECTED_RING_CARD")
        if card_id:
            add_edge(card_id, cc_id, "SHARED_DEVICE_RING")

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "verdict": verdict,
            "pattern": c_obj.get("pattern")
        }
    }

# -------------------------------------------------------------
# 5. Policy & Reference Endpoints
# -------------------------------------------------------------
@app.get("/api/policies", tags=["Policy"])
def get_policies():
    """Returns the full Bank Fraud Policy rules (R1-R10) and approval routes."""
    return {
        "policy_version": "1.0",
        "rules": POLICY_RULES,
        "action_types": ACTION_TYPES,
        "approval_routes": APPROVAL_ROUTES
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
