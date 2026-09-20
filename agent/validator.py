import re
from typing import Dict, Any, List, Tuple, Optional
from agent.policy import (
    CaseStatus,
    CaseVerdict,
    FraudPattern,
    ActionType,
    ApprovalRoute,
    get_action_route,
)

class CaseValidationError(Exception):
    """Raised when a case output violates bank fraud policy invariants or schema requirements."""
    pass

def validate_case_invariants(case_output: Dict[str, Any], case_id_expected: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
    """
    Validates a case JSON output against all schema and policy invariant rules defined in Dataset/README.md.
    
    Returns:
        (is_valid: bool, errors: List[str], warnings: List[str])
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Top-Level Required Fields
    required_top_fields = [
        "case_id", "case", "evidence_requests", "next_best_actions",
        "sar", "stop_reason", "tool_calls", "tokens", "latency_s"
    ]
    for f in required_top_fields:
        if f not in case_output:
            errors.append(f"Missing required top-level field: '{f}'")

    if errors:
        return False, errors, warnings

    # Case ID check
    case_id = case_output.get("case_id", "")
    if case_id_expected and case_id != case_id_expected:
        errors.append(f"Case ID mismatch: expected '{case_id_expected}', got '{case_id}'")

    # Metric type checks
    if not isinstance(case_output.get("tool_calls"), int) or case_output["tool_calls"] < 0:
        errors.append("Field 'tool_calls' must be a non-negative integer")
    if not isinstance(case_output.get("tokens"), int) or case_output["tokens"] < 0:
        errors.append("Field 'tokens' must be a non-negative integer")
    if not isinstance(case_output.get("latency_s"), (int, float)) or case_output["latency_s"] < 0:
        errors.append("Field 'latency_s' must be a non-negative number")

    # Stop Reason
    stop_reason = case_output.get("stop_reason", "")
    if not isinstance(stop_reason, str) or not stop_reason.strip():
        errors.append("Field 'stop_reason' must be a non-empty string explaining why the investigation stopped")

    # Evidence Requests
    ev_reqs = case_output.get("evidence_requests", [])
    if not isinstance(ev_reqs, list):
        errors.append("Field 'evidence_requests' must be a list")
    else:
        for idx, req in enumerate(ev_reqs):
            if not isinstance(req, dict):
                errors.append(f"evidence_requests[{idx}] must be an object")
                continue
            for req_key in ["type", "asked_after_step", "assumed_response"]:
                if req_key not in req:
                    errors.append(f"evidence_requests[{idx}] missing '{req_key}'")

    # 2. Part 1: Case Record
    case_data = case_output.get("case", {})
    if not isinstance(case_data, dict):
        errors.append("Field 'case' must be an object")
        return False, errors, warnings

    case_req_fields = [
        "status", "verdict", "fraud_probability", "pattern", "pattern_description",
        "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
        "connected_device_profiles", "exposure_usd", "evidence", "similar_prior_cases",
        "summary", "written_to_graph", "graph_case_id"
    ]
    for f in case_req_fields:
        if f not in case_data:
            errors.append(f"Missing required field in 'case': '{f}'")

    # Status & Verdict
    valid_statuses = [s.value for s in CaseStatus]
    valid_verdicts = [v.value for v in CaseVerdict]
    valid_patterns = [p.value for p in FraudPattern]

    status = case_data.get("status")
    verdict = case_data.get("verdict")
    pattern = case_data.get("pattern")
    fraud_prob = case_data.get("fraud_probability")
    exposure_usd = case_data.get("exposure_usd", 0.0)
    affected_txns = case_data.get("affected_txn_ids", [])

    if status not in valid_statuses:
        errors.append(f"Invalid status '{status}'. Must be one of {valid_statuses}")
    if verdict not in valid_verdicts:
        errors.append(f"Invalid verdict '{verdict}'. Must be one of {valid_verdicts}")
    if pattern not in valid_patterns:
        errors.append(f"Invalid pattern '{pattern}'. Must be one of {valid_patterns}")

    if not isinstance(fraud_prob, (int, float)) or not (0.0 <= fraud_prob <= 1.0):
        errors.append(f"Field 'fraud_probability' must be a float between 0.0 and 1.0, got {fraud_prob}")

    if pattern == FraudPattern.UNDOCUMENTED.value:
        pattern_desc = case_data.get("pattern_description", "")
        if not isinstance(pattern_desc, str) or not pattern_desc.strip():
            errors.append("Field 'pattern_description' is mandatory when pattern is 'undocumented'")

    # Invariants for Legitimate Verdicts
    if verdict == CaseVerdict.LEGITIMATE.value:
        if len(affected_txns) > 0:
            errors.append(f"Policy Invariant Violation: For verdict 'legitimate', affected_txn_ids must be empty, found {len(affected_txns)}")
        if exposure_usd != 0.0:
            errors.append(f"Policy Invariant Violation: For verdict 'legitimate', exposure_usd must be 0, got {exposure_usd}")

    # Evidence list validation
    evidence_list = case_data.get("evidence", [])
    if not isinstance(evidence_list, list):
        errors.append("Field 'case.evidence' must be a list")
    else:
        for idx, ev in enumerate(evidence_list):
            if not isinstance(ev, dict):
                errors.append(f"case.evidence[{idx}] must be an object")
                continue
            for ev_k in ["claim", "source", "ref", "entity_ids"]:
                if ev_k not in ev:
                    errors.append(f"case.evidence[{idx}] missing '{ev_k}'")
            if not isinstance(ev.get("entity_ids", []), list):
                errors.append(f"case.evidence[{idx}].entity_ids must be a list")

    # 3. Part 2: SAR Invariants
    sar_data = case_output.get("sar", {})
    if not isinstance(sar_data, dict):
        errors.append("Field 'sar' must be an object")
    else:
        sar_req_fields = ["file", "reason", "narrative", "subjects", "total_amount_usd", "activity_dates"]
        for f in sar_req_fields:
            if f not in sar_data:
                errors.append(f"Missing required field in 'sar': '{f}'")

        sar_file = sar_data.get("file")
        if not isinstance(sar_file, bool):
            errors.append("Field 'sar.file' must be a boolean")
        elif sar_file is False:
            if sar_data.get("narrative") != "":
                errors.append("Policy Invariant: When 'sar.file' is false, 'sar.narrative' must be empty string ''")
            if sar_data.get("subjects") != []:
                errors.append("Policy Invariant: When 'sar.file' is false, 'sar.subjects' must be empty list []")
            if sar_data.get("total_amount_usd") != 0 and sar_data.get("total_amount_usd") != 0.0:
                errors.append("Policy Invariant: When 'sar.file' is false, 'sar.total_amount_usd' must be 0")
            if sar_data.get("activity_dates") != []:
                errors.append("Policy Invariant: When 'sar.file' is false, 'sar.activity_dates' must be empty list []")
        else:
            # sar_file is True
            if not sar_data.get("narrative", "").strip():
                errors.append("Policy Invariant: When 'sar.file' is true, 'sar.narrative' is required and must not be empty")
            if not sar_data.get("subjects") or len(sar_data.get("subjects", [])) == 0:
                errors.append("Policy Invariant: When 'sar.file' is true, 'sar.subjects' must contain relevant entity IDs")
            if sar_data.get("total_amount_usd", 0.0) <= 0.0:
                errors.append("Policy Invariant: When 'sar.file' is true, 'sar.total_amount_usd' must be greater than 0")
            activity_dates = sar_data.get("activity_dates", [])
            if not isinstance(activity_dates, list) or len(activity_dates) != 2:
                errors.append("Policy Invariant: When 'sar.file' is true, 'sar.activity_dates' must be a list of two 'YYYY-MM-DD' dates")
            else:
                date_regex = re.compile(r"^\d{4}-\d{2}-\d{2}$")
                for d in activity_dates:
                    if not isinstance(d, str) or not date_regex.match(d):
                        errors.append(f"Date '{d}' in 'sar.activity_dates' does not match format 'YYYY-MM-DD'")

    # 4. Part 3: Next Best Actions Invariants
    nba_data = case_output.get("next_best_actions", {})
    if not isinstance(nba_data, dict):
        errors.append("Field 'next_best_actions' must be an object")
    else:
        for f in ["initial", "final", "what_changed"]:
            if f not in nba_data:
                errors.append(f"Missing required field in 'next_best_actions': '{f}'")

        initial_actions = nba_data.get("initial", [])
        final_actions = nba_data.get("final", [])

        if not isinstance(initial_actions, list) or len(initial_actions) == 0:
            errors.append("Field 'next_best_actions.initial' must be a non-empty list")
        if not isinstance(final_actions, list) or len(final_actions) == 0:
            errors.append("Field 'next_best_actions.final' must be a non-empty list")

        # Validate action objects and routes
        valid_actions = [a.value for a in ActionType]
        valid_routes = [r.value for r in ApprovalRoute]

        for stage_name, actions in [("initial", initial_actions), ("final", final_actions)]:
            for a_idx, act in enumerate(actions):
                if not isinstance(act, dict):
                    errors.append(f"next_best_actions.{stage_name}[{a_idx}] must be an object")
                    continue
                for ak in ["action", "route", "reason"]:
                    if ak not in act:
                        errors.append(f"next_best_actions.{stage_name}[{a_idx}] missing '{ak}'")
                
                a_name = act.get("action")
                a_route = act.get("route")
                if a_name not in valid_actions:
                    errors.append(f"Invalid action '{a_name}' in next_best_actions.{stage_name}[{a_idx}]. Must be one of {valid_actions}")
                if a_route not in valid_routes:
                    errors.append(f"Invalid route '{a_route}' in next_best_actions.{stage_name}[{a_idx}]. Must be one of {valid_routes}")
                
                # Check approval route correctness against policy
                if a_name in valid_actions:
                    expected_route = get_action_route(a_name, exposure_usd)
                    if a_route != expected_route:
                        errors.append(
                            f"Approval route mismatch for action '{a_name}' in {stage_name}: expected '{expected_route}', got '{a_route}'"
                        )

        # SAR Consistency Invariant
        final_action_names = [a.get("action") for a in final_actions if isinstance(a, dict)]
        has_file_report_action = ActionType.FILE_REPORT.value in final_action_names
        sar_file_flag = sar_data.get("file", False) if isinstance(sar_data, dict) else False

        if sar_file_flag != has_file_report_action:
            errors.append(
                f"Policy Invariant Violation: 'sar.file' ({sar_file_flag}) must agree with presence of '{ActionType.FILE_REPORT.value}' in next_best_actions.final ({has_file_report_action})"
            )

    is_valid = (len(errors) == 0)
    return is_valid, errors, warnings
