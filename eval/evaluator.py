"""
Case Evaluator for Fraud Investigation AI Agent.
Evaluates agent output artifacts against ground truth benchmarks and policy specifications.
"""

import os
import json
import glob
from datetime import datetime
from typing import List, Dict, Optional, Any, Union

from eval.schemas import (
    GroundTruthCase,
    CaseEvaluationResult,
    EvalMetricsReport,
    DimensionScores,
    CompositeScore,
)
from eval.ground_truth_builder import load_ground_truth, DEFAULT_GROUND_TRUTH_PATH
from eval.metrics import MetricsEngine
from agent.validator import validate_case_invariants
from agent.policy import get_action_route

SAR_MANDATORY_EXPOSURE_THRESHOLD = 1000.0


class CaseEvaluator:
    """Evaluates individual case decisions and aggregates benchmark metrics."""

    def __init__(self, ground_truth_path: str = DEFAULT_GROUND_TRUTH_PATH):
        self.ground_truth = load_ground_truth(ground_truth_path)

    def evaluate_case(
        self,
        case_data: Dict[str, Any],
        gt: Optional[GroundTruthCase] = None,
    ) -> CaseEvaluationResult:
        """Evaluates a single investigation output dictionary against ground truth."""
        case_id = case_data.get("case_id", "")
        if gt is None:
            if case_id not in self.ground_truth:
                raise ValueError(f"Ground truth not found for case: {case_id}")
            gt = self.ground_truth[case_id]

        c_info = case_data.get("case", {})
        predicted_verdict = str(c_info.get("verdict", "")).lower()
        expected_verdict = gt.expected_verdict.lower()
        verdict_correct = predicted_verdict == expected_verdict

        predicted_pattern = str(c_info.get("pattern", "")).lower()
        expected_pattern = gt.expected_pattern.lower()
        pattern_correct = MetricsEngine.is_pattern_aligned(predicted_pattern, expected_pattern)

        # Final actions extraction
        raw_final = case_data.get("next_best_actions", {}).get("final", [])
        predicted_actions = [a.get("action", "") for a in raw_final if isinstance(a, dict)]
        expected_actions = gt.expected_actions

        action_jaccard = MetricsEngine.calculate_jaccard_similarity(
            set(predicted_actions), set(expected_actions)
        )
        critical_hits = all(crit in predicted_actions for crit in gt.critical_actions)

        # SAR evaluation
        sar_info = case_data.get("sar", {})
        predicted_sar = bool(sar_info.get("file", False))
        expected_sar = gt.expected_sar_required
        sar_decision_correct = predicted_sar == expected_sar

        # SAR policy compliance check (e.g., exposure >= threshold mandates SAR)
        pred_exp = float(c_info.get("exposure_usd", 0.0))
        sar_policy_compliant = True
        if pred_exp >= SAR_MANDATORY_EXPOSURE_THRESHOLD and not predicted_sar and predicted_verdict == "fraud":
            sar_policy_compliant = False
        if predicted_sar and (not sar_info.get("narrative") or len(str(sar_info.get("narrative", "")).strip()) < 10):
            sar_narrative_valid = False
        else:
            sar_narrative_valid = True

        # Exposure error calculation
        if expected_verdict == "fraud":
            mid_expected = (gt.expected_min_exposure + gt.expected_max_exposure) / 2.0
            exposure_abs_err = abs(pred_exp - mid_expected)
            if mid_expected > 0:
                exposure_rel_err = exposure_abs_err / mid_expected
            else:
                exposure_rel_err = 0.0 if pred_exp == 0 else 1.0
        else:
            exposure_abs_err = abs(pred_exp - 0.0)
            exposure_rel_err = 0.0 if pred_exp == 0 else 1.0

        # Structural & Policy validation
        try:
            is_valid, errors, warnings = validate_case_invariants(case_data, case_id_expected=case_id)
            schema_valid = is_valid
            approval_routes_valid = True
            # Validate approval routes in actions
            for a in raw_final:
                act = a.get("action")
                route = a.get("route")
                if act:
                    expected_route = get_action_route(act, pred_exp)
                    if route != expected_route:
                        approval_routes_valid = False
            policy_compliant = schema_valid and approval_routes_valid and len(errors) == 0
        except Exception:
            schema_valid = False
            approval_routes_valid = False
            policy_compliant = False

        # Compute overall case score (0.0 to 1.0)
        case_score = (
            (0.30 if verdict_correct else 0.0)
            + (0.15 if pattern_correct else 0.0)
            + (0.20 * action_jaccard)
            + (0.15 if (sar_decision_correct and sar_policy_compliant) else 0.0)
            + (0.10 * max(0.0, 1.0 - min(1.0, exposure_rel_err)))
            + (0.10 if policy_compliant else 0.0)
        )

        return CaseEvaluationResult(
            case_id=case_id,
            verdict_correct=verdict_correct,
            predicted_verdict=predicted_verdict,
            expected_verdict=expected_verdict,
            pattern_correct=pattern_correct,
            predicted_pattern=predicted_pattern,
            expected_pattern=expected_pattern,
            action_jaccard=round(action_jaccard, 4),
            critical_actions_hit=critical_hits,
            predicted_actions=predicted_actions,
            expected_actions=expected_actions,
            sar_decision_correct=sar_decision_correct,
            predicted_sar=predicted_sar,
            expected_sar=expected_sar,
            sar_policy_compliant=sar_policy_compliant,
            sar_narrative_valid=sar_narrative_valid,
            exposure_predicted=pred_exp,
            exposure_expected_range=[gt.expected_min_exposure, gt.expected_max_exposure],
            exposure_absolute_error=round(exposure_abs_err, 2),
            exposure_relative_error=round(exposure_rel_err, 4),
            policy_compliant=policy_compliant,
            approval_routes_valid=approval_routes_valid,
            schema_valid=schema_valid,
            overall_case_score=round(case_score, 4),
        )

    def evaluate_answers_directory(
        self,
        answers_dir: str = "answers",
        determinism_rate: float = 100.0,
    ) -> EvalMetricsReport:
        """Evaluates all answer JSON files in the specified directory."""
        files = sorted(glob.glob(os.path.join(answers_dir, "HHG-*.json")))
        if not files:
            raise FileNotFoundError(f"No answer JSON files found in {answers_dir}")

        case_results: List[CaseEvaluationResult] = []
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            res = self.evaluate_case(data)
            case_results.append(res)

        return self._generate_report(case_results, determinism_rate=determinism_rate)

    def _generate_report(
        self,
        case_results: List[CaseEvaluationResult],
        determinism_rate: float = 100.0,
    ) -> EvalMetricsReport:
        """Assembles the aggregate report from individual case results."""
        total = len(case_results)
        cm = MetricsEngine.compute_confusion_matrix(case_results)
        pattern_matches = sum(1 for r in case_results if r.pattern_correct)
        pattern_match_rate = round(pattern_matches / total, 4) if total > 0 else 0.0

        mean_jaccard = sum(r.action_jaccard for r in case_results) / total if total > 0 else 0.0
        crit_hits = sum(1 for r in case_results if r.critical_actions_hit)
        critical_action_recall = round(crit_hits / total, 4) if total > 0 else 0.0

        sar_decisions = sum(1 for r in case_results if r.sar_decision_correct)
        sar_accuracy = round(sar_decisions / total, 4) if total > 0 else 0.0

        sar_policies = sum(1 for r in case_results if r.sar_policy_compliant and r.sar_narrative_valid)
        sar_policy_rate = round(sar_policies / total, 4) if total > 0 else 0.0

        # Exposure metrics
        exposure_mae = round(sum(r.exposure_absolute_error for r in case_results) / total, 2) if total > 0 else 0.0
        fraud_cases = [r for r in case_results if r.expected_verdict == "fraud"]
        if fraud_cases:
            exposure_mre = round(sum(r.exposure_relative_error for r in fraud_cases) / len(fraud_cases), 4)
        else:
            exposure_mre = 0.0

        policy_hits = sum(1 for r in case_results if r.policy_compliant and r.approval_routes_valid and r.schema_valid)
        policy_rate = round(policy_hits / total, 4) if total > 0 else 0.0

        dim_scores = MetricsEngine.compute_dimension_scores(case_results, determinism_rate=determinism_rate)
        composite = MetricsEngine.compute_composite_score(dim_scores)

        return EvalMetricsReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_cases=total,
            confusion_matrix=cm,
            pattern_match_rate=pattern_match_rate,
            mean_action_jaccard=round(mean_jaccard, 4),
            critical_action_recall=critical_action_recall,
            sar_filing_accuracy=sar_accuracy,
            sar_policy_adherence_rate=sar_policy_rate,
            exposure_mae=exposure_mae,
            exposure_mean_relative_error=exposure_mre,
            policy_compliance_rate=policy_rate,
            determinism_rate=determinism_rate,
            dimension_scores=dim_scores,
            composite_score=composite,
            case_results=case_results,
        )
