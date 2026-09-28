"""
Evaluation package for Fraud Investigation AI Agent.
Provides multi-dimensional metrics, ground-truth benchmarking, determinism checks,
and CI regression validation.
"""

from eval.schemas import (
    GroundTruthCase,
    CaseEvaluationResult,
    EvalMetricsReport,
    DimensionScores,
    CompositeScore,
)
from eval.metrics import MetricsEngine
from eval.evaluator import CaseEvaluator

__all__ = [
    "GroundTruthCase",
    "CaseEvaluationResult",
    "EvalMetricsReport",
    "DimensionScores",
    "CompositeScore",
    "MetricsEngine",
    "CaseEvaluator",
]
