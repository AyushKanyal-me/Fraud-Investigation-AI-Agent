"""
Unit tests for the evaluation metrics engine and ground truth builder.
"""

import pytest
from eval.metrics import MetricsEngine
from eval.schemas import CaseEvaluationResult, DimensionScores, CompositeScore
from eval.ground_truth_builder import REFERENCE_GROUND_TRUTH, load_ground_truth


def test_jaccard_similarity():
    # Identical sets
    assert MetricsEngine.calculate_jaccard_similarity({"A", "B"}, {"A", "B"}) == 1.0
    # Empty sets
    assert MetricsEngine.calculate_jaccard_similarity(set(), set()) == 1.0
    # Disjoint sets
    assert MetricsEngine.calculate_jaccard_similarity({"A"}, {"B"}) == 0.0
    # Partial overlap
    assert MetricsEngine.calculate_jaccard_similarity({"A", "B"}, {"B", "C"}) == 1.0 / 3.0


def test_confusion_matrix_calculation():
    results = [
        # 2 TP
        CaseEvaluationResult(
            case_id="1", verdict_correct=True, predicted_verdict="fraud", expected_verdict="fraud",
            pattern_correct=True, predicted_pattern="out_of_region_use", expected_pattern="out_of_region_use",
            action_jaccard=1.0, critical_actions_hit=True, predicted_actions=["BLOCK_CARD"], expected_actions=["BLOCK_CARD"],
            sar_decision_correct=True, predicted_sar=False, expected_sar=False, sar_policy_compliant=True, sar_narrative_valid=True,
            exposure_predicted=100.0, exposure_expected_range=[90.0, 110.0], exposure_absolute_error=0.0, exposure_relative_error=0.0,
            policy_compliant=True, approval_routes_valid=True, schema_valid=True, overall_case_score=1.0,
        ),
        CaseEvaluationResult(
            case_id="2", verdict_correct=True, predicted_verdict="fraud", expected_verdict="fraud",
            pattern_correct=True, predicted_pattern="card_not_present_fraud", expected_pattern="card_not_present_fraud",
            action_jaccard=1.0, critical_actions_hit=True, predicted_actions=["BLOCK_CARD"], expected_actions=["BLOCK_CARD"],
            sar_decision_correct=True, predicted_sar=False, expected_sar=False, sar_policy_compliant=True, sar_narrative_valid=True,
            exposure_predicted=50.0, exposure_expected_range=[40.0, 60.0], exposure_absolute_error=0.0, exposure_relative_error=0.0,
            policy_compliant=True, approval_routes_valid=True, schema_valid=True, overall_case_score=1.0,
        ),
        # 1 TN
        CaseEvaluationResult(
            case_id="3", verdict_correct=True, predicted_verdict="legitimate", expected_verdict="legitimate",
            pattern_correct=True, predicted_pattern="none", expected_pattern="none",
            action_jaccard=1.0, critical_actions_hit=True, predicted_actions=["ALLOW_TRANSACTION"], expected_actions=["ALLOW_TRANSACTION"],
            sar_decision_correct=True, predicted_sar=False, expected_sar=False, sar_policy_compliant=True, sar_narrative_valid=True,
            exposure_predicted=0.0, exposure_expected_range=[0.0, 0.0], exposure_absolute_error=0.0, exposure_relative_error=0.0,
            policy_compliant=True, approval_routes_valid=True, schema_valid=True, overall_case_score=1.0,
        ),
        # 1 FP
        CaseEvaluationResult(
            case_id="4", verdict_correct=False, predicted_verdict="fraud", expected_verdict="legitimate",
            pattern_correct=False, predicted_pattern="card_not_present_fraud", expected_pattern="none",
            action_jaccard=0.0, critical_actions_hit=False, predicted_actions=["BLOCK_CARD"], expected_actions=["ALLOW_TRANSACTION"],
            sar_decision_correct=True, predicted_sar=False, expected_sar=False, sar_policy_compliant=True, sar_narrative_valid=True,
            exposure_predicted=20.0, exposure_expected_range=[0.0, 0.0], exposure_absolute_error=20.0, exposure_relative_error=1.0,
            policy_compliant=True, approval_routes_valid=True, schema_valid=True, overall_case_score=0.2,
        ),
    ]

    cm = MetricsEngine.compute_confusion_matrix(results)
    assert cm.true_positives == 2
    assert cm.true_negatives == 1
    assert cm.false_positives == 1
    assert cm.false_negatives == 0
    assert cm.accuracy == 0.75
    assert cm.precision == round(2 / 3, 4)
    assert cm.recall == 1.0


def test_pattern_compatibility():
    assert MetricsEngine.is_pattern_aligned("out_of_region_use", "out_of_region_use") is True
    assert MetricsEngine.is_pattern_aligned("card_not_present_fraud", "card_not_present_new_device") is True
    assert MetricsEngine.is_pattern_aligned("card_testing", "out_of_region_use") is False


def test_composite_score_thresholds():
    dims = DimensionScores(
        verdict_accuracy_score=90.0,
        pattern_identification_score=90.0,
        action_alignment_score=90.0,
        sar_compliance_score=90.0,
        exposure_accuracy_score=90.0,
        policy_compliance_score=90.0,
        determinism_score=90.0,
    )
    composite = MetricsEngine.compute_composite_score(dims, passing_threshold=85.0)
    assert composite.total_score == 90.0
    assert composite.is_passing is True

    failing_dims = DimensionScores(
        verdict_accuracy_score=50.0,
        pattern_identification_score=50.0,
        action_alignment_score=50.0,
        sar_compliance_score=50.0,
        exposure_accuracy_score=50.0,
        policy_compliance_score=50.0,
        determinism_score=50.0,
    )
    failing_composite = MetricsEngine.compute_composite_score(failing_dims, passing_threshold=85.0)
    assert failing_composite.total_score == 50.0
    assert failing_composite.is_passing is False


def test_ground_truth_records_integrity():
    gt_map = load_ground_truth()
    assert len(gt_map) == 20
    for cid, gt in gt_map.items():
        assert cid.startswith("HHG-")
        assert gt.expected_verdict in ["fraud", "legitimate"]
        assert len(gt.expected_actions) > 0
        assert len(gt.critical_actions) > 0
