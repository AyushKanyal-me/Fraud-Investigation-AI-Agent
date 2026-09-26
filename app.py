"""
FastAPI Server for TigerGraph Agentic Fraud Investigation System.
Exposes REST endpoints for the Frontend UI dashboard, graph visualizer, and LangGraph live runner.
Utilizes FastAPI Lifespan management and Dependency Injection.
"""

import os
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Query, Body, Header, Depends, Security, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    DATASET_DIR, ANSWERS_DIR, CASES_DIR, POLICY_RULES, ACTION_TYPES,
    APPROVAL_ROUTES, CORS_ALLOWED_ORIGINS, API_AUTH_KEY
)
from agent.tools import GraphTools
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.workflow import FraudInvestigationWorkflow
from agent.policy import POLICY_VERSION
from agent.persistence import InvestigationPersistenceManager, get_persistence_manager
from agent.checkpoints import CheckpointStore, get_checkpoint_store
from agent.validator import validate_case_invariants
from agent.repository.exceptions import TigerGraphUnavailableError

logger = logging.getLogger("fraud_api")

# Known insecure/default keys that must never be accepted in production
_KNOWN_INSECURE_KEYS = {
    "tigergraph-fraud-agent-auth-key",
    "tg-fraud-key-dev-2026",
    "generate-a-long-random-secret-key-for-api-auth",
    "YOUR_SECURE_RANDOM_SECRET_KEY_HERE",
    "YOUR_API_KEY_HERE",
    "change_me",
    "123456",
    "admin",
    "secret"
}

# API Key Authentication Scheme
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    current_key = os.getenv("API_AUTH_KEY") or API_AUTH_KEY
    if not current_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication key is not configured on server."
        )
    if current_key in _KNOWN_INSECURE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API_AUTH_KEY is set to an insecure/placeholder default. Please configure a unique secure key."
        )
    if not api_key or api_key != current_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide valid 'X-API-Key' header."
        )
    return api_key

# -------------------------------------------------------------
# Lifespan Context Manager
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initializes backend resources (vector store, repository tools, workflow, persistence)
    and validates critical environment settings upon startup.
    """
    auth_key = os.getenv("API_AUTH_KEY") or API_AUTH_KEY
    if not auth_key:
        logger.warning("API_AUTH_KEY is not set. All authenticated routes will reject requests.")
    elif auth_key in _KNOWN_INSECURE_KEYS:
        logger.critical("SECURITY ALERT: API_AUTH_KEY is configured with an insecure placeholder default! Authenticated requests will be rejected.")
    elif len(auth_key) < 16:
        logger.warning("API_AUTH_KEY is shorter than 16 characters. Consider using a stronger key in production.")

    # Initialize subsystems on app state
    vector_store = FraudVectorStore()
    memory = CaseMemory()
    tools = GraphTools(vector_store=vector_store)
    workflow = FraudInvestigationWorkflow(tools=tools, memory=memory, vector_store=vector_store)
    persistence = get_persistence_manager()
    checkpoints = get_checkpoint_store()

    app.state.vector_store = vector_store
    app.state.memory = memory
    app.state.tools = tools
    app.state.workflow = workflow
    app.state.persistence = persistence
    app.state.checkpoints = checkpoints

    logger.info("TigerGraph Fraud Investigation API initialized successfully.")
    yield

    logger.info("Shutting down TigerGraph Fraud Investigation API.")

# Initialize FastAPI App with Lifespan
app = FastAPI(
    title="TigerGraph Agentic Fraud Investigation API",
    description="Backend API powering the Agentic Fraud Investigation UI, Graph Visualizer, and Policy Engine.",
    version="2.0.0",
    lifespan=lifespan
)

@app.exception_handler(TigerGraphUnavailableError)
async def tigergraph_unavailable_handler(request: Request, exc: TigerGraphUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "TigerGraphUnavailableError",
            "detail": str(exc),
            "fallback_policy": "fail_closed"
        }
    )

# Enable Restricted CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Dependency Injections
# -------------------------------------------------------------
def get_vector_store(request: Request) -> FraudVectorStore:
    return getattr(request.app.state, "vector_store", None) or FraudVectorStore()

def get_memory(request: Request) -> CaseMemory:
    return getattr(request.app.state, "memory", None) or CaseMemory()

def get_tools(request: Request) -> GraphTools:
    return getattr(request.app.state, "tools", None) or GraphTools(vector_store=get_vector_store(request))

def get_workflow(request: Request) -> FraudInvestigationWorkflow:
    if hasattr(request.app.state, "workflow") and request.app.state.workflow is not None:
        return request.app.state.workflow
    vs = get_vector_store(request)
    mem = get_memory(request)
    tls = get_tools(request)
    return FraudInvestigationWorkflow(tools=tls, memory=mem, vector_store=vs)

def get_persistence(request: Request) -> InvestigationPersistenceManager:
    return getattr(request.app.state, "persistence", None) or get_persistence_manager()

def get_checkpoints(request: Request) -> CheckpointStore:
    return getattr(request.app.state, "checkpoints", None) or get_checkpoint_store()

# -------------------------------------------------------------
# Pydantic Request Schemas
# -------------------------------------------------------------
class CustomInvestigateRequest(BaseModel):
    case_id: str = Field(..., description="Unique case identifier, e.g. HHG-001")
    opened_at: Optional[str] = Field("2016-12-30 12:00:00", description="Alert opening timestamp")
    trigger_type: str = Field("risk_score", description="risk_score | customer_report | analyst_request")
    trigger_text: Optional[str] = Field("Real-time model risk threshold exceeded", description="Trigger context")
    flagged_txn_id: str = Field(..., description="Primary transaction ID triggering alert")
    card_id: Optional[str] = Field("", description="Card ID")
    customer_id: Optional[str] = Field("", description="Customer ID")
    risk_score: Optional[float] = Field(0.85, description="Initial risk score")

class EvidenceSubmissionRequest(BaseModel):
    request_id: str = Field(..., description="Unique evidence request ID")
    response_text: str = Field(..., description="Response provided by customer or analyst")
    source: str = Field("customer_portal", description="Source of evidence: customer_portal | analyst | external")
    actor_id: Optional[str] = Field("customer", description="Actor providing evidence")

# -------------------------------------------------------------
# 1. Health, Diagnostic & System Metrics (Read-Only)
# -------------------------------------------------------------
@app.get("/healthz", tags=["System"])
def get_liveness():
    """
    Lightweight liveness probe for load balancers and orchestrators.
    Guaranteed O(1) response without triggering dataset load or graph queries.
    """
    return {
        "status": "healthy",
        "agent_engine": "LangGraph StateGraph 2.0",
        "policy_version": POLICY_VERSION
    }

@app.get("/api/health", tags=["System"])
def get_readiness(
    vs: FraudVectorStore = Depends(get_vector_store),
    mem: CaseMemory = Depends(get_memory),
    tls: GraphTools = Depends(get_tools)
):
    """Returns detailed server and subsystem readiness status without forcing full CSV dataset load."""
    return {
        "status": "healthy",
        "agent_engine": "LangGraph StateGraph 2.0",
        "policy_version": POLICY_VERSION,
        "vector_store_docs": vs.collection.count() if vs.collection else len(vs.documents),
        "memory_cases_count": len(mem.cases),
        "tigergraph_connected": tls.conn is not None,
        "data_loaded": tls.is_data_loaded,
        "dataset_transactions_loaded": tls.loaded_txn_count
    }


@app.get("/api/repository/health", tags=["System"])
def get_repository_health(tls: GraphTools = Depends(get_tools)):
    """Returns detailed diagnostics on the active data repository and fallback history."""
    if hasattr(tls, "repo") and hasattr(tls.repo, "get_health_status"):
        return tls.repo.get_health_status()
    return {"backend": "local", "is_connected": True}

@app.get("/metrics", tags=["Dashboard"])
@app.get("/api/stats", tags=["Dashboard"])
def get_dashboard_stats():
    """Aggregates high-level statistics across all investigated cases."""
    answers = []
    if ANSWERS_DIR.exists():
        for p in ANSWERS_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
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
# 2. Case Listing & Detail (Read-Only GET Endpoints)
# -------------------------------------------------------------
@app.get("/api/cases", tags=["Cases"])
def list_cases(
    status: Optional[str] = Query(None, description="Filter by status: fraud, legitimate, uncertain"),
    persistence: InvestigationPersistenceManager = Depends(get_persistence)
):
    """Returns the list of all cases in the case pack with their investigated summaries."""
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    df_cases = pd.read_csv(case_pack_file)
    case_list = []

    for _, row in df_cases.iterrows():
        cid = str(row["case_id"])
        cdata = persistence.get_case_state(cid)
        if not cdata:
            ans_file = ANSWERS_DIR / f"{cid}.json"
            if ans_file.exists():
                try:
                    with open(ans_file, "r", encoding="utf-8") as f:
                        cdata = json.load(f)
                except Exception:
                    cdata = None

        investigated = False
        verdict = "uninvestigated"
        prob = None
        pattern = "unknown"
        exposure = 0.0
        sar_file = False
        summary = ""

        if cdata:
            c_obj = cdata.get("case", {})
            investigated = True
            verdict = c_obj.get("verdict", "uncertain")
            prob = c_obj.get("fraud_probability")
            pattern = c_obj.get("pattern", "none")
            exposure = c_obj.get("exposure_usd", 0.0)
            summary = c_obj.get("summary", "")
            sar_file = cdata.get("sar", {}).get("file", False)

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

@app.get("/cases/{case_id}", tags=["Cases"])
@app.get("/api/cases/{case_id}", tags=["Cases"])
def get_case_detail(case_id: str, persistence: InvestigationPersistenceManager = Depends(get_persistence)):
    """Returns the full investigation JSON payload for a given case_id."""
    cdata = persistence.get_case_state(case_id)
    if cdata:
        return cdata

    ans_file = ANSWERS_DIR / f"{case_id}.json"
    if ans_file.exists():
        with open(ans_file, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

@app.get("/cases/{case_id}/audit-log", tags=["Cases"])
@app.get("/api/cases/{case_id}/audit-log", tags=["Cases"])
def get_case_audit_log(case_id: str, persistence: InvestigationPersistenceManager = Depends(get_persistence)):
    """Returns the structured, tamper-evident audit trail for a given case."""
    trail = persistence.get_audit_trail(case_id)
    return {
        "case_id": case_id,
        "event_count": len(trail),
        "audit_events": trail
    }

@app.get("/cases/{case_id}/audit/verify", tags=["Cases"])
@app.get("/api/cases/{case_id}/audit/verify", tags=["Cases"])
def verify_case_audit_chain(case_id: str, persistence: InvestigationPersistenceManager = Depends(get_persistence)):
    """Cryptographically verifies the SHA-256 hash-chain integrity of the case's audit trail."""
    is_valid, errors = persistence.verify_audit_integrity(case_id)
    return {
        "case_id": case_id,
        "chain_intact": is_valid,
        "verification_errors": errors
    }

@app.get("/cases/{case_id}/evidence", tags=["Cases"])
@app.get("/api/cases/{case_id}/evidence", tags=["Cases"])
def get_case_evidence(case_id: str, persistence: InvestigationPersistenceManager = Depends(get_persistence)):
    """Returns all evidence items retrieved and cited for a given case."""
    cdata = persistence.get_case_state(case_id)
    if not cdata:
        ans_file = ANSWERS_DIR / f"{case_id}.json"
        if ans_file.exists():
            with open(ans_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
    if not cdata:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    
    evidence_items = cdata.get("case", {}).get("evidence", [])
    evidence_requests = cdata.get("evidence_requests", [])
    return {
        "case_id": case_id,
        "evidence": evidence_items,
        "evidence_requests": evidence_requests
    }

@app.get("/cases/{case_id}/checkpoints", tags=["Cases"])
@app.get("/api/cases/{case_id}/checkpoints", tags=["Cases"])
def get_case_checkpoint(case_id: str, checkpoints: CheckpointStore = Depends(get_checkpoints)):
    """Returns the active checkpoint for an investigation awaiting evidence."""
    cp = checkpoints.get_checkpoint(case_id)
    if not cp:
        return {"case_id": case_id, "status": "no_pending_checkpoint", "checkpoint": None}
    return {"case_id": case_id, "status": "awaiting_evidence", "checkpoint": cp}

# -------------------------------------------------------------
# 3. Investigation Endpoints (Secured by API Key)
# -------------------------------------------------------------
@app.post("/api/cases/{case_id}/investigate", tags=["Investigation"])
def trigger_investigation(
    case_id: str,
    auth: str = Depends(verify_api_key),
    wf: FraudInvestigationWorkflow = Depends(get_workflow),
    persistence: InvestigationPersistenceManager = Depends(get_persistence)
):
    """Triggers live LangGraph investigation for a case and atomically updates persistence."""
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    df_cases = pd.read_csv(case_pack_file)
    matches = df_cases[df_cases["case_id"] == case_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")

    case_row = matches.iloc[0].to_dict()
    result = wf.run_investigation(case_row)

    # Validate output
    is_valid, errors, _ = validate_case_invariants(result, case_id_expected=case_id)
    if not is_valid:
        raise HTTPException(status_code=500, detail=f"Investigation output failed validation: {errors}")

    # Atomic Persistence
    persistence.persist_case_state(case_id, result, actor="api_user")
    persistence.persist_answer_artifact(case_id, result)

    return result

@app.post("/api/investigate/custom", tags=["Investigation"])
def investigate_custom_transaction(
    req: CustomInvestigateRequest,
    auth: str = Depends(verify_api_key),
    wf: FraudInvestigationWorkflow = Depends(get_workflow),
    persistence: InvestigationPersistenceManager = Depends(get_persistence)
):
    """Investigates an arbitrary transaction or alert payload using the full LangGraph pipeline."""
    case_dict = req.dict()
    result = wf.run_investigation(case_dict)
    
    cid = req.case_id
    persistence.persist_case_state(cid, result, actor="custom_api_user")
    persistence.persist_answer_artifact(cid, result)
    return result

@app.post("/cases/{case_id}/evidence/submit", tags=["Evidence Workflow"])
@app.post("/api/cases/{case_id}/evidence/submit", tags=["Evidence Workflow"])
def submit_external_evidence(
    case_id: str,
    req: EvidenceSubmissionRequest,
    auth: str = Depends(verify_api_key),
    wf: FraudInvestigationWorkflow = Depends(get_workflow),
    persistence: InvestigationPersistenceManager = Depends(get_persistence),
    checkpoints: CheckpointStore = Depends(get_checkpoints)
):
    """
    Submits real customer / analyst evidence for a case awaiting evidence and resumes workflow to final disposition.
    """
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    df_cases = pd.read_csv(case_pack_file)
    matches = df_cases[df_cases["case_id"] == case_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")

    case_row = matches.iloc[0].to_dict()
    
    # Retrieve checkpoint state if available
    checkpoint_record = checkpoints.get_checkpoint(case_id, request_id=req.request_id)
    if not checkpoint_record:
        checkpoint_record = checkpoints.get_checkpoint(case_id)
    
    resume_state = checkpoint_record.get("state") if checkpoint_record else None

    # Resume workflow with submitted evidence and checkpoint state
    result = wf.run_investigation(case_row, submitted_evidence=req.model_dump(), resume_state=resume_state)

    # Validate output
    is_valid, errors, _ = validate_case_invariants(result, case_id_expected=case_id)
    if not is_valid:
        raise HTTPException(status_code=500, detail=f"Resumed investigation output failed validation: {errors}")

    # Atomic Persistence
    persistence.persist_case_state(case_id, result, actor=f"evidence_submitter_{req.actor_id}")
    persistence.persist_answer_artifact(case_id, result)

    # Clean up checkpoint
    checkpoints.delete_checkpoint(case_id, request_id=req.request_id)

    # Log audit event
    persistence.audit_logger.log_event(
        case_id=case_id,
        event_type="EXTERNAL_EVIDENCE_RESUMED",
        actor=req.actor_id,
        details={
            "request_id": req.request_id,
            "source": req.source,
            "final_verdict": result.get("case", {}).get("verdict"),
            "final_status": result.get("case", {}).get("status")
        }
    )

    return result

# -------------------------------------------------------------
# 4. Interactive Graph Visualizer Subgraph (Cytoscape / D3 format)
# -------------------------------------------------------------
@app.get("/api/graph/{case_id}", tags=["Graph Visualizer"])
def get_case_subgraph(
    case_id: str,
    persistence: InvestigationPersistenceManager = Depends(get_persistence),
    tls: GraphTools = Depends(get_tools)
):
    """
    Returns node-link graph data (nodes & edges) for interactive rendering in the frontend.
    Compatible with Cytoscape.js, Vis.js, D3.js, and ECharts.
    """
    cdata = persistence.get_case_state(case_id)
    if not cdata:
        ans_file = ANSWERS_DIR / f"{case_id}.json"
        if ans_file.exists():
            with open(ans_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
    if not cdata:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    c_obj = cdata.get("case", {})
    verdict = c_obj.get("verdict", "uncertain")
    flagged_txn_id = ""
    
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

    txn_meta = tls.get_transaction_detail(flagged_txn_id) if flagged_txn_id else {}
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
        t_data = tls.get_transaction_detail(tid)
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
        "policy_version": POLICY_VERSION,
        "rules": POLICY_RULES,
        "action_types": ACTION_TYPES,
        "approval_routes": APPROVAL_ROUTES
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
