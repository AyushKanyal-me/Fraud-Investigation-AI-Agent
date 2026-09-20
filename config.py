import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "YOUR_GEMINI_API_KEY_HERE"

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
DATASET_DIR = BASE_DIR / os.getenv("DATASET_DIR", "Datatset")
REGULATIONS_DIR = BASE_DIR / os.getenv("REGULATIONS_DIR", "regulations")
ANSWERS_DIR = BASE_DIR / os.getenv("ANSWERS_DIR", "answers")
MEMORY_FILE = BASE_DIR / os.getenv("MEMORY_FILE", "memory/case_memory.json")

# Ensure required directories exist
ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

# Fraud Patterns Enum
PATTERNS = [
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none"
]

# Action Types Enum (Fraud Policy Section 1)
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

# Approval Routes Enum
APPROVAL_ROUTES = ["auto", "L1", "L2"]

# Policy Rules Definition
POLICY_RULES = {
    "R1": {
        "id": "R1",
        "title": "Card Testing Pattern",
        "description": "≥3 small txns (<$15) within 10 minutes, followed by a large txn ($>100) on the same card.",
        "actions": ["BLOCK_CARD", "NOTIFY_CUSTOMER_SMS"],
        "sar_trigger": False
    },
    "R2": {
        "id": "R2",
        "title": "New Device + High Amount (CNP)",
        "description": "Card-not-present txn on an unseen DeviceID/DeviceType where amount > $500 or amount > 3x 30-day card average.",
        "actions": ["TEMP_SUSPEND", "REQUEST_ID_DOCS", "NOTIFY_CUSTOMER_SMS"],
        "sar_trigger": False
    },
    "R3": {
        "id": "R3",
        "title": "Geographic Anomaly / Impossible Speed",
        "description": "Txn occurring in an addr1/addr2 distinct from card's 30-day primary region within < 4 hours of previous transaction in home region.",
        "actions": ["TEMP_SUSPEND", "NOTIFY_CUSTOMER_CALL"],
        "sar_trigger": False
    },
    "R4": {
        "id": "R4",
        "title": "Account Takeover Signature",
        "description": "Email domain change (P_emaildomain or R_emaildomain mismatch with customer profile) + new device + password reset / high value txn within 24 hours.",
        "actions": ["FORCE_PASSWORD_RESET", "BLOCK_CARD", "REQUEST_ID_DOCS"],
        "sar_trigger": True
    },
    "R5": {
        "id": "R5",
        "title": "Shared Entity Fraud Ring",
        "description": "Card or Customer shares DeviceID or Email with 2+ other cards that had confirmed fraud in closed_cases_history.",
        "actions": ["BLOCK_CARD", "ADD_TO_WATCHLIST", "FILE_SAR"],
        "sar_trigger": True
    },
    "R6": {
        "id": "R6",
        "title": "High Exposure Threshold for Card Block Approval",
        "description": "If confirmed/estimated fraud exposure ≤ $2,500, BLOCK_CARD routes to L1. If > $2,500, BLOCK_CARD requires L2 approval.",
        "actions": ["BLOCK_CARD"],
        "sar_trigger": False
    },
    "R7": {
        "id": "R7",
        "title": "SAR Filing Mandatory Criteria",
        "description": "SAR filing is mandatory if total fraud exposure across connected entities ≥ $10,000, OR if Account Takeover / Fraud Ring (R4/R5) is confirmed with exposure ≥ $5,000, OR structured transactions (FinCEN AML).",
        "actions": ["FILE_SAR"],
        "sar_trigger": True
    },
    "R8": {
        "id": "R8",
        "title": "Customer Communication Rules",
        "description": "NOTIFY_CUSTOMER_SMS is auto-approved. NOTIFY_CUSTOMER_CALL requires L1 approval. TEMP_SUSPEND is auto-approved.",
        "actions": ["NOTIFY_CUSTOMER_SMS", "NOTIFY_CUSTOMER_CALL", "TEMP_SUSPEND"],
        "sar_trigger": False
    },
    "R9": {
        "id": "R9",
        "title": "Legitimate Behavior & False Positive Clearance",
        "description": "If cardholder confirms transaction via simulated reply OR txn aligns with 90-day spending history with matching device/IP/email, close with CLOSE_NO_ACTION.",
        "actions": ["CLOSE_NO_ACTION"],
        "sar_trigger": False
    },
    "R10": {
        "id": "R10",
        "title": "Watchlist & Monitoring Placement",
        "description": "Place customer/card on watchlist if fraud probability is between 0.40 and 0.70 without conclusive proof, or if card is connected to suspicious clusters.",
        "actions": ["ADD_TO_WATCHLIST"],
        "sar_trigger": False
    }
}
