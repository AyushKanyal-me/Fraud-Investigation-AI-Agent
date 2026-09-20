import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import MEMORY_FILE

class CaseMemory:
    def __init__(self, memory_file: Path = MEMORY_FILE):
        self.memory_file = memory_file
        self.cases: Dict[str, Dict[str, Any]] = {}
        self.compromised_cards: Dict[str, str] = {}  # card_id -> case_id
        self.suspicious_devices: Dict[str, List[str]] = {}  # device_id -> list of case_ids
        self.suspicious_emails: Dict[str, List[str]] = {}  # email -> list of case_ids
        self.load()

    def load(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r") as f:
                    data = json.load(f)
                    self.cases = data.get("cases", {})
                    self.compromised_cards = data.get("compromised_cards", {})
                    self.suspicious_devices = data.get("suspicious_devices", {})
                    self.suspicious_emails = data.get("suspicious_emails", {})
            except Exception as e:
                print(f"[!] Error loading memory: {e}")

    def save(self):
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cases": self.cases,
            "compromised_cards": self.compromised_cards,
            "suspicious_devices": self.suspicious_devices,
            "suspicious_emails": self.suspicious_emails
        }
        with open(self.memory_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_case(self, case_id: str, case_data: Dict[str, Any]):
        """Records a newly investigated case into active working memory."""
        self.cases[case_id] = case_data
        case_info = case_data.get("case", {})
        verdict = case_info.get("verdict")
        
        if verdict == "fraud":
            # Record compromised cards
            connected_cards = case_info.get("connected_card_ids", [])
            for cid in connected_cards:
                self.compromised_cards[cid] = case_id

            # Record suspicious device profiles
            devices = case_info.get("connected_device_profiles", [])
            for dev in devices:
                if dev not in self.suspicious_devices:
                    self.suspicious_devices[dev] = []
                if case_id not in self.suspicious_devices[dev]:
                    self.suspicious_devices[dev].append(case_id)

        self.save()

    def check_entity_history(self, card_id: Optional[str] = None, device_info: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """Queries memory to see if any entity was involved in prior investigated cases."""
        hits = {
            "card_prior_fraud": None,
            "device_prior_cases": [],
            "email_prior_cases": []
        }
        if card_id and card_id in self.compromised_cards:
            hits["card_prior_fraud"] = self.compromised_cards[card_id]
        if device_info and device_info in self.suspicious_devices:
            hits["device_prior_cases"] = self.suspicious_devices[device_info]
        if email and email in self.suspicious_emails:
            hits["email_prior_cases"] = self.suspicious_emails[email]
        return hits
