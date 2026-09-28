"""
Historical Benchmark for Fraud Investigation AI Agent.
Evaluates alignment against 5,565 human-investigated closed historical cases in closed_cases_history.csv.
"""

import os
import csv
import json
from typing import List, Dict, Any, Optional
from eval.metrics import MetricsEngine

DEFAULT_HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Dataset",
    "closed_cases_history.csv",
)


class HistoricalBenchmark:
    """Evaluates agent predictions or historical parity against human investigator records."""

    def __init__(self, history_csv_path: str = DEFAULT_HISTORY_PATH):
        self.history_csv_path = history_csv_path
        self.records: List[Dict[str, Any]] = []
        self._load_records()

    def _load_records(self):
        if not os.path.exists(self.history_csv_path):
            return
        with open(self.history_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.records.append(row)

    def compute_historical_distribution(self) -> Dict[str, Any]:
        """Calculates statistical distributions across historical closed cases."""
        total = len(self.records)
        if total == 0:
            return {}

        outcomes = {}
        patterns = {}
        reports_filed = 0
        total_exposure = 0.0

        for r in self.records:
            outcome = r.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            pattern = r.get("pattern", "unknown")
            patterns[pattern] = patterns.get(pattern, 0) + 1

            if r.get("report_filed", "").strip().lower() in ["yes", "true", "1"]:
                reports_filed += 1

            try:
                exp = float(r.get("exposure_usd", 0.0))
                total_exposure += exp
            except ValueError:
                pass

        return {
            "total_cases": total,
            "outcomes": outcomes,
            "patterns": patterns,
            "sar_rate": round(reports_filed / total, 4),
            "mean_exposure": round(total_exposure / total, 2),
        }

    def evaluate_sample_alignment(
        self,
        predicted_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluates a sample of predictions against historical ground-truth records.
        """
        if not self.records:
            return {"error": "No historical records found."}

        history_map = {r["case_id"]: r for r in self.records}
        matched = 0
        verdict_matches = 0
        action_jaccards = []

        for p in predicted_cases:
            cid = p.get("case_id")
            if cid in history_map:
                matched += 1
                h = history_map[cid]
                h_outcome = h.get("outcome", "")
                is_fraud_hist = "fraud" in h_outcome.lower()
                pred_verdict = p.get("case", {}).get("verdict", "").lower()
                if (pred_verdict == "fraud" and is_fraud_hist) or (pred_verdict == "legitimate" and not is_fraud_hist):
                    verdict_matches += 1

                # Actions comparison
                h_actions = set(h.get("actions_taken", "").split("|"))
                pred_actions = set(a.get("action", "") for a in p.get("next_best_actions", {}).get("final", []))
                action_jaccards.append(MetricsEngine.calculate_jaccard_similarity(pred_actions, h_actions))

        return {
            "evaluated_sample_size": matched,
            "verdict_match_rate": round(verdict_matches / matched, 4) if matched > 0 else 0.0,
            "mean_action_jaccard": round(sum(action_jaccards) / len(action_jaccards), 4) if action_jaccards else 0.0,
        }
