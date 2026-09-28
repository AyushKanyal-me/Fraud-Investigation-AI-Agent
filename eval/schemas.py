"""
Pydantic data schemas for the Fraud Investigation AI Agent evaluation suite.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class GroundTruthCase(BaseModel):
    """Ground truth reference data for a single investigation case."""
    case_id: str
    expected_verdict: str  # "fraud" or "legitimate"
    expected_pattern: str  # e.g. "out_of_region_use", "card_not_present_fraud", "none"
    expected_actions: List[str] = Field(default_factory=list)  # e.g. ["BLOCK_CARD", "CREATE_CASE"]
    expected_sar_required: bool = False
    expected_min_exposure: float = 0.0
    expected_max_exposure: float = 0.0
    critical_actions: List[str] = Field(default_factory=list)  # subset that MUST be taken if fraud
    source_notes: Optional[str] = None


class ConfusionMatrix(BaseModel):
    """Confusion matrix counts and standard classification rates."""
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    specificity: float = 0.0


class CaseEvaluationResult(BaseModel):
    """Detailed evaluation result for an individual case."""
    case_id: str
    verdict_correct: bool
    predicted_verdict: str
    expected_verdict: str
    
    pattern_correct: bool
    predicted_pattern: str
    expected_pattern: str
    
    action_jaccard: float
    critical_actions_hit: bool
    predicted_actions: List[str]
    expected_actions: List[str]
    
    sar_decision_correct: bool
    predicted_sar: bool
    expected_sar: bool
    sar_policy_compliant: bool
    sar_narrative_valid: bool
    
    exposure_predicted: float
    exposure_expected_range: List[float]
    exposure_absolute_error: float
    exposure_relative_error: float
    
    policy_compliant: bool
    approval_routes_valid: bool
    schema_valid: bool
    
    overall_case_score: float  # 0.0 to 1.0


class DimensionScores(BaseModel):
    """Aggregate scores for the 7 evaluation dimensions (0-100 scale)."""
    verdict_accuracy_score: float = 0.0     # Dim 1 (Weight: 25%)
    pattern_identification_score: float = 0.0 # Dim 2 (Weight: 15%)
    action_alignment_score: float = 0.0     # Dim 3 (Weight: 20%)
    sar_compliance_score: float = 0.0       # Dim 4 (Weight: 15%)
    exposure_accuracy_score: float = 0.0    # Dim 5 (Weight: 10%)
    policy_compliance_score: float = 0.0    # Dim 6 (Weight: 10%)
    determinism_score: float = 100.0        # Dim 7 (Weight: 5%)


class CompositeScore(BaseModel):
    """Weighted composite scorecard with pass/fail determination."""
    total_score: float = 0.0  # 0 to 100
    is_passing: bool = False
    passing_threshold: float = 85.0
    dimension_breakdown: DimensionScores
    weights: Dict[str, float] = {
        "verdict_accuracy": 0.25,
        "pattern_identification": 0.15,
        "action_alignment": 0.20,
        "sar_compliance": 0.15,
        "exposure_accuracy": 0.10,
        "policy_compliance": 0.10,
        "determinism": 0.05,
    }


class EvalMetricsReport(BaseModel):
    """Complete evaluation report covering all cases and dimensions."""
    timestamp: str
    total_cases: int
    confusion_matrix: ConfusionMatrix
    pattern_match_rate: float
    mean_action_jaccard: float
    critical_action_recall: float
    sar_filing_accuracy: float
    sar_policy_adherence_rate: float
    exposure_mae: float
    exposure_mean_relative_error: float
    policy_compliance_rate: float
    determinism_rate: float
    dimension_scores: DimensionScores
    composite_score: CompositeScore
    case_results: List[CaseEvaluationResult]
