"""
Ground Truth Builder and Loader for the Fraud Investigation AI Agent evaluation suite.
Constructs and validates the benchmark reference dataset for the 20 HHG evaluation cases.
"""

import os
import csv
from typing import List, Dict, Optional
from eval.schemas import GroundTruthCase

DEFAULT_GROUND_TRUTH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Dataset",
    "ground_truth.csv",
)

# Reference definitions for 20 benchmark cases
REFERENCE_GROUND_TRUTH = [
    {
        "case_id": "HHG-001",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 70.0,
        "expected_max_exposure": 85.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Out-of-region card use confirmed unauthorized by cardholder.",
    },
    {
        "case_id": "HHG-002",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 280.0,
        "expected_max_exposure": 305.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "High risk CNP transaction confirmed fraudulent.",
    },
    {
        "case_id": "HHG-003",
        "expected_verdict": "legitimate",
        "expected_pattern": "none",
        "expected_actions": ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"],
        "expected_sar_required": False,
        "expected_min_exposure": 0.0,
        "expected_max_exposure": 0.0,
        "critical_actions": ["CLOSE_NO_FRAUD"],
        "source_notes": "Cardholder verified transaction was authorized upon follow-up.",
    },
    {
        "case_id": "HHG-004",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 120.0,
        "expected_max_exposure": 140.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Customer dispute confirmed unauthorized online purchase.",
    },
    {
        "case_id": "HHG-005",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 95.0,
        "expected_max_exposure": 110.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Risk score alert confirmed unauthorized card use.",
    },
    {
        "case_id": "HHG-006",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 470.0,
        "expected_max_exposure": 495.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Customer dispute confirmed unauthorized transaction.",
    },
    {
        "case_id": "HHG-007",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 105.0,
        "expected_max_exposure": 120.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "High risk score transaction confirmed unauthorized.",
    },
    {
        "case_id": "HHG-008",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 50.0,
        "expected_max_exposure": 65.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Customer dispute confirmed out-of-region unauthorized use.",
    },
    {
        "case_id": "HHG-009",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 25.0,
        "expected_max_exposure": 35.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Customer dispute confirmed unauthorized out-of-region use.",
    },
    {
        "case_id": "HHG-010",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE", "FILE_REPORT"],
        "expected_sar_required": True,
        "expected_min_exposure": 990.0,
        "expected_max_exposure": 1050.0,
        "critical_actions": ["BLOCK_CARD", "FILE_REPORT"],
        "source_notes": "Exposure >= $1,000 mandates SAR filing under Policy R4.",
    },
    {
        "case_id": "HHG-011",
        "expected_verdict": "fraud",
        "expected_pattern": "card_testing",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"],
        "expected_sar_required": True,
        "expected_min_exposure": 180.0,
        "expected_max_exposure": 230.0,
        "critical_actions": ["BLOCK_CARD", "FILE_REPORT"],
        "source_notes": "Card testing attack across connected cards mandates SAR under Policy R4.",
    },
    {
        "case_id": "HHG-012",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 25.0,
        "expected_max_exposure": 35.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Out-of-region card use confirmed unauthorized.",
    },
    {
        "case_id": "HHG-013",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 30.0,
        "expected_max_exposure": 40.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Out-of-region card use confirmed unauthorized.",
    },
    {
        "case_id": "HHG-014",
        "expected_verdict": "fraud",
        "expected_pattern": "account_takeover",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"],
        "expected_sar_required": True,
        "expected_min_exposure": 65.0,
        "expected_max_exposure": 85.0,
        "critical_actions": ["BLOCK_CARD", "FILE_REPORT"],
        "source_notes": "Account takeover ring across shared device profile mandates SAR under Policy R4.",
    },
    {
        "case_id": "HHG-015",
        "expected_verdict": "fraud",
        "expected_pattern": "out_of_region_use",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 580.0,
        "expected_max_exposure": 620.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "High risk out-of-region transaction confirmed unauthorized.",
    },
    {
        "case_id": "HHG-016",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_new_device",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 50.0,
        "expected_max_exposure": 70.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "Customer dispute confirmed new device CNP unauthorized transaction.",
    },
    {
        "case_id": "HHG-017",
        "expected_verdict": "legitimate",
        "expected_pattern": "none",
        "expected_actions": ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"],
        "expected_sar_required": False,
        "expected_min_exposure": 0.0,
        "expected_max_exposure": 0.0,
        "critical_actions": ["CLOSE_NO_FRAUD"],
        "source_notes": "Cardholder confirmed transaction was legitimate travel.",
    },
    {
        "case_id": "HHG-018",
        "expected_verdict": "legitimate",
        "expected_pattern": "none",
        "expected_actions": ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"],
        "expected_sar_required": False,
        "expected_min_exposure": 0.0,
        "expected_max_exposure": 0.0,
        "critical_actions": ["CLOSE_NO_FRAUD"],
        "source_notes": "Cardholder verified recognized family member transaction.",
    },
    {
        "case_id": "HHG-019",
        "expected_verdict": "fraud",
        "expected_pattern": "card_not_present_fraud",
        "expected_actions": ["BLOCK_CARD", "CREATE_CASE"],
        "expected_sar_required": False,
        "expected_min_exposure": 90.0,
        "expected_max_exposure": 110.0,
        "critical_actions": ["BLOCK_CARD"],
        "source_notes": "High risk score CNP purchase confirmed fraudulent.",
    },
    {
        "case_id": "HHG-020",
        "expected_verdict": "legitimate",
        "expected_pattern": "none",
        "expected_actions": ["ALLOW_TRANSACTION", "CLOSE_NO_FRAUD"],
        "expected_sar_required": False,
        "expected_min_exposure": 0.0,
        "expected_max_exposure": 0.0,
        "critical_actions": ["CLOSE_NO_FRAUD"],
        "source_notes": "Cardholder confirmed legitimate purchase from new phone.",
    },
]


def write_ground_truth_csv(output_path: str = DEFAULT_GROUND_TRUTH_PATH) -> str:
    """Generates the ground_truth.csv reference file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "case_id",
        "expected_verdict",
        "expected_pattern",
        "expected_actions",
        "expected_sar_required",
        "expected_min_exposure",
        "expected_max_exposure",
        "critical_actions",
        "source_notes",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in REFERENCE_GROUND_TRUTH:
            row = item.copy()
            row["expected_actions"] = "|".join(row["expected_actions"])
            row["critical_actions"] = "|".join(row["critical_actions"])
            row["expected_sar_required"] = "True" if row["expected_sar_required"] else "False"
            writer.writerow(row)
    return output_path


def load_ground_truth(csv_path: str = DEFAULT_GROUND_TRUTH_PATH) -> Dict[str, GroundTruthCase]:
    """Loads ground truth records from CSV into a dictionary keyed by case_id."""
    if not os.path.exists(csv_path):
        write_ground_truth_csv(csv_path)

    cases: Dict[str, GroundTruthCase] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            actions = [a.strip() for a in row["expected_actions"].split("|") if a.strip()]
            crit_actions = [a.strip() for a in row["critical_actions"].split("|") if a.strip()]
            sar_req = row["expected_sar_required"].strip().lower() in ["true", "1", "yes"]
            gt = GroundTruthCase(
                case_id=row["case_id"].strip(),
                expected_verdict=row["expected_verdict"].strip().lower(),
                expected_pattern=row["expected_pattern"].strip().lower(),
                expected_actions=actions,
                expected_sar_required=sar_req,
                expected_min_exposure=float(row.get("expected_min_exposure", 0.0)),
                expected_max_exposure=float(row.get("expected_max_exposure", 0.0)),
                critical_actions=crit_actions,
                source_notes=row.get("source_notes"),
            )
            cases[gt.case_id] = gt
    return cases


if __name__ == "__main__":
    path = write_ground_truth_csv()
    print(f"Ground truth written to {path}")
