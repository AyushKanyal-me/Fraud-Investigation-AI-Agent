import json
import re
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("agent_schemas")

VALID_VERDICTS = {"fraud", "legitimate", "uncertain"}


def extract_json_from_llm_text(text: str) -> Dict[str, Any]:
    """Extract JSON dict from markdown code block or raw LLM string."""
    text = text.strip()
    if not text:
        return {}

    # Try ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try finding outermost { ... }
    match_braces = re.search(r"(\{.*\})", text, re.DOTALL)
    if match_braces:
        try:
            return json.loads(match_braces.group(1))
        except Exception:
            pass

    try:
        return json.loads(text)
    except Exception as e:
        logger.debug("Failed to extract JSON from LLM text: %s", e)
        return {}


class HypothesisOutput(BaseModel):
    preliminary_verdict: str = Field(description="fraud | legitimate | uncertain")
    preliminary_probability: float = Field(ge=0.0, le=1.0, description="Estimated fraud probability 0-1")
    preliminary_pattern: str = Field(description="Fraud pattern name or none")
    reasoning: str = Field(description="Summary of initial reasoning")
    suggested_evidence_queries: List[str] = Field(default_factory=list, description="List of suggested graph queries")

    @field_validator("preliminary_verdict", mode="before")
    @classmethod
    def validate_verdict(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if s in VALID_VERDICTS:
            return s
        if "fraud" in s:
            return "fraud"
        if "legit" in s:
            return "legitimate"
        return "uncertain"

    @classmethod
    def from_llm_text(cls, text: str) -> Optional["HypothesisOutput"]:
        data = extract_json_from_llm_text(text)
        if not data:
            return None
        try:
            return cls(**data)
        except Exception as e:
            logger.warning("Error validating HypothesisOutput from LLM: %s", e)
            return None


class EvidenceSynthesisOutput(BaseModel):
    final_verdict: str = Field(description="fraud | legitimate | uncertain")
    calibrated_probability: float = Field(ge=0.0, le=1.0, description="Calibrated final probability 0-1")
    final_pattern: str = Field(description="Final fraud pattern typology")
    pattern_description: str = Field(default="", description="Description if pattern is undocumented")
    what_changed: str = Field(description="Explanation of how evidence shifted probability and actions")
    stop_reason: str = Field(description="Why the investigation terminated here")
    cited_transaction_ids: List[str] = Field(default_factory=list, description="Transaction IDs cited in evidence")

    @field_validator("final_verdict", mode="before")
    @classmethod
    def validate_verdict(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if s in VALID_VERDICTS:
            return s
        if "fraud" in s:
            return "fraud"
        if "legit" in s:
            return "legitimate"
        return "uncertain"

    @classmethod
    def from_llm_text(cls, text: str) -> Optional["EvidenceSynthesisOutput"]:
        data = extract_json_from_llm_text(text)
        if not data:
            return None
        try:
            return cls(**data)
        except Exception as e:
            logger.warning("Error validating EvidenceSynthesisOutput from LLM: %s", e)
            return None


class SARNarrativeOutput(BaseModel):
    file_sar: bool = Field(description="Whether a SAR should be filed")
    reason: str = Field(description="Policy rationale for filing or not filing")
    narrative: str = Field(default="", description="Comprehensive 5 Ws and H FinCEN narrative")
    subjects: List[str] = Field(default_factory=list, description="Entities named in SAR (customer, cards, devices)")
    activity_dates: List[str] = Field(default_factory=list, description="[first_date, last_date] in YYYY-MM-DD format")
    total_amount_usd: float = Field(default=0.0, ge=0.0, description="Total unauthorized exposure")

    @classmethod
    def from_llm_text(cls, text: str) -> Optional["SARNarrativeOutput"]:
        data = extract_json_from_llm_text(text)
        if not data:
            return None
        try:
            return cls(**data)
        except Exception as e:
            logger.warning("Error validating SARNarrativeOutput from LLM: %s", e)
            return None
