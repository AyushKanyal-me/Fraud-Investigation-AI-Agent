import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import PATTERNS, ACTION_TYPES, APPROVAL_ROUTES

class CaseValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_case(self, data: Dict[str, Any], case_id_expected: str = None) -> Tuple[bool, List[str], List[str]]:
        errors = []
        warnings = []

        # 1. Top Level Fields
        req_top_keys = ["case_id", "case", "evidence_requests", "next_best_actions", "sar", "stop_reason", "tool_calls", "tokens", "latency_s"]
        for k in req_top_keys:
            if k not in data:
                errors.append(f"Missing top-level key: '{k}'")

        if case_id_expected and data.get("case_id") != case_id_expected:
            errors.append(f"case_id mismatch: expected '{case_id_expected}', got '{data.get('case_id')}'")

        # 2. Part 1: case
        c = data.get("case", {})
        req_case_keys = [
            "status", "verdict", "fraud_probability", "pattern", "pattern_description",
            "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
            "connected_device_profiles", "exposure_usd", "evidence", "similar_prior_cases",
            "summary", "written_to_graph", "graph_case_id"
        ]
        for k in req_case_keys:
            if k not in c:
                errors.append(f"Missing case key: 'case.{k}'")

        verdict = c.get("verdict")
        if verdict not in ["fraud", "legitimate", "uncertain"]:
            errors.append(f"Invalid verdict: '{verdict}'")

        pattern = c.get("pattern")
        if pattern not in PATTERNS:
            errors.append(f"Invalid pattern: '{pattern}'. Must be one of {PATTERNS}")

        if pattern == "undocumented" and not c.get("pattern_description"):
            errors.append("pattern is 'undocumented' but pattern_description is empty")

        prob = c.get("fraud_probability", -1)
        if not (0.0 <= prob <= 1.0):
            errors.append(f"fraud_probability out of bounds [0, 1]: {prob}")

        # Strict Semantic Checks: Legitimate vs Fraud
        nba = data.get("next_best_actions", {})
        final_actions = nba.get("final", [])
        final_action_names = [a.get("action") for a in final_actions]

        if verdict == "legitimate":
            if c.get("affected_txn_ids") != []:
                errors.append(f"Policy Breach: Verdict is legitimate but affected_txn_ids is not empty: {c.get('affected_txn_ids')}")
            if c.get("exposure_usd") != 0.0:
                errors.append(f"Policy Breach: Verdict is legitimate but exposure_usd is not 0: {c.get('exposure_usd')}")
            if "BLOCK_CARD" in final_action_names or "BLOCK_ALL_CARDS" in final_action_names:
                errors.append("Policy Breach: Legitimate case cannot recommend BLOCK_CARD or BLOCK_ALL_CARDS")
            if "FILE_REPORT" in final_action_names:
                errors.append("Policy Breach: Legitimate case cannot recommend FILE_REPORT")
            if "CLOSE_NO_FRAUD" not in final_action_names:
                errors.append("Policy Requirement: Legitimate case final actions must include CLOSE_NO_FRAUD")

        if verdict == "fraud":
            if not c.get("affected_txn_ids"):
                errors.append("Fraud verdict requires non-empty affected_txn_ids")
            if c.get("exposure_usd", 0.0) <= 0.0:
                errors.append("Fraud verdict requires exposure_usd > 0")
            if "ALLOW_TRANSACTION" in final_action_names:
                errors.append("Policy Contradiction: Confirmed fraud verdict cannot include ALLOW_TRANSACTION in final actions")
            if "CLOSE_NO_FRAUD" in final_action_names:
                errors.append("Policy Contradiction: Confirmed fraud verdict cannot include CLOSE_NO_FRAUD in final actions")
            if "BLOCK_CARD" not in final_action_names:
                errors.append("Policy Requirement: Confirmed fraud final actions must include BLOCK_CARD")
            if "CREATE_CASE" not in final_action_names:
                errors.append("Policy Requirement: Confirmed fraud final actions must include CREATE_CASE")

        # Check evidence objects
        for idx, ev in enumerate(c.get("evidence", [])):
            for ek in ["claim", "source", "ref", "entity_ids"]:
                if ek not in ev:
                    errors.append(f"Evidence item #{idx} missing '{ek}'")
            if ev.get("source") not in ["graph", "document", "customer", "external"]:
                errors.append(f"Evidence item #{idx} invalid source: '{ev.get('source')}'")

        # 3. Part 2: SAR
        sar = data.get("sar", {})
        req_sar_keys = ["file", "reason", "narrative", "subjects", "total_amount_usd", "activity_dates"]
        for k in req_sar_keys:
            if k not in sar:
                errors.append(f"Missing sar key: 'sar.{k}'")

        sar_file = sar.get("file")
        if sar_file is False:
            if sar.get("narrative") != "":
                warnings.append("sar.file is false but sar.narrative is not empty")
            if sar.get("subjects") != []:
                warnings.append("sar.file is false but sar.subjects is not empty")
            if sar.get("total_amount_usd") != 0.0:
                warnings.append("sar.file is false but sar.total_amount_usd is not 0")
            if sar.get("activity_dates") != []:
                warnings.append("sar.file is false but sar.activity_dates is not empty")
        elif sar_file is True:
            if not sar.get("narrative") or len(sar.get("narrative", "").split(".")) < 4:
                errors.append("sar.file is true but narrative is missing or insufficiently detailed (< 4 sentences)")
            if not sar.get("subjects"):
                errors.append("sar.file is true but subjects list is empty")
            if len(sar.get("activity_dates", [])) != 2:
                errors.append("sar.activity_dates should contain [first_date, last_date]")

        # Consistency: FILE_REPORT in final actions <=> sar.file is true
        has_file_report = "FILE_REPORT" in final_action_names
        if has_file_report != sar_file:
            errors.append(f"Contradiction: 'FILE_REPORT' in final actions is {has_file_report} but sar.file is {sar_file}")

        # 4. Part 3: next_best_actions
        for nk in ["initial", "final", "what_changed"]:
            if nk not in nba:
                errors.append(f"Missing next_best_actions key: 'next_best_actions.{nk}'")

        for stage_name in ["initial", "final"]:
            actions_list = nba.get(stage_name, [])
            for a_idx, act in enumerate(actions_list):
                for ak in ["action", "route", "reason"]:
                    if ak not in act:
                        errors.append(f"{stage_name} action #{a_idx} missing '{ak}'")
                a_type = act.get("action")
                if a_type not in ACTION_TYPES:
                    errors.append(f"Invalid action '{a_type}' in {stage_name} actions")
                route = act.get("route")
                if route not in APPROVAL_ROUTES:
                    errors.append(f"Invalid route '{route}' in {stage_name} action '{a_type}'")

                # Approval route checks
                exp = c.get("exposure_usd", 0.0)
                if a_type == "BLOCK_CARD":
                    expected_route = "L2" if exp > 2500.0 else "L1"
                    if route != expected_route:
                        errors.append(f"Route Mismatch: BLOCK_CARD with exposure ${exp:.2f} must route to '{expected_route}', got '{route}'")
                if a_type in ["BLOCK_ALL_CARDS", "FILE_REPORT"]:
                    if route != "L2":
                        errors.append(f"Route Mismatch: {a_type} must always route to 'L2', got '{route}'")
                if a_type in ["ALLOW_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH", "CLOSE_NO_FRAUD", "CREATE_CASE", "ESCALATE_TO_ANALYST"]:
                    if route != "auto":
                        errors.append(f"Route Mismatch: {a_type} must route to 'auto', got '{route}'")

        # 5. Graph write check
        if c.get("written_to_graph") is True and not c.get("graph_case_id"):
            errors.append("written_to_graph is true but graph_case_id is empty")

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

if __name__ == "__main__":
    v = CaseValidator()
    print("[+] Deep Semantic Validator loaded.")
