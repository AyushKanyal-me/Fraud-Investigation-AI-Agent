import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.validator import validate_case_invariants

class CaseValidator:
    """Wrapper around agent.validator.validate_case_invariants for backward compatibility."""
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_case(self, data: Dict[str, Any], case_id_expected: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
        is_valid, errors, warnings = validate_case_invariants(data, case_id_expected=case_id_expected)
        self.errors = errors
        self.warnings = warnings
        return is_valid, errors, warnings

if __name__ == "__main__":
    v = CaseValidator()
    print("[+] CaseValidator loaded and backed by agent.validator.")
