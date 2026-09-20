import os
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import DATA_REPOSITORY_BACKEND
from agent.repository.base import FraudDataRepository
from agent.repository.local import LocalFraudRepository
from agent.repository.tigergraph import TigerGraphFraudRepository

_repository_instance: Optional[FraudDataRepository] = None

def get_fraud_repository(backend: Optional[str] = None) -> FraudDataRepository:
    """
    Factory function providing a singleton FraudDataRepository instance.
    """
    global _repository_instance
    if _repository_instance is None:
        chosen_backend = (backend or DATA_REPOSITORY_BACKEND).lower()
        if chosen_backend == "tigergraph":
            _repository_instance = TigerGraphFraudRepository()
        else:
            _repository_instance = LocalFraudRepository()
    return _repository_instance

def reset_fraud_repository():
    global _repository_instance
    _repository_instance = None
