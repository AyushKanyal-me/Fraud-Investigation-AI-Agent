from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class HypothesisOutput(BaseModel):
    preliminary_verdict: str = Field(description="fraud | legitimate | uncertain")
    preliminary_probability: float = Field(ge=0.0, le=1.0, description="Estimated fraud probability 0-1")
    preliminary_pattern: str = Field(description="Fraud pattern name or none")
    reasoning: str = Field(description="Summary of initial reasoning")
    suggested_evidence_queries: List[str] = Field(default_factory=list, description="List of suggested graph queries")

class EvidenceSynthesisOutput(BaseModel):
    final_verdict: str = Field(description="fraud | legitimate | uncertain")
    calibrated_probability: float = Field(ge=0.0, le=1.0, description="Calibrated final probability 0-1")
    final_pattern: str = Field(description="Final fraud pattern typology")
    pattern_description: str = Field(default="", description="Description if pattern is undocumented")
    what_changed: str = Field(description="Explanation of how evidence shifted probability and actions")
    stop_reason: str = Field(description="Why the investigation terminated here")
    cited_transaction_ids: List[str] = Field(default_factory=list, description="Transaction IDs cited in evidence")

class SARNarrativeOutput(BaseModel):
    file_sar: bool = Field(description="Whether a SAR should be filed")
    reason: str = Field(description="Policy rationale for filing or not filing")
    narrative: str = Field(default="", description="Comprehensive 5 Ws and H FinCEN narrative")
    subjects: List[str] = Field(default_factory=list, description="Entities named in SAR (customer, cards, devices)")
    activity_dates: List[str] = Field(default_factory=list, description="[first_date, last_date] in YYYY-MM-DD format")
    total_amount_usd: float = Field(default=0.0, ge=0.0, description="Total unauthorized exposure")
