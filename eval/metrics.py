"""
Metrics Engine for Fraud Investigation AI Agent.
Implements multi-dimensional evaluation calculations across the 7 dimensions.
"""

from typing import List, Dict, Tuple, Set, Optional
import math
from eval.schemas import (
    ConfusionMatrix,
    CaseEvaluationResult,
    DimensionScores,
    CompositeScore,
)


class MetricsEngine:
    """Computes rigorous quantitative metrics across all investigation dimensions."""

    @staticmethod
    def calculate_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Calculates Jaccard similarity index between two string sets."""
        if not set_a and not set_b:
            return 1.0
        union = set_a.union(set_b)
        if not union:
            return 1.0
        intersection = set_a.intersection(set_b)
        return len(intersection) / len(union)

    @staticmethod
    def compute_confusion_matrix(case_results: List[CaseEvaluationResult]) -> ConfusionMatrix:
        """
        Computes standard binary classification metrics.
        Positive class: 'fraud', Negative class: 'legitimate'.
        """
        tp = 0
        fp = 0
        fn = 0
        tn = 0

        for r in case_results:
            pred = r.predicted_verdict.lower()
            actual = r.expected_verdict.lower()

            if actual == "fraud":
                if pred == "fraud":
                    tp += 1
                else:
                    fn += 1
            else:  # legitimate
                if pred == "fraud":
                    fp += 1
                else:
                    tn += 1

        total = tp + fp + fn + tn
        accuracy = (tp + tn) / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 1.0

        return ConfusionMatrix(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            specificity=round(specificity, 4),
        )

    @staticmethod
    def is_pattern_aligned(predicted: str, expected: str) -> bool:
        """
        Checks if the predicted pattern matches or is taxonomically compatible
        with the expected pattern.
        """
        pred = predicted.strip().lower()
        exp = expected.strip().lower()

        if pred == exp:
            return True

        # Compatible subtype pairings
        compatible_pairs = [
            ("card_not_present_fraud", "card_not_present_new_device"),
            ("card_not_present_new_device", "card_not_present_fraud"),
            ("account_takeover", "card_not_present_new_device"),
            ("card_not_present_new_device", "account_takeover"),
        ]
        return (pred, exp) in compatible_pairs

    @staticmethod
    def compute_dimension_scores(
        case_results: List[CaseEvaluationResult],
        determinism_rate: float = 100.0,
    ) -> DimensionScores:
        """Aggregates all 7 dimension scores on a 0-100 scale."""
        if not case_results:
            return DimensionScores()

        total = len(case_results)

        # 1. Verdict Accuracy Score (0-100)
        cm = MetricsEngine.compute_confusion_matrix(case_results)
        verdict_score = round(cm.f1_score * 100.0, 2)

        # 2. Pattern Identification Score (0-100)
        pattern_matches = sum(1 for r in case_results if r.pattern_correct)
        pattern_score = round((pattern_matches / total) * 100.0, 2)

        # 3. Action Alignment Score (0-100)
        # Weighted combination of mean Jaccard (50%) and Critical Action Recall (50%)
        mean_jaccard = sum(r.action_jaccard for r in case_results) / total
        crit_hits = sum(1 for r in case_results if r.critical_actions_hit)
        crit_recall = crit_hits / total
        action_score = round((0.5 * mean_jaccard + 0.5 * crit_recall) * 100.0, 2)

        # 4. SAR Compliance Score (0-100)
        sar_decisions = sum(1 for r in case_results if r.sar_decision_correct)
        sar_policy = sum(1 for r in case_results if r.sar_policy_compliant)
        sar_narrative = sum(1 for r in case_results if r.sar_narrative_valid)
        sar_score = round(
            (0.4 * (sar_decisions / total) + 0.4 * (sar_policy / total) + 0.2 * (sar_narrative / total)) * 100.0,
            2,
        )

        # 5. Exposure Accuracy Score (0-100)
        # Bounded score based on mean relative error %
        valid_rel_errors = [r.exposure_relative_error for r in case_results if r.expected_verdict == "fraud"]
        if valid_rel_errors:
            avg_rel_err = sum(valid_rel_errors) / len(valid_rel_errors)
            # 0% error -> 100 score; 50% error -> 0 score
            exp_score = max(0.0, min(100.0, (1.0 - (avg_rel_err / 0.50)) * 100.0))
        else:
            exp_score = 100.0
        exposure_score = round(exp_score, 2)

        # 6. Policy Compliance Score (0-100)
        policy_hits = sum(1 for r in case_results if r.policy_compliant and r.approval_routes_valid and r.schema_valid)
        policy_score = round((policy_hits / total) * 100.0, 2)

        # 7. Determinism Score (0-100)
        determinism_score = round(determinism_rate, 2)

        return DimensionScores(
            verdict_accuracy_score=verdict_score,
            pattern_identification_score=pattern_score,
            action_alignment_score=action_score,
            sar_compliance_score=sar_score,
            exposure_accuracy_score=exposure_score,
            policy_compliance_score=policy_score,
            determinism_score=determinism_score,
        )

    @staticmethod
    def compute_composite_score(
        dimension_scores: DimensionScores,
        passing_threshold: float = 85.0,
    ) -> CompositeScore:
        """Calculates final weighted composite score and pass/fail status."""
        weights = {
            "verdict_accuracy": 0.25,
            "pattern_identification": 0.15,
            "action_alignment": 0.20,
            "sar_compliance": 0.15,
            "exposure_accuracy": 0.10,
            "policy_compliance": 0.10,
            "determinism": 0.05,
        }

        weighted_total = (
            dimension_scores.verdict_accuracy_score * weights["verdict_accuracy"]
            + dimension_scores.pattern_identification_score * weights["pattern_identification"]
            + dimension_scores.action_alignment_score * weights["action_alignment"]
            + dimension_scores.sar_compliance_score * weights["sar_compliance"]
            + dimension_scores.exposure_accuracy_score * weights["exposure_accuracy"]
            + dimension_scores.policy_compliance_score * weights["policy_compliance"]
            + dimension_scores.determinism_score * weights["determinism"]
        )

        total_score = round(weighted_total, 2)
        is_passing = total_score >= passing_threshold

        return CompositeScore(
            total_score=total_score,
            is_passing=is_passing,
            passing_threshold=passing_threshold,
            dimension_breakdown=dimension_scores,
            weights=weights,
        )
