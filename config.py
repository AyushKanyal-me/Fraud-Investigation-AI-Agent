import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# API Keys & Auth
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
API_AUTH_KEY = os.getenv("API_AUTH_KEY")
CHECKPOINT_BACKEND = os.getenv("CHECKPOINT_BACKEND", "sqlite")


# Server / CORS Settings
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]

# Mode Flags
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")
DATA_REPOSITORY_BACKEND = os.getenv("DATA_REPOSITORY_BACKEND", "tigergraph")
TIGERGRAPH_FALLBACK_POLICY = os.getenv("TIGERGRAPH_FALLBACK_POLICY", "fallback").strip().lower()
LLM_ENHANCED_ASSESSMENT = os.getenv("LLM_ENHANCED_ASSESSMENT", "false").lower() in ("true", "1", "yes")


# TigerGraph Settings
TG_HOST = os.getenv("TIGERGRAPH_HOST", "http://localhost")
TG_RESTPP_PORT = int(os.getenv("TIGERGRAPH_RESTPP_PORT", 9000))
TG_GS_PORT = int(os.getenv("TIGERGRAPH_GS_PORT", 14240))
TG_USERNAME = os.getenv("TIGERGRAPH_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TIGERGRAPH_PASSWORD", "tigergraph")
TG_GRAPH_NAME = os.getenv("TIGERGRAPH_GRAPH_NAME", "FraudGraph")
TG_SECRET = os.getenv("TIGERGRAPH_SECRET", "")
TG_API_TOKEN = os.getenv("TIGERGRAPH_API_TOKEN", "")

# Directory Paths
DATASET_DIR = BASE_DIR / os.getenv("DATASET_DIR", "Dataset")
REGULATIONS_DIR = BASE_DIR / os.getenv("REGULATIONS_DIR", "regulations")
ANSWERS_DIR = BASE_DIR / os.getenv("ANSWERS_DIR", "answers")
CASES_DIR = BASE_DIR / os.getenv("CASES_DIR", "cases")
CHECKPOINTS_DIR = BASE_DIR / os.getenv("CHECKPOINTS_DIR", "checkpoints")
AUDIT_LOG_DIR = BASE_DIR / os.getenv("AUDIT_LOG_DIR", "logs")
MEMORY_FILE = BASE_DIR / os.getenv("MEMORY_FILE", "memory/case_memory.json")

# Ensure required directories exist
ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
CASES_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

# Canonical Fraud Patterns Enum (Dataset/README.md)
PATTERNS = [
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none"
]

# Canonical Action Types Enum (Fraud Policy Section 1)
ACTION_TYPES = [
    "ALLOW_TRANSACTION",
    "DECLINE_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD"
]

# Canonical Approval Routes Enum (Fraud Policy Section 2)
APPROVAL_ROUTES = ["auto", "L1", "L2"]

# Canonical Policy Rules Definition (Dataset/README.md R1-R10)
POLICY_RULES = {
    "R1": {
        "id": "R1",
        "title": "Verify Before Blocking on Weak Signal",
        "description": "If the case rests on a single signal (including risk score alone) and assessed fraud probability is below 0.70, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate customer on one signal is a policy breach.",
        "actions": ["VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH"],
        "sar_trigger": False
    },
    "R2": {
        "id": "R2",
        "title": "Customer Denies Transaction",
        "description": "Customer denies the transaction. Recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud.",
        "actions": ["BLOCK_CARD", "CREATE_CASE", "FILE_REPORT"],
        "sar_trigger": True
    },
    "R3": {
        "id": "R3",
        "title": "Customer Confirms Transaction",
        "description": "Customer confirms the transaction. Recommend CLOSE_NO_FRAUD and ALLOW_TRANSACTION. Note the confirmation in the case file.",
        "actions": ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"],
        "sar_trigger": False
    },
    "R4": {
        "id": "R4",
        "title": "No Customer Reply Within 24 Hours",
        "description": "No reply within 24 hours. Recommend MONITOR_CARD and DECLINE_TRANSACTION for pending authorizations. Escalate (ESCALATE_TO_ANALYST) if exposure exceeds $500.",
        "actions": ["MONITOR_CARD", "DECLINE_TRANSACTION", "ESCALATE_TO_ANALYST"],
        "sar_trigger": False
    },
    "R5": {
        "id": "R5",
        "title": "Card Testing Pattern",
        "description": "Three or more small online authorizations on one card within an hour, followed by a larger purchase: recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a purchase over $100 has already cleared, recommend BLOCK_CARD.",
        "actions": ["DECLINE_TRANSACTION", "STEP_UP_AUTH", "BLOCK_CARD"],
        "sar_trigger": False
    },
    "R6": {
        "id": "R6",
        "title": "Shared Origin Across Cards",
        "description": "When several cards show fraud from the same device profile, billing region, or recipient email in one window, name shared element, recommend CREATE_CASE, FILE_REPORT, and MONITOR_CONNECTED_CARDS for every card that shares it.",
        "actions": ["CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"],
        "sar_trigger": True
    },
    "R7": {
        "id": "R7",
        "title": "Disputed But Legitimate Recurring Pattern",
        "description": "When customer disputes a charge that matches their recurring pattern (same merchant, amount, monthly), recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, and WARN_CUSTOMER. Do not block. Final resolution closes as CLOSE_NO_FRAUD.",
        "actions": ["CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER", "CLOSE_NO_FRAUD"],
        "sar_trigger": False
    },
    "R8": {
        "id": "R8",
        "title": "Escalate When Uncertain and Exposed",
        "description": "If verdict is uncertain and exposure exceeds $500, or evidence conflicts, recommend ESCALATE_TO_ANALYST.",
        "actions": ["CREATE_CASE", "MONITOR_CARD", "ESCALATE_TO_ANALYST"],
        "sar_trigger": False
    },
    "R9": {
        "id": "R9",
        "title": "Undocumented Fraud Patterns",
        "description": "When activity fits none of the known patterns but evidence shows coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST, and describe pattern in own words.",
        "actions": ["CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST"],
        "sar_trigger": True
    },
    "R10": {
        "id": "R10",
        "title": "Restrictions on Blocking All Cards",
        "description": "Never BLOCK_ALL_CARDS unless at least two of customer's cards show confirmed fraud or customer's credentials are confirmed compromised.",
        "actions": ["BLOCK_ALL_CARDS"],
        "sar_trigger": False
    }
}
