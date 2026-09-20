# Agentic Fraud Investigation System

An enterprise-grade, autonomous AI fraud investigation and policy governance engine. The system automates the end-to-end investigation lifecycle for banking transactions by combining multi-hop knowledge graph analysis, dynamic tool-driven reasoning via LangGraph, GraphRAG regulatory retrieval, behavioral customer simulation, and automated FinCEN Suspicious Activity Report (SAR) narrative generation.

---

## 1. System Overview

Traditional fraud monitoring systems flag transactions with real-time risk scores but leave the complex investigation process to human analysts. Analysts must manually reconstruct customer spending baselines, trace device and network links across accounts, verify policy compliance, simulate customer outreach, and draft regulatory filings.

This system acts as an autonomous AI investigator operating under strict banking governance rules. It transforms raw transaction alerts into defensible decisions, executes multi-stage policy evaluations, and persists structured case records back into the knowledge graph for cross-case memory.

---

## 2. Core Capabilities

### Multi-Hop Knowledge Graph Traversal
- **Time-Bounded Historical Baselines:** Evaluates 30-day customer spending baselines strictly prior to the alert timestamp, eliminating lookahead bias.
- **Temporal Episode Expansion:** Groups burst authorizations, velocity spikes, and micro-authorization card testing sequences ($<$\$15) within sliding time windows.
- **Hardware Profile & Ring Detection:** Identifies shared device fingerprints (OS, browser, hardware profiles) across multiple distinct card accounts within 7-day lookbacks.

### LangGraph Multi-Agent Orchestrator
- **Stateful Cognitive Pipeline:** Operates a 9-stage finite state graph managing evidence collection, hypothesis generation, risk calibration, policy evaluation, and audit logging.
- **Explainability Traces:** Captures step-by-step agent reasoning at each transition, providing an audit trail for risk and compliance officers.

### GraphRAG Policy Retrieval
- **ChromaDB Vector Store:** Indexes banking policy rules (R1–R10), known fraud pattern typologies, historical closed cases, and FinCEN SAR regulatory guidance.
- **Active Context Retrieval:** Dynamically queries policy precedents and regulatory thresholds during case assessment to ground decisions.

### Behavioral Customer & 2FA Simulator
- **Dynamic Persona Simulation:** Uses contextual LLM prompts to simulate cardholder responses to SMS fraud alerts and 2FA step-up challenges rather than using static rules.
- **Outcome Classification:** Classifies cardholder replies into structured states (`CONFIRMED_LEGITIMATE`, `DENIED_UNAUTHORIZED`, `RECURRING_DISPUTE`, `STEP_UP_FAILED`).

### Regulatory Compliance & SAR Narrative Synthesis
- **FinCEN 5 Ws and H Standard:** Generates complete, self-contained SAR narratives answering Who, What, When, Where, How, and Why.
- **Automated Filing Triggers:** Enforces mandatory SAR filing when exposure exceeds $1,000 USD, when shared origin infrastructure is detected, or when undocumented fraud rings emerge.

### Live Graph Persistence & Working Memory
- **Graph Upserts:** Writes completed case vertices (`FraudCase`) and relational edges (`INVOLVES_TXN`, `INVOLVES_CARD`, `INVOLVES_CUSTOMER`) directly into TigerGraph.
- **Cross-Case Memory:** Tracks compromised cards, repeat offender devices, and suspicious email domains across investigation lifecycles.

### REST API & Interactive Visualizer
- **FastAPI Backend:** Provides REST endpoints for alert queues, case details, live on-demand investigation triggers, and dashboard KPI metrics.
- **Graph Visualization Subgraphs:** Emits node-link payloads compatible with Cytoscape.js, Vis.js, and D3.js.

---

## 3. Architecture & Cognitive Pipeline

The investigation lifecycle is governed by a compiled LangGraph state machine:

```
[Trigger Alert]
       │
       ▼
[node_initialize] ──────────► Formulates initial hypothesis and state containers
       │
       ▼
[node_gather_evidence] ────► Executes graph queries (baseline, episode expansion, device rings)
       │
       ▼
[node_initial_assessment] ─► Calibrates initial fraud probability & identifies pattern
       │
       ▼
[node_customer_inquiry] ───► Dynamic customer verification / step-up auth simulation
       │
       ▼
[node_rag_retriever] ──────► Fetches relevant FinCEN guidance & policy rules from vector store
       │
       ▼
[node_final_assessment] ───► Synthesizes final verdict, calibrated risk, and "what changed" delta
       │
       ▼
[node_evaluate_policy] ────► Maps policy actions and determines approval routes (auto, L1, L2)
       │
       ▼
[node_sar_generation] ─────► Synthesizes FinCEN 5 Ws and H narrative (if mandated by policy)
       │
       ▼
[node_persist_and_record] ─► Upserts case to TigerGraph & updates cross-case working memory
       │
       ▼
     [END]
```

---

## 4. Bank Fraud Policy & Governance (Rules R1–R10)

The agent operates strictly within the bank's policy rules:

| Rule | Title | Condition | Permitted Actions |
| :--- | :--- | :--- | :--- |
| **R1** | Single Signal Verification | Probability $< 0.70$ on single alert | `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH` |
| **R2** | Customer Denial | Customer denies transaction | `BLOCK_CARD`, `CREATE_CASE`, `FILE_REPORT` (if exposure $> \$1,000$) |
| **R3** | Customer Confirmation | Customer confirms transaction | `ALLOW_TRANSACTION`, `CLOSE_NO_FRAUD` |
| **R4** | Unreachable Customer | No reply within 24 hours | `MONITOR_CARD`, `DECLINE_TRANSACTION`, `ESCALATE_TO_ANALYST` (if exposure $> \$500$) |
| **R5** | Card Testing Pattern | $\ge 3$ micro-txns ($< \$15$) in 1 hour + large txn | `DECLINE_TRANSACTION`, `BLOCK_CARD` (if large txn cleared), `STEP_UP_AUTH` |
| **R6** | Shared Origin Cluster | 2+ cards sharing device/region/email | `CREATE_CASE`, `FILE_REPORT`, `MONITOR_CONNECTED_CARDS` |
| **R7** | Recurring Dispute | Disputed charge matches monthly baseline | `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER` (no card block) |
| **R8** | Uncertain Exposure | Verdict uncertain and exposure $> \$500$ | `CREATE_CASE`, `MONITOR_CARD`, `ESCALATE_TO_ANALYST` |
| **R9** | Undocumented Typology | Emerging multi-party coordination | `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST` |
| **R10** | Multi-Card Compromise | 2+ cards of same customer compromised | `BLOCK_ALL_CARDS` |

### Approval Routing Matrix
- **`auto` (Automated):** `ALLOW_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `GENERATE_REPORT`, `CREATE_CASE`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD`
- **`L1` (Team Lead Approval):** `DECLINE_TRANSACTION`; `BLOCK_CARD` when exposure $\le \$2,500$ USD
- **`L2` (Risk VP Approval):** `BLOCK_CARD` when exposure $> \$2,500$ USD; `BLOCK_ALL_CARDS`; `FILE_REPORT`

---

## 5. Project Structure

```
.
├── agent/
│   ├── graph.py             # LangGraph StateGraph engine (9 state nodes)
│   ├── workflow.py          # Unified workflow orchestrator
│   ├── tools.py             # TigerGraph tools (baseline, episode, device rings)
│   ├── langchain_tools.py   # LangChain tool bindings
│   ├── simulator.py         # Dynamic customer dialogue & 2FA simulator
│   ├── policy.py            # Rule evaluator & approval router (R1-R10)
│   ├── prompts.py           # Investigation, simulation, and SAR prompt templates
│   ├── card_identity.py     # Canonical card mapping engine
│   └── canonical_card_map.pkl # Pre-computed card mapping index
├── rag/
│   ├── vector_store.py      # ChromaDB vector store for GraphRAG
│   └── chroma_db/           # Persistent vector embeddings
├── memory/
│   ├── case_memory.py       # Cross-case working memory
│   └── case_memory.json     # Working memory storage
├── output/
│   └── validator.py         # Semantic output schema and policy validator
├── schema/
│   ├── create_schema.gsql   # TigerGraph vertex and edge schema definitions
│   └── setup_schema.py      # Schema deployment script
├── queries/
│   └── *.gsql               # GSQL analytical queries for graph traversal
├── data_loading/
│   ├── load_data.py         # Dataset ingestion pipeline
│   └── build_next_edges.py  # Temporal transaction edge builder
├── answers/                 # Generated investigation JSON artifacts
├── cases/                   # Mirror case deliverables
├── app.py                   # FastAPI backend server with CORS and visualizer endpoints
├── run_cases.py             # Batch investigation execution harness
├── config.py                # Configuration and environment bindings
├── requirements.txt         # Project dependencies
├── FRONTEND_API_CONTRACT.md # Frontend integration guide and TypeScript interfaces
└── README.md                # System documentation
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- TigerGraph (Savanna cloud instance or local Community Edition)

### Environment Configuration
Create a `.env` file in the root directory:

```bash
# LLM Configuration (Optional: system operates with robust fallback if unset)
GEMINI_API_KEY=YOUR_API_KEY_HERE

# TigerGraph Settings
TIGERGRAPH_HOST=http://localhost
TIGERGRAPH_RESTPP_PORT=9000
TIGERGRAPH_GS_PORT=14240
TIGERGRAPH_USERNAME=tigergraph
TIGERGRAPH_PASSWORD=tigergraph
TIGERGRAPH_GRAPH_NAME=FraudGraph
TIGERGRAPH_SECRET=
TIGERGRAPH_API_TOKEN=

# Directory Settings
DATASET_DIR=Datatset
REGULATIONS_DIR=regulations
ANSWERS_DIR=answers
MEMORY_FILE=memory/case_memory.json
```

### Installation
```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 7. Execution Guide

### Running Batch Case Investigations
To execute the complete LangGraph investigation workflow across all test cases:

```bash
python run_cases.py
```
This will:
1. Initialize the ChromaDB GraphRAG vector store.
2. Index dataset transactions with canonical card mappings.
3. Execute the 9-node LangGraph agent for each case.
4. Run semantic and policy validation on the outputs.
5. Persist JSON deliverables into `answers/` and `cases/`.

### Starting the FastAPI Server
To start the REST API for the frontend dashboard:

```bash
uvicorn app:app --reload --port 8000
```
- **API Base URL:** `http://localhost:8000`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`

---

## 8. REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Subsystem health check (TigerGraph, ChromaDB, Memory) |
| `GET` | `/api/stats` | Executive KPI summary metrics across all cases |
| `GET` | `/api/cases` | Case inbox listing with filtering (`?status=fraud\|legitimate\|uncertain`) |
| `GET` | `/api/cases/{case_id}` | Full case investigation JSON detail |
| `POST` | `/api/cases/{case_id}/investigate` | Trigger real-time LangGraph investigation |
| `POST` | `/api/investigate/custom` | Investigate an ad-hoc custom transaction alert |
| `GET` | `/api/graph/{case_id}` | Node-link graph for interactive network visualizers (Cytoscape/D3) |
| `GET` | `/api/policies` | Policy rules (R1–R10) and approval routes |

---

## 9. Frontend Integration & Graph Visualization

For frontend engineers building dashboards or analyst workbenches, refer to [`FRONTEND_API_CONTRACT.md`](FRONTEND_API_CONTRACT.md) for:
- TypeScript interfaces (`CaseInvestigationResponse`, `CaseSubgraphResponse`, `PolicyAction`, `ExplainabilityStep`).
- Pre-formatted node/edge schemas for Cytoscape.js, Vis.js, and D3.js graph visualizers.
- UI widget recommendations and design tokens.
