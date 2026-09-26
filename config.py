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

# Canonical Policy Rules and Enums (Single source of truth in agent/policy.py)
from agent.policy import (
    PATTERNS,
    ACTION_TYPES,
    APPROVAL_ROUTES,
    POLICY_RULES,
)

