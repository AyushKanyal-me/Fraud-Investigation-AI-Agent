"""
Evaluation CLI Runner for Fraud Investigation AI Agent.
Executes the comprehensive 7-dimension benchmark suite, generates reports, and checks CI passing criteria.
"""

import os
import sys
import json
import argparse
from typing import Optional

from eval.evaluator import CaseEvaluator
from eval.schemas import EvalMetricsReport
from eval.ground_truth_builder import DEFAULT_GROUND_TRUTH_PATH


def format_markdown_summary(report: EvalMetricsReport) -> str:
    """Generates a rich Markdown summary of evaluation metrics."""
    cm = report.confusion_matrix
    comp = report.composite_score
    dims = report.dimension_scores

    md = [
        "# Fraud Investigation AI Agent — Evaluation Scorecard",
        f"**Timestamp:** {report.timestamp}  ",
        f"**Total Cases Evaluated:** {report.total_cases}  ",
        f"**Overall Status:** **{'PASSED' if comp.is_passing else 'FAILED'}** (Composite Score: **{comp.total_score} / 100.0**)  ",
        "",
        "## 1. Executive Summary & Composite Score",
        "",
        "| Evaluation Dimension | Weight | Score (0-100) | Weighted Contribution |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Verdict Classification (F1)** | 25% | {dims.verdict_accuracy_score}% | {round(dims.verdict_accuracy_score * 0.25, 2)} / 25.0 |",
        f"| **Pattern Identification** | 15% | {dims.pattern_identification_score}% | {round(dims.pattern_identification_score * 0.15, 2)} / 15.0 |",
        f"| **Next Best Action Alignment** | 20% | {dims.action_alignment_score}% | {round(dims.action_alignment_score * 0.20, 2)} / 20.0 |",
        f"| **SAR Compliance & Narrative** | 15% | {dims.sar_compliance_score}% | {round(dims.sar_compliance_score * 0.15, 2)} / 15.0 |",
        f"| **Exposure Dollar Accuracy** | 10% | {dims.exposure_accuracy_score}% | {round(dims.exposure_accuracy_score * 0.10, 2)} / 10.0 |",
        f"| **Policy & Route Adherence** | 10% | {dims.policy_compliance_score}% | {round(dims.policy_compliance_score * 0.10, 2)} / 10.0 |",
        f"| **Determinism & Stability** | 5% | {dims.determinism_score}% | {round(dims.determinism_score * 0.05, 2)} / 5.0 |",
        f"| **TOTAL COMPOSITE SCORE** | **100%** | **{comp.total_score}%** | **{comp.total_score} / 100.0** (Target: ≥{comp.passing_threshold}%) |",
        "",
        "## 2. Classification Metrics (Confusion Matrix)",
        "",
        f"- **Accuracy:** `{cm.accuracy * 100:.1f}%` ({cm.true_positives + cm.true_negatives}/{report.total_cases})",
        f"- **Precision:** `{cm.precision:.3f}`",
        f"- **Recall (Sensitivity):** `{cm.recall:.3f}`",
        f"- **F1 Score:** `{cm.f1_score:.3f}`",
        f"- **Specificity:** `{cm.specificity:.3f}`",
        "",
        "| | Predicted Fraud | Predicted Legitimate |",
        "| :--- | :---: | :---: |",
        f"| **Actual Fraud** | **TP:** {cm.true_positives} | **FN:** {cm.false_negatives} |",
        f"| **Actual Legitimate** | **FP:** {cm.false_positives} | **TN:** {cm.true_negatives} |",
        "",
        "## 3. Operational & Policy Metrics",
        "",
        f"- **Pattern Match Rate:** `{report.pattern_match_rate * 100:.1f}%`",
        f"- **Mean Action Jaccard Similarity:** `{report.mean_action_jaccard:.3f}`",
        f"- **Critical Action Recall:** `{report.critical_action_recall * 100:.1f}%`",
        f"- **SAR Filing Accuracy:** `{report.sar_filing_accuracy * 100:.1f}%`",
        f"- **SAR Policy Compliance:** `{report.sar_policy_adherence_rate * 100:.1f}%`",
        f"- **Exposure MAE:** `${report.exposure_mae:.2f}`",
        f"- **Exposure Mean Relative Error:** `{report.exposure_mean_relative_error * 100:.1f}%`",
        f"- **Policy & Routing Compliance:** `{report.policy_compliance_rate * 100:.1f}%`",
        "",
        "## 4. Per-Case Evaluation Results",
        "",
        "| Case ID | Predicted Verdict | Expected | Pattern Match | Action Jaccard | SAR Correct | Policy Valid | Overall Score |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for res in report.case_results:
        pm = "✓" if res.pattern_correct else "✗"
        sar = "✓" if res.sar_decision_correct else "✗"
        pol = "✓" if res.policy_compliant else "✗"
        score_pct = f"{res.overall_case_score * 100:.1f}%"
        md.append(
            f"| `{res.case_id}` | `{res.predicted_verdict}` | `{res.expected_verdict}` | {pm} | `{res.action_jaccard:.2f}` | {sar} | {pol} | **{score_pct}** |"
        )

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Fraud Investigation AI Agent Output")
    parser.add_argument("--answers-dir", default="answers", help="Directory containing answer JSON files")
    parser.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH_PATH, help="Path to ground_truth.csv")
    parser.add_argument("--output-json", default="eval/results/eval_report.json", help="Path to save JSON metrics report")
    parser.add_argument("--output-md", default="eval/results/eval_summary.md", help="Path to save Markdown scorecard")
    parser.add_argument("--fail-below", type=float, default=85.0, help="Minimum composite score required to pass")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose stdout table")

    args = parser.parse_args()

    evaluator = CaseEvaluator(ground_truth_path=args.ground_truth)
    report = evaluator.evaluate_answers_directory(answers_dir=args.answers_dir)
    report.composite_score.passing_threshold = args.fail_below
    report.composite_score.is_passing = report.composite_score.total_score >= args.fail_below

    # Ensure output directories exist
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    os.makedirs(os.path.dirname(args.output_md), exist_ok=True)

    # Save outputs
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)

    md_content = format_markdown_summary(report)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Print terminal output
    if not args.quiet:
        cm = report.confusion_matrix
        comp = report.composite_score
        dims = report.dimension_scores

        print("=" * 65)
        print("          FRAUD INVESTIGATION AI AGENT — EVALUATION REPORT       ")
        print("=" * 65)
        print(f"Cases Evaluated:             {report.total_cases}")
        print(f"Verdict Accuracy:            {cm.accuracy * 100:.1f}% ({cm.true_positives + cm.true_negatives}/{report.total_cases})")
        print(f"Verdict Precision:           {cm.precision:.3f}")
        print(f"Verdict Recall:              {cm.recall:.3f}")
        print(f"Verdict F1 Score:            {cm.f1_score:.3f}")
        print(f"Pattern Match Rate:          {report.pattern_match_rate * 100:.1f}%")
        print(f"Mean Action Jaccard Sim:     {report.mean_action_jaccard:.3f}")
        print(f"Critical Action Recall:      {report.critical_action_recall * 100:.1f}%")
        print(f"SAR Filing Accuracy:         {report.sar_filing_accuracy * 100:.1f}%")
        print(f"SAR Policy Adherence:        {report.sar_policy_adherence_rate * 100:.1f}%")
        print(f"Exposure MAE:                ${report.exposure_mae:.2f}")
        print(f"Exposure Mean Rel Error:     {report.exposure_mean_relative_error * 100:.1f}%")
        print(f"Policy & Routing Compliance: {report.policy_compliance_rate * 100:.1f}%")
        print(f"Determinism Stability:       {report.determinism_rate:.1f}%")
        print("-" * 65)
        status_tag = "[PASSED]" if comp.is_passing else "[FAILED]"
        print(f"COMPOSITE BENCHMARK SCORE:   {comp.total_score:.1f} / 100.0  {status_tag}")
        print(f"Threshold:                   >= {comp.passing_threshold:.1f}%")
        print("-" * 65)
        print(f"Full JSON Report:            {args.output_json}")
        print(f"Markdown Summary:            {args.output_md}")
        print("=" * 65)

    if not report.composite_score.is_passing:
        sys.exit(1)


if __name__ == "__main__":
    main()
