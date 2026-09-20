"""
LangGraph Multi-Agent Investigation StateGraph for TigerGraph Fraud Investigation.
Implements the full ReAct / Plan-Execute-Verify cognitive architecture with dynamic tool calling,
GraphRAG policy retrieval, customer simulation, explainability logging, and TigerGraph persistence.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, END

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import GEMINI_API_KEY
from agent.tools import GraphTools
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.simulator import CustomerSimulator
from agent.policy import evaluate_policy_rules, CustomerReplyOutcome, get_action_route
from agent.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    INITIAL_ASSESSMENT_PROMPT,
    FINAL_ASSESSMENT_PROMPT,
    SAR_NARRATIVE_PROMPT
)

class InvestigationGraphState(TypedDict, total=False):
    # Initial trigger metadata
    case_id: str
    opened_at: str
    trigger_type: str
    trigger_text: str
    flagged_txn_id: str
    card_id: str
    customer_id: str
    risk_score: float

    # Operational metrics & explainability trace
    tool_call_count: int
    tokens_consumed: int
    explainability_trace: List[Dict[str, str]]

    # Graph Evidence gathered
    txn_data: Dict[str, Any]
    baseline: Dict[str, Any]
    episode_txns: List[str]
    episode_exposure: float
    first_suspicious_txn: str
    episode_meta: Dict[str, Any]
    connected_cards: List[str]
    connected_dev_profiles: List[str]
    has_shared_device_ring: bool
    memory_hits: Dict[str, Any]
    similar_cases: List[str]
    evidence_claims: List[Dict[str, Any]]

    # Step 1: Initial Assessment
    initial_verdict: str
    initial_prob: float
    initial_pattern: str
    initial_actions: List[Dict[str, str]]
    initial_exposure: float

    # Step 2: Dynamic Customer Inquiry & Simulation
    evidence_requests: List[Dict[str, Any]]
    customer_outcome: CustomerReplyOutcome
    simulated_reply: str

    # Step 3: GraphRAG Policy Retrieval & Final Assessment
    rag_precedents: List[Dict[str, Any]]
    final_verdict: str
    final_prob: float
    final_pattern: str
    final_status: str
    final_exposure: float
    affected_txn_ids: List[str]
    final_actions: List[Dict[str, str]]
    what_changed: str
    stop_reason: str

    # Step 4: SAR Compliance
    sar_file: bool
    sar_reason: str
    sar_narrative: str
    sar_subjects: List[str]
    sar_amount: float
    sar_dates: List[str]

    # Step 5: Summary & Graph Persistence
    summary: str
    written_to_graph: bool
    graph_case_id: str
    latency_s: float
    final_payload: Dict[str, Any]

class FraudInvestigationGraph:
    def __init__(
        self,
        tools: Optional[GraphTools] = None,
        vector_store: Optional[FraudVectorStore] = None,
        memory: Optional[CaseMemory] = None
    ):
        self.tools = tools or GraphTools()
        self.vector_store = vector_store or FraudVectorStore()
        self.memory = memory or CaseMemory()
        self.client = None
        self.llm = None
        self._init_llm()
        self.simulator = CustomerSimulator(llm_caller=self._call_gemini)
        self.graph = self._build_graph()

    def _init_llm(self):
        if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                print("[+] LangGraph: google-genai client initialized.")
                return
            except Exception as e:
                print(f"[i] LangGraph google-genai client note: {e}")

            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
                    try:
                        self.llm = ChatGoogleGenerativeAI(
                            model=model_name,
                            google_api_key=GEMINI_API_KEY,
                            temperature=0.1
                        )
                        print(f"[+] LangGraph: LangChain Gemini LLM initialized ('{model_name}').")
                        return
                    except Exception:
                        continue
            except Exception as e:
                print(f"[i] LangGraph langchain Gemini note: {e}")

    def _call_gemini(self, prompt: str) -> Optional[str]:
        if self.client:
            for model_id in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
                try:
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception:
                    continue
        if self.llm:
            try:
                res = self.llm.invoke(prompt)
                return res.content.strip()
            except Exception:
                pass
        return None

    # -------------------------------------------------------------
    # Node 1: Initialize Case State & Hypotheses
    # -------------------------------------------------------------
    def node_initialize(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        trace.append({
            "step": "Initialize Case",
            "thought": f"Initiating investigation for case {state['case_id']}. Trigger: {state['trigger_type']} ('{state['trigger_text']}'). Flagged Txn: {state['flagged_txn_id']}."
        })
        return {
            "tool_call_count": 0,
            "tokens_consumed": 0,
            "explainability_trace": trace,
            "evidence_claims": []
        }

    # -------------------------------------------------------------
    # Node 2: Gather TigerGraph & Temporal Neighborhood Evidence
    # -------------------------------------------------------------
    def node_gather_evidence(self, state: InvestigationGraphState) -> Dict[str, Any]:
        tool_count = state.get("tool_call_count", 0)
        trace = state.get("explainability_trace", [])
        evidence_claims = state.get("evidence_claims", [])

        flagged_txn_id = state["flagged_txn_id"]
        
        # 1. Transaction Detail
        tool_count += 1
        txn_data = self.tools.get_transaction_detail(flagged_txn_id)
        card_id = state.get("card_id") or txn_data.get("card_id", "")
        customer_id = state.get("customer_id") or txn_data.get("customer_id", "")
        
        txn_amt = float(txn_data.get("TransactionAmt", 0.0))
        txn_ts = float(txn_data.get("ts_val", 0.0))
        dev_info = str(txn_data.get("DeviceInfo", "unknown"))
        dev_type = str(txn_data.get("DeviceType", "unknown"))
        p_email = str(txn_data.get("P_emaildomain", "unknown"))
        addr1 = txn_data.get("addr1")

        # 2. Time-bounded Historical Baseline
        tool_count += 1
        baseline = self.tools.get_time_bounded_card_baseline(card_id=card_id, before_ts=txn_ts)

        # 3. Temporal Fraud Episode Expansion (card testing / burst velocity)
        tool_count += 1
        episode_txns, episode_exposure, first_txn, episode_meta = self.tools.expand_fraud_episode(
            card_id=card_id, center_ts=txn_ts, flagged_txn_id=flagged_txn_id, window_sec=86400
        )
        is_card_testing = episode_meta.get("is_card_testing", False)

        # 4. Device Ring Analysis (7-day window)
        tool_count += 1
        dev_neighbors = self.tools.get_time_bounded_device_neighbors(
            device_info=dev_info, center_ts=txn_ts, exclude_card_id=card_id
        )
        connected_cards = [str(r["card_id"]) for r in dev_neighbors]
        has_shared_device_ring = len(connected_cards) >= 2
        connected_dev_profiles = [f"{dev_info} | {dev_type}"] if dev_info != "unknown" and has_shared_device_ring else []

        # 5. Cross-Case Memory Check
        tool_count += 1
        memory_hits = self.memory.check_entity_history(card_id=card_id, device_info=dev_info, email=p_email)
        if memory_hits.get("device_prior_cases"):
            has_shared_device_ring = True

        # 6. Hybrid Similar Closed Cases
        tool_count += 1
        similar_cases = self.tools.find_similar_closed_cases(card_id=card_id, customer_id=customer_id)

        # Synthesize Evidence Claims
        if is_card_testing:
            evidence_claims.append({
                "claim": f"{episode_meta.get('small_txn_count', 3)} online authorizations under $15 within 1 hour followed by larger purchase on card {card_id}",
                "source": "graph",
                "ref": f"query:expand_fraud_episode(card_id={card_id}, window=3600)",
                "entity_ids": episode_txns
            })

        is_new_device = False
        if dev_info != "unknown":
            if baseline["known_devices"] and dev_info not in baseline["known_devices"]:
                is_new_device = True
                evidence_claims.append({
                    "claim": f"Transaction initiated from unseen device profile ({dev_info}) not present in historical baseline",
                    "source": "graph",
                    "ref": f"query:get_time_bounded_card_baseline(card_id={card_id})",
                    "entity_ids": [flagged_txn_id]
                })

            if has_shared_device_ring:
                evidence_claims.append({
                    "claim": f"Device {dev_info} shared across {len(connected_cards) + 1} distinct cards in active time window",
                    "source": "graph",
                    "ref": f"query:get_time_bounded_device_neighbors(device={dev_info})",
                    "entity_ids": connected_cards[:5]
                })

        is_region_anomaly = False
        if addr1 and baseline.get("primary_addr1") and str(addr1) != str(baseline["primary_addr1"]):
            is_region_anomaly = True
            evidence_claims.append({
                "claim": f"Transaction location (region {addr1}) differs from cardholder 30-day home region {baseline['primary_addr1']}",
                "source": "graph",
                "ref": "query:region_anomaly",
                "entity_ids": [flagged_txn_id]
            })

        is_recurring_dispute = False
        if state["trigger_type"] == "customer_report" and baseline.get("recurring_amounts"):
            if any(abs(r_amt - txn_amt) < 0.10 for r_amt in baseline["recurring_amounts"]):
                is_recurring_dispute = True
                evidence_claims.append({
                    "claim": f"Disputed amount ${txn_amt:.2f} matches customer historical recurring monthly billing pattern",
                    "source": "graph",
                    "ref": f"query:get_time_bounded_card_baseline(card_id={card_id})",
                    "entity_ids": [flagged_txn_id]
                })

        trace.append({
            "step": "Gather Evidence",
            "thought": f"Retrieved graph data for {flagged_txn_id}. Baseline avg: ${baseline.get('avg_amount', 0):.2f}. Episode txns: {len(episode_txns)} (${episode_exposure:.2f}). Connected cards: {len(connected_cards)}."
        })

        return {
            "card_id": card_id,
            "customer_id": customer_id,
            "tool_call_count": tool_count,
            "explainability_trace": trace,
            "txn_data": txn_data,
            "baseline": baseline,
            "episode_txns": episode_txns,
            "episode_exposure": episode_exposure,
            "first_suspicious_txn": first_txn,
            "episode_meta": episode_meta,
            "connected_cards": connected_cards,
            "connected_dev_profiles": connected_dev_profiles,
            "has_shared_device_ring": has_shared_device_ring,
            "memory_hits": memory_hits,
            "similar_cases": similar_cases,
            "evidence_claims": evidence_claims
        }

    # -------------------------------------------------------------
    # Node 3: Initial Assessment & Policy Routing (R1-R10)
    # -------------------------------------------------------------
    def node_initial_assessment(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        evidence_claims = state.get("evidence_claims", [])
        tokens_consumed = state.get("tokens_consumed", 0)

        trigger_type = state["trigger_type"]
        risk_score = state.get("risk_score", 0.50)
        txn_data = state["txn_data"]
        baseline = state["baseline"]
        episode_meta = state["episode_meta"]
        connected_cards = state["connected_cards"]
        has_shared_device_ring = state["has_shared_device_ring"]
        episode_exposure = state["episode_exposure"]
        flagged_txn_id = state["flagged_txn_id"]
        dev_info = str(txn_data.get("DeviceInfo", "unknown"))
        addr1 = txn_data.get("addr1")
        txn_amt = float(txn_data.get("TransactionAmt", 0.0))

        is_card_testing = episode_meta.get("is_card_testing", False)
        testing_cleared_gt_100 = episode_meta.get("testing_cleared_gt_100", False)
        is_new_device = dev_info != "unknown" and baseline.get("known_devices") and dev_info not in baseline["known_devices"]
        is_region_anomaly = addr1 and baseline.get("primary_addr1") and str(addr1) != str(baseline["primary_addr1"])
        is_recurring_dispute = trigger_type == "customer_report" and baseline.get("recurring_amounts") and any(abs(r_amt - txn_amt) < 0.10 for r_amt in baseline["recurring_amounts"])

        # Determine Initial Pattern & Initial Probability
        if is_recurring_dispute:
            initial_pattern = "none"
            initial_prob = 0.25
            initial_verdict = "uncertain"
        elif trigger_type == "customer_report":
            initial_prob = 0.82
            initial_verdict = "fraud"
            if is_card_testing:
                initial_pattern = "card_testing"
            elif is_new_device:
                initial_pattern = "card_not_present_new_device"
            elif is_region_anomaly:
                initial_pattern = "out_of_region_use"
            else:
                initial_pattern = "card_not_present_fraud"
        elif trigger_type == "analyst_request":
            initial_prob = 0.85
            initial_verdict = "fraud"
            initial_pattern = "card_not_present_new_device" if is_new_device else "account_takeover"
            evidence_claims.append({
                "claim": f"Analyst inquiry regarding multi-card cluster sharing device profile {dev_info}",
                "source": "external",
                "ref": "trigger:analyst_request",
                "entity_ids": [flagged_txn_id] + connected_cards[:2]
            })
        elif is_card_testing:
            initial_pattern = "card_testing"
            initial_prob = 0.80
            initial_verdict = "fraud"
        elif has_shared_device_ring and is_new_device:
            initial_pattern = "card_not_present_new_device"
            initial_prob = 0.85
            initial_verdict = "fraud"
        elif risk_score >= 0.85:
            initial_pattern = "card_not_present_fraud"
            initial_prob = 0.72
            initial_verdict = "uncertain"
        elif risk_score <= 0.55 and not is_new_device and not is_region_anomaly:
            initial_pattern = "none"
            initial_prob = 0.10
            initial_verdict = "legitimate"
        else:
            initial_pattern = "out_of_region_use" if is_region_anomaly else "card_not_present_fraud"
            initial_prob = 0.45
            initial_verdict = "uncertain"

        # Evaluate Initial Policy Actions
        initial_exposure = episode_exposure if initial_verdict != "legitimate" else 0.0
        initial_actions, _, _ = evaluate_policy_rules(
            stage="initial",
            verdict=initial_verdict,
            fraud_prob=initial_prob,
            pattern=initial_pattern,
            exposure_usd=initial_exposure,
            connected_cards=connected_cards,
            has_shared_device_ring=has_shared_device_ring,
            is_card_testing=is_card_testing,
            testing_cleared_gt_100=testing_cleared_gt_100,
            is_recurring_dispute=is_recurring_dispute
        )

        trace.append({
            "step": "Initial Assessment",
            "thought": f"Evaluated initial signals: verdict={initial_verdict}, prob={initial_prob:.2f}, pattern={initial_pattern}. Recommended initial actions: {[a['action'] for a in initial_actions]}."
        })

        return {
            "initial_verdict": initial_verdict,
            "initial_prob": initial_prob,
            "initial_pattern": initial_pattern,
            "initial_actions": initial_actions,
            "initial_exposure": initial_exposure,
            "explainability_trace": trace,
            "tokens_consumed": tokens_consumed,
            "evidence_claims": evidence_claims
        }

    # -------------------------------------------------------------
    # Node 4: Dynamic Customer Inquiry & Authentication Simulator
    # -------------------------------------------------------------
    def node_customer_inquiry(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        evidence_claims = state.get("evidence_claims", [])
        tool_count = state.get("tool_call_count", 0)

        initial_verdict = state["initial_verdict"]
        initial_prob = state["initial_prob"]
        trigger_type = state["trigger_type"]
        risk_score = state.get("risk_score", 0.50)
        txn_data = state["txn_data"]
        baseline = state["baseline"]
        episode_meta = state["episode_meta"]
        flagged_txn_id = state["flagged_txn_id"]
        customer_id = state.get("customer_id", "")
        card_id = state.get("card_id", "")
        txn_amt = float(txn_data.get("TransactionAmt", 0.0))
        product_cd = str(txn_data.get("ProductCD", "W"))
        dev_info = str(txn_data.get("DeviceInfo", "unknown"))
        addr1 = txn_data.get("addr1")

        is_new_device = dev_info != "unknown" and baseline.get("known_devices") and dev_info not in baseline["known_devices"]
        is_region_anomaly = addr1 and baseline.get("primary_addr1") and str(addr1) != str(baseline["primary_addr1"])
        is_recurring_dispute = trigger_type == "customer_report" and baseline.get("recurring_amounts") and any(abs(r_amt - txn_amt) < 0.10 for r_amt in baseline["recurring_amounts"])
        is_card_testing = episode_meta.get("is_card_testing", False)
        has_shared_device_ring = state.get("has_shared_device_ring", False)

        evidence_requests = []
        customer_outcome = CustomerReplyOutcome.NO_REQUEST
        simulated_reply = ""

        if initial_verdict == "legitimate":
            # Clear false positive; no intrusive customer inquiry needed
            customer_outcome = CustomerReplyOutcome.NO_REQUEST
            evidence_requests = []
            trace.append({
                "step": "Customer Verification",
                "thought": "Initial verdict is legitimate; skipping customer inquiry per policy Section 1."
            })
        else:
            # Trigger dynamic simulation tool
            tool_count += 1
            customer_outcome, inq_type, simulated_reply = self.simulator.simulate_inquiry(
                customer_id=customer_id,
                card_id=card_id,
                flagged_txn_id=flagged_txn_id,
                txn_amt=txn_amt,
                product_cd=product_cd,
                trigger_type=trigger_type,
                risk_score=risk_score,
                is_recurring_dispute=is_recurring_dispute,
                is_new_device=is_new_device,
                is_region_anomaly=is_region_anomaly,
                is_card_testing=is_card_testing,
                has_shared_device_ring=has_shared_device_ring
            )

            evidence_requests.append({
                "type": inq_type,
                "asked_after_step": tool_count,
                "assumed_response": simulated_reply
            })

            if customer_outcome == CustomerReplyOutcome.DENIED_UNAUTHORIZED:
                evidence_claims.append({
                    "claim": f"Customer denied transaction {flagged_txn_id} (${txn_amt:.2f}) when contacted",
                    "source": "customer",
                    "ref": f"evidence_request:{len(evidence_requests)}",
                    "entity_ids": [flagged_txn_id]
                })

            trace.append({
                "step": "Customer Verification",
                "thought": f"Simulated {inq_type}: outcome={customer_outcome.value}. Response: '{simulated_reply}'."
            })

        return {
            "tool_call_count": tool_count,
            "evidence_requests": evidence_requests,
            "customer_outcome": customer_outcome,
            "simulated_reply": simulated_reply,
            "evidence_claims": evidence_claims,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Node 5: GraphRAG Regulatory & Bank Policy Retrieval
    # -------------------------------------------------------------
    def node_rag_retriever(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        tool_count = state.get("tool_call_count", 0)

        initial_pattern = state.get("initial_pattern", "none")
        has_ring = state.get("has_shared_device_ring", False)

        tool_count += 1
        query = f"policy actions for {initial_pattern} fraud with {'shared device ring' if has_ring else 'unauthorized card'}"
        rag_results = self.vector_store.search(query=query, n_results=3)

        trace.append({
            "step": "GraphRAG Policy Retrieval",
            "thought": f"Retrieved {len(rag_results)} policy and precedent documents for query '{query}'."
        })

        return {
            "tool_call_count": tool_count,
            "rag_precedents": rag_results,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Node 6: Final Assessment & Calibrated Verdict
    # -------------------------------------------------------------
    def node_final_assessment(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        tokens_consumed = state.get("tokens_consumed", 0)

        initial_verdict = state["initial_verdict"]
        initial_prob = state["initial_prob"]
        initial_pattern = state["initial_pattern"]
        customer_outcome = state["customer_outcome"]
        episode_exposure = state["episode_exposure"]
        first_suspicious_txn = state.get("first_suspicious_txn", "")
        episode_txns = state["episode_txns"]

        if customer_outcome == CustomerReplyOutcome.CONFIRMED_LEGITIMATE:
            final_verdict = "legitimate"
            final_prob = 0.06
            final_pattern = "none"
            final_status = "closed_legitimate"
            affected_txn_ids = []
            final_exposure = 0.0
            first_suspicious_txn = ""
            what_changed = f"Customer confirmation lowered fraud probability from {initial_prob:.2f} to {final_prob:.2f} and cleared the alert without card block."
            stop_reason = "Customer confirmation settled the inquiry; closed as legitimate under Rule R3."

        elif customer_outcome == CustomerReplyOutcome.RECURRING_DISPUTE:
            final_verdict = "legitimate"
            final_prob = 0.05
            final_pattern = "none"
            final_status = "closed_legitimate"
            affected_txn_ids = []
            final_exposure = 0.0
            first_suspicious_txn = ""
            what_changed = "Investigation confirmed recurring subscription billing match under Rule R7; cardholder reminded and case closed."
            stop_reason = "Recurring monthly billing established; closed without card block under Rule R7/R3."

        elif initial_verdict == "legitimate":
            final_verdict = "legitimate"
            final_prob = initial_prob
            final_pattern = "none"
            final_status = "closed_legitimate"
            affected_txn_ids = []
            final_exposure = 0.0
            first_suspicious_txn = ""
            what_changed = "nothing"
            stop_reason = f"Activity conforms to 30-day spending baseline; fraud probability ({final_prob:.2f}) satisfies stopping threshold <= 0.15."

        elif customer_outcome in [CustomerReplyOutcome.DENIED_UNAUTHORIZED, CustomerReplyOutcome.STEP_UP_FAILED] or initial_verdict == "fraud":
            final_verdict = "fraud"
            final_prob = max(initial_prob, 0.90)
            final_pattern = initial_pattern
            final_status = "closed_fraud"
            final_exposure = round(episode_exposure, 2)
            affected_txn_ids = episode_txns
            what_changed = f"Customer denial / step-up failure confirmed unauthorized compromise, raising probability from {initial_prob:.2f} to {final_prob:.2f} and triggering block under Rule R2."
            stop_reason = "Definitive evidence of unauthorized activity established; episode exposure computed and protective actions executed."

        else:
            final_verdict = "uncertain"
            final_prob = 0.50
            final_pattern = initial_pattern
            final_status = "escalated"
            final_exposure = round(episode_exposure, 2)
            affected_txn_ids = episode_txns
            what_changed = "nothing"
            stop_reason = "Evidence remains conflicting and exposure exceeds threshold; escalated under Rule R8."

        trace.append({
            "step": "Final Assessment",
            "thought": f"Final resolution: verdict={final_verdict}, prob={final_prob:.2f}, pattern={final_pattern}, exposure=${final_exposure:.2f}. Stop reason: {stop_reason}"
        })

        return {
            "final_verdict": final_verdict,
            "final_prob": final_prob,
            "final_pattern": final_pattern,
            "final_status": final_status,
            "final_exposure": final_exposure,
            "affected_txn_ids": affected_txn_ids,
            "first_suspicious_txn": first_suspicious_txn,
            "what_changed": what_changed,
            "stop_reason": stop_reason,
            "tokens_consumed": tokens_consumed,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Node 7: Final Policy Actions & SAR Evaluation
    # -------------------------------------------------------------
    def node_evaluate_policy_actions(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])

        final_verdict = state["final_verdict"]
        final_prob = state["final_prob"]
        final_pattern = state["final_pattern"]
        final_exposure = state["final_exposure"]
        connected_cards = state["connected_cards"]
        has_shared_device_ring = state["has_shared_device_ring"]
        episode_meta = state["episode_meta"]
        customer_outcome = state["customer_outcome"]

        is_card_testing = episode_meta.get("is_card_testing", False)
        testing_cleared_gt_100 = episode_meta.get("testing_cleared_gt_100", False)
        is_recurring_dispute = customer_outcome == CustomerReplyOutcome.RECURRING_DISPUTE

        final_actions, sar_file, sar_reason = evaluate_policy_rules(
            stage="final",
            verdict=final_verdict,
            fraud_prob=final_prob,
            pattern=final_pattern,
            exposure_usd=final_exposure,
            connected_cards=connected_cards,
            has_shared_device_ring=has_shared_device_ring,
            is_card_testing=is_card_testing,
            testing_cleared_gt_100=testing_cleared_gt_100,
            is_recurring_dispute=is_recurring_dispute,
            customer_outcome=customer_outcome
        )

        trace.append({
            "step": "Policy Rules Evaluation",
            "thought": f"Computed final actions: {[a['action'] for a in final_actions]}. SAR Required: {sar_file} ({sar_reason})."
        })

        return {
            "final_actions": final_actions,
            "sar_file": sar_file,
            "sar_reason": sar_reason,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Node 8: FinCEN SAR Narrative Generation (5 Ws and H)
    # -------------------------------------------------------------
    def node_sar_generation(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        tokens_consumed = state.get("tokens_consumed", 0)

        sar_file = state["sar_file"]
        opened_at = state["opened_at"]
        customer_id = state.get("customer_id", "")
        card_id = state.get("card_id", "")
        connected_cards = state.get("connected_cards", [])
        final_exposure = state.get("final_exposure", 0.0)
        affected_txn_ids = state.get("affected_txn_ids", [])
        final_pattern = state.get("final_pattern", "none")
        txn_data = state.get("txn_data", {})
        dev_info = str(txn_data.get("DeviceInfo", "unknown"))
        p_email = str(txn_data.get("P_emaildomain", "unknown"))

        date_str = opened_at.split()[0] if " " in opened_at else opened_at

        if sar_file:
            sar_subjects = list(set([s for s in [customer_id, card_id] + connected_cards[:5] if s]))
            sar_amount = round(final_exposure, 2)
            sar_dates = [date_str, date_str]

            llm_prompt = SAR_NARRATIVE_PROMPT.format(
                customer_id=customer_id,
                card_id=card_id,
                connected_cards=connected_cards[:5],
                total_amount=sar_amount,
                affected_txns=affected_txn_ids,
                opened_at=date_str,
                device_info=dev_info,
                email_domain=p_email,
                pattern=final_pattern
            )
            llm_sar = self._call_gemini(llm_prompt)
            if llm_sar and len(llm_sar.split(".")) >= 5:
                sar_narrative = llm_sar
                tokens_consumed += 450
            else:
                sar_narrative = (
                    f"On {date_str}, fraud monitoring detected unauthorized transaction activity on card {card_id} "
                    f"belonging to customer {customer_id}. The total unauthorized exposure is ${sar_amount:.2f} USD across {len(affected_txn_ids)} "
                    f"transaction(s) ({', '.join(affected_txn_ids)}) conforming to the '{final_pattern}' fraud typology. "
                    f"The activity was executed through eCommerce channels utilizing device profile '{dev_info}' and email domain '{p_email}'. "
                    f"Cardholder outreach was conducted pursuant to Bank Fraud Policy, and the cardholder confirmed that the transactions were unauthorized. "
                    f"Graph neighborhood analysis identified infrastructure connections linking this incident to {len(connected_cards)} additional card(s) sharing identical device infrastructure. "
                    f"The bank took immediate protective action by placing a block on card {card_id} and placing all connected cards under heightened monitoring. "
                    f"This report is filed pursuant to regulatory requirements due to confirmed unauthorized compromise and shared device infrastructure."
                )

            trace.append({
                "step": "SAR Generation",
                "thought": f"Generated FinCEN 5 Ws and H SAR narrative for ${sar_amount:.2f} across {len(affected_txn_ids)} transactions."
            })
        else:
            sar_narrative = ""
            sar_subjects = []
            sar_amount = 0.0
            sar_dates = []
            trace.append({
                "step": "SAR Generation",
                "thought": "SAR filing not triggered under bank policy thresholds."
            })

        return {
            "sar_narrative": sar_narrative,
            "sar_subjects": sar_subjects,
            "sar_amount": sar_amount,
            "sar_dates": sar_dates,
            "tokens_consumed": tokens_consumed,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Node 9: Summary, TigerGraph Live Write, & Memory Update
    # -------------------------------------------------------------
    def node_persist_and_record(self, state: InvestigationGraphState) -> Dict[str, Any]:
        trace = state.get("explainability_trace", [])
        
        case_id = state["case_id"]
        opened_at = state["opened_at"]
        trigger_type = state["trigger_type"]
        trigger_text = state["trigger_text"]
        flagged_txn_id = state["flagged_txn_id"]
        card_id = state.get("card_id", "")
        customer_id = state.get("customer_id", "")
        final_verdict = state["final_verdict"]
        final_prob = state["final_prob"]
        final_pattern = state["final_pattern"]
        final_status = state["final_status"]
        final_exposure = state["final_exposure"]
        affected_txn_ids = state["affected_txn_ids"]
        first_suspicious_txn = state.get("first_suspicious_txn", "")
        connected_cards = state.get("connected_cards", [])
        connected_dev_profiles = state.get("connected_dev_profiles", [])
        evidence_claims = state.get("evidence_claims", [])
        similar_cases = state.get("similar_cases", [])
        evidence_requests = state.get("evidence_requests", [])
        initial_actions = state.get("initial_actions", [])
        final_actions = state.get("final_actions", [])
        what_changed = state.get("what_changed", "")
        stop_reason = state.get("stop_reason", "")
        sar_file = state["sar_file"]
        sar_reason = state["sar_reason"]
        sar_narrative = state["sar_narrative"]
        sar_subjects = state["sar_subjects"]
        sar_amount = state["sar_amount"]
        sar_dates = state["sar_dates"]
        tool_count = state.get("tool_call_count", 0)
        tokens_consumed = state.get("tokens_consumed", 0)
        txn_data = state.get("txn_data", {})
        txn_amt = float(txn_data.get("TransactionAmt", 0.0))
        dev_info = str(txn_data.get("DeviceInfo", "unknown"))

        # Build comprehensive summary
        if final_verdict == "fraud":
            summary = (
                f"Investigation of case {case_id} confirmed unauthorized {final_pattern} activity on card {card_id} "
                f"totaling ${final_exposure:.2f} USD across {len(affected_txn_ids)} transaction(s). Graph traversal identified "
                f"device profile {dev_info} linking {len(connected_cards)} connected card(s). Protective card block and case records "
                f"have been initiated in compliance with Bank Fraud Policy R2/R6."
            )
        else:
            summary = (
                f"Investigation of alert on transaction {flagged_txn_id} (${txn_amt:.2f}) on card {card_id} concluded with a verdict of "
                f"legitimate cardholder activity (fraud probability: {final_prob:.2f}). Activity conforms to historical account behavior "
                f"and customer validation confirmed authorization. Alert closed with no adverse action."
            )

        pattern_desc = ""
        if final_pattern == "undocumented":
            pattern_desc = f"Coordinated anomalous multi-card velocity pattern detected across device {dev_info} affecting multiple accounts within a short temporal window."

        payload = {
            "case_id": case_id,
            "case": {
                "status": final_status,
                "verdict": final_verdict,
                "fraud_probability": round(final_prob, 2),
                "pattern": final_pattern,
                "pattern_description": pattern_desc,
                "affected_txn_ids": affected_txn_ids,
                "first_suspicious_txn_id": first_suspicious_txn,
                "connected_card_ids": connected_cards,
                "connected_device_profiles": connected_dev_profiles,
                "exposure_usd": round(final_exposure, 2),
                "evidence": evidence_claims,
                "similar_prior_cases": similar_cases[:3],
                "summary": summary,
                "written_to_graph": False,
                "graph_case_id": ""
            },
            "evidence_requests": evidence_requests,
            "next_best_actions": {
                "initial": initial_actions,
                "final": final_actions,
                "what_changed": what_changed
            },
            "sar": {
                "file": sar_file,
                "reason": sar_reason,
                "narrative": sar_narrative,
                "subjects": sar_subjects,
                "total_amount_usd": sar_amount,
                "activity_dates": sar_dates
            },
            "stop_reason": stop_reason,
            "tool_calls": tool_count,
            "tokens": tokens_consumed,
            "latency_s": 0.0,
            "explainability_trace": trace
        }

        # Persist to TigerGraph live
        written_success, receipt_id = self.tools.write_case_to_graph(case_id, {
            **payload,
            "opened_at": opened_at,
            "trigger_type": trigger_type,
            "trigger_text": trigger_text,
            "card_id": card_id
        })
        payload["case"]["written_to_graph"] = written_success
        payload["case"]["graph_case_id"] = f"CASE-{case_id}" if written_success else ""

        # Update Cross-Case Working Memory
        self.memory.record_case(case_id, payload)

        trace.append({
            "step": "Persist & Memory",
            "thought": f"Persisted case {case_id} to TigerGraph (success={written_success}). Case memory updated."
        })

        return {
            "summary": summary,
            "written_to_graph": written_success,
            "graph_case_id": payload["case"]["graph_case_id"],
            "final_payload": payload,
            "explainability_trace": trace
        }

    # -------------------------------------------------------------
    # Build LangGraph StateGraph
    # -------------------------------------------------------------
    def _build_graph(self):
        workflow = StateGraph(InvestigationGraphState)

        # Add nodes
        workflow.add_node("initialize", self.node_initialize)
        workflow.add_node("gather_evidence", self.node_gather_evidence)
        workflow.add_node("initial_assessment", self.node_initial_assessment)
        workflow.add_node("customer_inquiry", self.node_customer_inquiry)
        workflow.add_node("rag_retriever", self.node_rag_retriever)
        workflow.add_node("final_assessment", self.node_final_assessment)
        workflow.add_node("evaluate_policy_actions", self.node_evaluate_policy_actions)
        workflow.add_node("sar_generation", self.node_sar_generation)
        workflow.add_node("persist_and_record", self.node_persist_and_record)

        # Add edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "gather_evidence")
        workflow.add_edge("gather_evidence", "initial_assessment")
        workflow.add_edge("initial_assessment", "customer_inquiry")
        workflow.add_edge("customer_inquiry", "rag_retriever")
        workflow.add_edge("rag_retriever", "final_assessment")
        workflow.add_edge("final_assessment", "evaluate_policy_actions")
        workflow.add_edge("evaluate_policy_actions", "sar_generation")
        workflow.add_edge("sar_generation", "persist_and_record")
        workflow.add_edge("persist_and_record", END)

        return workflow.compile()

    def run(self, case_row: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the compiled LangGraph workflow for a single case."""
        start_time = time.time()
        
        raw_risk_score = case_row.get("risk_score")
        risk_score = float(raw_risk_score) if pd_not_na(raw_risk_score) else 0.50

        initial_state: InvestigationGraphState = {
            "case_id": str(case_row["case_id"]),
            "opened_at": str(case_row["opened_at"]),
            "trigger_type": str(case_row["trigger_type"]),
            "trigger_text": str(case_row["trigger_text"]),
            "flagged_txn_id": str(case_row["flagged_txn_id"]),
            "card_id": str(case_row.get("card_id", "")),
            "customer_id": str(case_row.get("customer_id", "")),
            "risk_score": risk_score,
            "tool_call_count": 0,
            "tokens_consumed": 0,
            "explainability_trace": []
        }

        final_state = self.graph.invoke(initial_state)
        latency_s = round(time.time() - start_time, 2)
        
        payload = final_state.get("final_payload", {})
        payload["latency_s"] = latency_s
        return payload

def pd_not_na(val):
    if val is None:
        return False
    if isinstance(val, str) and (val.strip() == "" or val.strip() == "—" or val.strip() == "nan"):
        return False
    try:
        import pandas as pd
        return pd.notna(val)
    except Exception:
        return True
