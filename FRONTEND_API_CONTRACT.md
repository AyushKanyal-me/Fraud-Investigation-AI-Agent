# Frontend Integration Guide & API Contract
**TigerGraph Agentic Fraud Investigation System — Hacker House Goa 2026**

This document specifies the complete API contracts, data models, endpoints, and frontend visualization recommendations for building the analyst dashboard UI.

---

## 1. Quick Start for Frontend Developers

### Starting the Backend API Server
The backend is powered by FastAPI and LangGraph.

```bash
# 1. Activate Python virtual environment
source .venv/bin/activate

# 2. Start the API server on port 8000
uvicorn app:app --reload --port 8000
```
- **Base URL:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **CORS:** Enabled for all origins (`*`) — works with Next.js, Vite/React, Vue, or Angular without proxy configuration.

---

## 2. TypeScript Data Interfaces

```typescript
export type Verdict = 'fraud' | 'legitimate' | 'uncertain';
export type CaseStatus = 'open' | 'closed_fraud' | 'closed_legitimate' | 'escalated';
export type ApprovalRoute = 'auto' | 'L1' | 'L2';
export type EvidenceSource = 'graph' | 'document' | 'customer' | 'external';
export type TriggerType = 'risk_score' | 'customer_report' | 'analyst_request';

export interface DashboardStats {
  total_cases: number;
  fraud_cases: number;
  legitimate_cases: number;
  uncertain_cases: number;
  sars_filed: number;
  total_exposure_usd: number;
  average_latency_s: number;
}

export interface CaseListItem {
  case_id: string;
  opened_at: string;
  trigger_type: TriggerType;
  trigger_text: string;
  flagged_txn_id: string;
  card_id: string;
  customer_id: string;
  risk_score: number | null;
  investigated: boolean;
  verdict: Verdict | 'uninvestigated';
  fraud_probability: number | null;
  pattern: string;
  exposure_usd: number;
  sar_filed: boolean;
  summary: string;
}

export interface EvidenceItem {
  claim: string;
  source: EvidenceSource;
  ref: string;
  entity_ids: string[];
}

export interface EvidenceRequest {
  type: 'customer_validation' | 'step_up_auth' | 'analyst_info';
  asked_after_step: number;
  assumed_response: string;
}

export interface PolicyAction {
  action: string;
  route: ApprovalRoute;
  reason: string;
}

export interface SARReport {
  file: boolean;
  reason: string;
  narrative: string;
  subjects: string[];
  total_amount_usd: number;
  activity_dates: string[];
}

export interface ExplainabilityStep {
  step: string;
  thought: string;
}

export interface CaseInvestigationResponse {
  case_id: string;
  case: {
    status: CaseStatus;
    verdict: Verdict;
    fraud_probability: number;
    pattern: string;
    pattern_description: string;
    affected_txn_ids: string[];
    first_suspicious_txn_id: string;
    connected_card_ids: string[];
    connected_device_profiles: string[];
    exposure_usd: number;
    evidence: EvidenceItem[];
    similar_prior_cases: string[];
    summary: string;
    written_to_graph: boolean;
    graph_case_id: string;
  };
  evidence_requests: EvidenceRequest[];
  next_best_actions: {
    initial: PolicyAction[];
    final: PolicyAction[];
    what_changed: string;
  };
  sar: SARReport;
  stop_reason: string;
  tool_calls: number;
  tokens: number;
  latency_s: number;
  explainability_trace: ExplainabilityStep[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'FraudCase' | 'Customer' | 'Card' | 'Transaction' | 'Device';
  data: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  data: Record<string, any>;
}

export interface CaseSubgraphResponse {
  case_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    node_count: number;
    edge_count: number;
    verdict: Verdict;
    pattern: string;
  };
}
```

---

## 3. REST API Endpoint Reference

### 3.1. Dashboard Summary
- **Endpoint:** `GET /api/stats`
- **Description:** Returns aggregate KPI metrics across all 20 investigated cases.
- **Sample Response:**
```json
{
  "total_cases": 20,
  "fraud_cases": 16,
  "legitimate_cases": 4,
  "uncertain_cases": 0,
  "sars_filed": 3,
  "total_exposure_usd": 3383.15,
  "average_latency_s": 0.26
}
```

---

### 3.2. List All Alerts & Cases
- **Endpoint:** `GET /api/cases`
- **Query Parameters:**
  - `status` *(optional)*: Filter by verdict (`all`, `fraud`, `legitimate`, `uncertain`).
- **Description:** Returns the complete case inbox queue.

---

### 3.3. Get Full Case Investigation Detail
- **Endpoint:** `GET /api/cases/{case_id}`
- **Path Parameter:** `case_id` (e.g., `HHG-011`)
- **Description:** Returns the complete investigation artifact including graph evidence, next best actions, SAR report, and step-by-step explainability trace.

---

### 3.4. Trigger Live LangGraph Investigation
- **Endpoint:** `POST /api/cases/{case_id}/investigate`
- **Path Parameter:** `case_id` (e.g., `HHG-003`)
- **Description:** Re-runs the multi-step LangGraph StateGraph live, executes dynamic graph tools, customer simulation, and vector policy lookups, writes the result to disk and TigerGraph, and returns the fresh JSON payload.

---

### 3.5. Investigate Custom Ad-Hoc Transaction
- **Endpoint:** `POST /api/investigate/custom`
- **Request Body:**
```json
{
  "case_id": "CUSTOM-001",
  "opened_at": "2016-12-30 14:00:00",
  "trigger_type": "risk_score",
  "trigger_text": "Real-time anomaly score spike on high-velocity device",
  "flagged_txn_id": "3583368",
  "card_id": "C11923-K2",
  "customer_id": "C11923",
  "risk_score": 0.92
}
```

---

### 3.6. Interactive Graph Visualizer Subgraph
- **Endpoint:** `GET /api/graph/{case_id}`
- **Description:** Returns nodes and edges formatted for Cytoscape.js, Vis.js, D3.js, or ECharts.
- **Sample Response:**
```json
{
  "case_id": "HHG-011",
  "nodes": [
    { "id": "CASE-HHG-011", "label": "Case HHG-011", "type": "FraudCase", "data": { "verdict": "fraud", "pattern": "card_testing", "exposure_usd": 204.49 } },
    { "id": "C11923", "label": "Customer C11923", "type": "Customer", "data": {} },
    { "id": "C11923-K2", "label": "Card C11923-K2", "type": "Card", "data": { "is_primary": true } },
    { "id": "TXN-3583368", "label": "Txn 3583368 ($131.30)", "type": "Transaction", "data": { "amount": 131.30, "is_flagged": true } },
    { "id": "DEV-SM-G610F Build/NRD90M", "label": "SM-G610F Build/NRD90M", "type": "Device", "data": { "device_type": "mobile" } },
    { "id": "C05595-K1", "label": "Ring Card C05595-K1", "type": "Card", "data": { "is_connected_ring": true } }
  ],
  "edges": [
    { "id": "e_CASE-HHG-011_C11923_INVOLVES_CUSTOMER", "source": "CASE-HHG-011", "target": "C11923", "label": "INVOLVES_CUSTOMER" },
    { "id": "e_C11923-K2_TXN-3583368_MADE", "source": "C11923-K2", "target": "TXN-3583368", "label": "MADE" },
    { "id": "e_TXN-3583368_DEV-SM-G610F Build/NRD90M_USED_DEVICE", "source": "TXN-3583368", "target": "DEV-SM-G610F Build/NRD90M", "label": "USED_DEVICE" },
    { "id": "e_C11923-K2_C05595-K1_SHARED_DEVICE_RING", "source": "C11923-K2", "target": "C05595-K1", "label": "SHARED_DEVICE_RING" }
  ],
  "summary": {
    "node_count": 14,
    "edge_count": 23,
    "verdict": "fraud",
    "pattern": "card_testing"
  }
}
```

---

### 3.7. Bank Policy Rules & Permissions
- **Endpoint:** `GET /api/policies`
- **Description:** Returns the bank's fraud policy rules (R1–R10) and approval routes (`auto`, `L1`, `L2`).

---

## 4. Suggested UI Screen Layouts & Color Palette

### Recommended Color Tokens:
- **Fraud Alert / High Risk:** `#EF4444` (Red-500)
- **Legitimate / Cleared:** `#10B981` (Emerald-500)
- **Uncertain / Pending:** `#F59E0B` (Amber-500)
- **Primary TigerGraph Orange:** `#F97316` (Orange-500)
- **Approval Route `auto`:** `#10B981` (Emerald badge)
- **Approval Route `L1` (Lead):** `#3B82F6` (Blue badge)
- **Approval Route `L2` (Risk VP):** `#8B5CF6` (Purple badge)

### Recommended Dashboard Widgets:
1. **Top Header**: KPI cards (Total Cases, Confirmed Fraud %, Dollars Prevented, Active SAR Filings).
2. **Left Panel**: Alert Inbox table with instant filters (`All`, `High Risk`, `Analyst Requests`, `Customer Disputes`).
3. **Center Main Panel**:
   - **Case Header**: Case ID, trigger text, risk score vs. calibrated fraud probability gauge.
   - **Interactive TigerGraph Graph Visualizer**: Zoomable cluster map showing Card $\rightarrow$ Device $\rightarrow$ Ring linkages.
   - **Explainability Timeline**: Vertical stepper showing the LangGraph ReAct thoughts:
     - *Initialize* $\rightarrow$ *Gather Evidence* $\rightarrow$ *Customer Simulation* $\rightarrow$ *GraphRAG Policy Retrieval* $\rightarrow$ *Final Decision*.
4. **Right Drawer / Split**:
   - **Action & Governance Hub**: Initial vs. Final Next Best Actions with `auto` / `L1` / `L2` badges.
   - **Customer Dialogue Simulation**: Chat bubble view showing the cardholder SMS / 2FA interaction.
   - **FinCEN SAR Narrative Card**: One-click **"Copy SAR for Filing"** button with full 5 Ws and H text.
