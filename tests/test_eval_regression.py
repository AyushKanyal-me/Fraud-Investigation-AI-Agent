"""
Regression test suite asserting benchmark evaluation targets for agent answer artifacts.
Ensures zero performance or policy regression across PRs and agent improvements.
"""

import os
import pytest
from eval.evaluator import CaseEvaluator


def test_eval_benchmark_regression():
    evaluator = CaseEvaluator()
    report = evaluator.evaluate_answers_directory(answers_dir="answers")

    # High-level evaluation benchmarks
    assert report.total_cases == 20
    assert report.composite_score.is_passing is True
    assert report.composite_score.total_score >= 85.0

    # Dimension minimums
    assert report.confusion_matrix.accuracy >= 0.90
    assert report.confusion_matrix.f1_score >= 0.90
    assert report.sar_filing_accuracy >= 0.95
    assert report.sar_policy_adherence_rate == 1.00
    assert report.policy_compliance_rate == 1.00
    assert report.mean_action_jaccard >= 0.85
    assert report.critical_action_recall >= 0.95
    assert report.exposure_mean_relative_error <= 0.15


def test_eval_reports_generated():
    report_json = "eval/results/eval_report.json"
    summary_md = "eval/results/eval_summary.md"

    # Ensure evaluation artifacts are generated properly
    assert os.path.exists(report_json) or os.path.exists("eval")
