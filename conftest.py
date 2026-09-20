import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure test suite runs with standard test API key and in-memory/test settings by default
os.environ.setdefault("API_AUTH_KEY", "test-secret-key-32-characters-long")
os.environ.setdefault("DATA_REPOSITORY_BACKEND", "local")
os.environ.setdefault("SIMULATION_MODE", "true")
os.environ.setdefault("CHECKPOINT_BACKEND", "sqlite")
