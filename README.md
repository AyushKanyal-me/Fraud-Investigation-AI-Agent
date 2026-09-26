# Agentic Fraud Investigation System

An enterprise-grade, autonomous AI fraud investigation and policy governance engine. The system automates the end-to-end investigation lifecycle for banking transactions by combining multi-hop knowledge graph analysis, dynamic tool-driven reasoning via LangGraph, GraphRAG regulatory retrieval, behavioral customer simulation, real-time token observability, and automated FinCEN Suspicious Activity Report (SAR) narrative generation.

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
- **Enterprise TigerGraph Parity:** Seamless graph analytics backed by native GSQL queries with deterministic response normalization and fallback resilience.

### LangGraph Multi-Agent Orchestrator
- **Stateful Cognitive Pipeline:** Operates a 9-stage finite state graph managing evidence collection, hypothesis generation, risk calibration, policy evaluation, and audit logging.
- **Explainability Traces:** Captures step-by-step agent reasoning at each transition, providing an audit trail for risk and compliance officers.
- **Real-Time Token Accounting:** Integrates native LLM token usage tracking (`agent/token_tracker.py`) capturing exact prompt, candidate, and total token consumption per node.

### GraphRAG Policy Retrieval
- **ChromaDB Vector Store:** Indexes banking policy rules (R1–R10), known fraud pattern typologies, historical closed cases, and FinCEN SAR regulatory guidance.
- **Active Context Retrieval:** Dynamically queries policy precedents and regulatory thresholds during case assessment to ground decisions.

### Multi-Typology Evidence Classification & Customer Simulator
- **Multi-Typology Evidence Classifier (`agent/evidence_classifier.py`):** Negation-aware regex rule engine with semantic LLM fallback for robust classification of customer communications into structured states:
  - `CONFIRMED_LEGITIMATE`
  - `DENIED_UNAUTHORIZED`
  - `RECURRING_DISPUTE`
  - `NO_REPLY_24H`
  - `STEP_UP_PASSED`
  - `STEP_UP_FAILED`
- **Dynamic Persona Simulation:** Uses contextual LLM prompts to simulate cardholder responses to SMS fraud alerts and 2FA step-up challenges rather than static mock rules.

### Regulatory Compliance & SAR Narrative Synthesis
- **FinCEN 5 Ws and H Standard:** Generates complete, self-contained SAR narratives answering Who, What, When, Where, How, and Why.
- **Automated Filing Triggers:** Enforces mandatory SAR filing when exposure exceeds $1,000 USD, when shared origin infrastructure is detected, or when undocumented fraud rings emerge.

### Live Graph Persistence & Working Memory
- **Graph Upserts:** Writes completed case vertices (`FraudCase`) and relational edges (`INVOLVES_TXN`, `INVOLVES_CARD`, `INVOLVES_CUSTOMER`) directly into TigerGraph.
- **Cross-Case Memory:** Tracks compromised cards, repeat offender devices, and suspicious email domains across investigation lifecycles.

### REST API & Interactive Visualizer
- **FastAPI Backend:** Provides REST endpoints for alert queues, case details, live on-demand investigation triggers, asynchronous evidence submission, and dashboard KPI metrics.
- **Lightweight Liveness & Diagnostic Readiness:** Fast $O(1)$ `/healthz` probe without heavy dataset loading alongside deep `/api/health` diagnostic subsystem checks.
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

The agent operates strictly within the bank's policy rules, defined centrally in [`agent/policy.py`](file:///agent/policy.py) as the single source of truth for all evaluators, prompt generators, and API endpoints:

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

### 4a. Deterministic Policy Engine vs. LLM Assistance Boundaries

A core architectural principle of this system is strict governance:
- **Authoritative Deterministic Layer (`agent/policy.py`, `agent/validator.py`):**
  - All decisions regarding actions, approval routes (`auto`, `L1`, `L2`), exposure calculation, and SAR filing mandates are 100% deterministic and strictly evaluated by code based on Rules R1–R10.
  - LLMs **never** determine whether a card is blocked, whether a SAR is filed, or which approval route is required.
  - Invariant validators strictly guarantee compliance with banking policy.
- **LLM Assistance Layer (`agent/graph.py`, `agent/prompts.py`, `agent/schemas.py`, `agent/evidence_classifier.py`):**
  - LLMs are utilized strictly for auxiliary cognitive tasks: formulating initial hypotheses, simulating realistic customer SMS/2FA dialogues, classifying ambiguous unstructured responses, and drafting narrative explanations for SAR filings.
  - All structured LLM claims are grounded and validated against verified graph evidence.

---

## 5. Project Structure

```
.
├── agent/
│   ├── graph.py               # LangGraph StateGraph engine (9 state nodes)
│   ├── workflow.py            # Unified workflow orchestrator
│   ├── tools.py               # Graph analytics tools (baseline, episode, device rings)
│   ├── policy.py              # Single-source canonical rule evaluator (R1–R10)
│   ├── evidence_classifier.py # Multi-typology classification (negation regex + LLM fallback)
│   ├── token_tracker.py       # Real token accounting and usage telemetry
│   ├── validator.py           # Invariant & schema validator
│   ├── simulator.py           # Customer dialogue & 2FA simulator
│   ├── checkpoints.py         # Durable state checkpoint store (SQLite/PostgreSQL/File)
│   ├── persistence.py         # Atomic file storage & audit logging
│   ├── card_identity.py       # Canonical card mapping engine
│   └── repository/            # Data repository (Local pandas & TigerGraph backends)
├── rag/
│   ├── vector_store.py        # ChromaDB vector store for GraphRAG
│   └── chroma_db/             # Persistent vector embeddings
├── memory/
│   ├── case_memory.py         # Cross-case working memory
│   └── case_memory.json       # Working memory storage
├── schema/
│   ├── create_schema.gsql     # TigerGraph vertex and edge schema definitions
│   └── setup_schema.py        # Schema deployment script
├── queries/
│   └── *.gsql                 # GSQL analytical queries for graph traversal
├── data_loading/
│   ├── load_data.py           # Dataset ingestion pipeline
│   └── build_next_edges.py    # Temporal transaction edge builder
├── answers/                   # Generated investigation JSON artifacts
├── cases/                     # Internal investigation state records
├── tests/                     # Unit & Integration test suite
│   ├── test_policy.py         # Policy R1-R10 test suite
│   ├── test_evidence_classifier.py # Evidence classifier unit tests
│   ├── test_token_tracker.py  # Token accounting unit tests
│   ├── test_tigergraph_parity.py   # TigerGraph mock response normalization tests
│   └── test_tigergraph_parity_live.py # Live TigerGraph integration tests
├── .github/workflows/         # CI/CD workflows
│   ├── ci.yml                 # Core test suite on push/PR
│   └── integration.yml        # Live TigerGraph integration test workflow
├── app.py                     # FastAPI backend server with CORS and auth
├── run_cases.py               # Batch investigation execution harness
├── config.py                  # Configuration, security validations, and env bindings
├── pyproject.toml            # Unified project metadata and dependencies
├── docker-compose.yml         # Container orchestration configuration
├── Dockerfile                 # Production container image
├── FRONTEND_API_CONTRACT.md   # Frontend integration guide and TypeScript interfaces
└── README.md                  # System documentation
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- TigerGraph (Cloud instance or local Community Edition)

### Environment Configuration
Create a `.env` file in the root directory (refer to `.env.example`):

```bash
# LLM Configuration
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE

# API Security (Generate a secure random key, e.g., openssl rand -hex 32)
API_AUTH_KEY=YOUR_SECURE_RANDOM_SECRET_KEY_HERE
AUTH_DISABLED=false
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# TigerGraph Settings
TIGERGRAPH_HOST=http://localhost
TIGERGRAPH_RESTPP_PORT=9000
TIGERGRAPH_GS_PORT=14240
TIGERGRAPH_USERNAME=tigergraph
TIGERGRAPH_PASSWORD=tigergraph
TIGERGRAPH_GRAPH_NAME=FraudGraph
TIGERGRAPH_SECRET=
TIGERGRAPH_API_TOKEN=
TIGERGRAPH_FALLBACK_POLICY=fallback

# Directory Settings
DATASET_DIR=Dataset
REGULATIONS_DIR=regulations
ANSWERS_DIR=answers
CASES_DIR=cases
CHECKPOINTS_DIR=checkpoints
AUDIT_LOG_DIR=logs
MEMORY_FILE=memory/case_memory.json
```

> **Security Note:** The server validates `API_AUTH_KEY` at startup to prevent running with known insecure default keys (e.g. `change-me-in-production`, `secret`, `123456`). Always set a secure random key.

### Installation
All dependencies are unified in `pyproject.toml`:

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install package in editable mode with development dependencies
pip install ".[dev]"

# 3. Optional: Install PostgreSQL checkpoint storage extra
pip install -e .[postgres]
```

### Docker Deployment
You can deploy the complete agent as a containerized service:

```bash
# Build and run using Docker Compose
docker-compose up --build -d

# Check service logs and health
docker-compose logs -f
curl http://localhost:8000/healthz
```

---

## 7. Configuration & Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API Key for LLM reasoning and SAR narratives |
| `TIGERGRAPH_HOST` | `http://localhost` | TigerGraph RESTPP endpoint |
| `TIGERGRAPH_FALLBACK_POLICY` | `fallback` | `fallback` for automatic local pandas fallback; `fail_closed` to raise `TigerGraphUnavailableError` |
| `LLM_ENHANCED_ASSESSMENT` | `false` | `true` to enable dynamic LLM hypothesis synthesis; `false` for deterministic rule engine |
| `DATA_REPOSITORY_BACKEND` | `tigergraph` | `tigergraph` or `local` |
| `CHECKPOINT_BACKEND` | `sqlite` | `sqlite`, `postgres`, or `file` |
| `SIMULATION_MODE` | `false` | `true` for offline mock execution; `false` for live LLM calls |
| `API_AUTH_KEY` | *(required)* | Header/Bearer token for API access (`X-API-Key`) |
| `AUTH_DISABLED` | `false` | Set to `true` strictly during local development testing to bypass auth |

---

## 8. Architecture Decision Records (ADRs)

### ADR-1: Deterministic Policy Engine Single-Source Definition
- **Context:** Banking compliance mandates 100% reproducible, predictable policy routing across known typologies (R1–R10). Having policy descriptions duplicated across prompts, validators, and endpoints leads to divergence.
- **Decision:** Centrally define rules, conditions, action maps, and approval requirements in `agent/policy.py`. All state nodes, validator invariants, and prompt templates dynamically derive from this single source of truth.

### ADR-2: Multi-Typology Evidence Classification with Negation Handling
- **Context:** Customer responses often contain complex phrasings (e.g. "No, this was not me", "I never bought this", "I did this"). Simple keyword substring matching misclassifies negated statements.
- **Decision:** Implement `agent/evidence_classifier.py` using prioritized, negation-aware regex rules covering multiple typologies with optional LLM fallback for ambiguous text, and fail-safe non-blocking defaults (`NO_REPLY_24H` / `UNCERTAIN`).

### ADR-3: Native Token Usage Accounting
- **Context:** Estimating token usage with fixed character multipliers produces inaccurate audit trails.
- **Decision:** Implement `agent/token_tracker.py` to extract real token metrics directly from provider metadata (`usage_metadata.prompt_token_count`, `candidates_token_count`, `total_token_count`) and LangChain callbacks, recording token consumption per investigation node.

### ADR-4: Fast Liveness vs Deep Subsystem Readiness
- **Context:** Orchestrators (Kubernetes/ECS) require frequent liveness probes (`/healthz`) that must return in $< 10\text{ms}$ without triggering heavy ~600k row dataset loads into memory.
- **Decision:** Decouple `/healthz` ($O(1)$ instant check) from `/api/health` (deep readiness probe verifying TigerGraph, ChromaDB vector indices, and case memory).

### ADR-5: TigerGraph Fail-Closed vs Fallback Policy
- **Context:** CI and local testing frequently operate without live graph infrastructure, whereas production banking environments mandate graph-native execution without silent fallbacks.
- **Decision:** Configure `TIGERGRAPH_FALLBACK_POLICY`. Default to `fallback` in development/CI and `fail_closed` in production, raising `TigerGraphUnavailableError` upon connection failure.

---

## 9. Execution & Testing Guide

### Running Batch Case Investigations
To execute the complete LangGraph investigation workflow across all cases:

```bash
python run_cases.py
```
This will:
1. Initialize the ChromaDB GraphRAG vector store.
2. Index dataset transactions with canonical card mappings.
3. Execute the 9-node LangGraph agent for each case.
4. Record exact token usage per investigation node.
5. Run semantic and policy validation on the outputs.
6. Persist JSON deliverables into `answers/` and `cases/`.

### Starting the FastAPI Server
To start the REST API for the frontend dashboard:

```bash
uvicorn app:app --reload --port 8000
```
- **API Base URL:** `http://localhost:8000`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`

### Running the Test Suite
```bash
# Run all unit tests
pytest

# Run tests with coverage
pytest --cov=agent --cov-report=term-missing

# Run live TigerGraph integration tests (requires live TigerGraph instance)
RUN_TIGERGRAPH_LIVE_TESTS=true pytest tests/test_tigergraph_parity_live.py
```

---

## 10. REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/healthz` | Lightweight $O(1)$ liveness check for orchestrators |
| `GET` | `/api/health` | Deep diagnostic subsystem health check (TigerGraph, ChromaDB, Memory) |
| `GET` | `/api/stats` | Executive KPI summary metrics across all cases |
| `GET` | `/api/cases` | Case inbox listing with filtering (`?status=fraud\|legitimate\|uncertain`) |
| `GET` | `/api/cases/{case_id}` | Full case investigation JSON detail |
| `POST` | `/api/cases/{case_id}/investigate` | Trigger real-time LangGraph investigation |
| `POST` | `/api/cases/{case_id}/evidence/submit` | Submit human-in-the-loop evidence / resume investigation from checkpoint |
| `POST` | `/api/investigate/custom` | Investigate an ad-hoc custom transaction alert |
| `GET` | `/api/graph/{case_id}` | Node-link graph for interactive network visualizers (Cytoscape/D3) |
| `GET` | `/api/policies` | Policy rules (R1–R10), approval routes, and metadata |

---

## 11. Frontend Integration & Graph Visualization

For frontend engineers building dashboards or analyst workbenches, refer to [`FRONTEND_API_CONTRACT.md`](FRONTEND_API_CONTRACT.md) for:
- TypeScript interfaces (`CaseInvestigationResponse`, `CaseSubgraphResponse`, `PolicyAction`, `ExplainabilityStep`).
- Pre-formatted node/edge schemas for Cytoscape.js, Vis.js, and D3.js graph visualizers.
- UI widget recommendations and design tokens.
