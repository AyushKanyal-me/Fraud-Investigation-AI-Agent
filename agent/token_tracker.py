import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class TokenUsageRecord:
    step_name: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_s: float
    timestamp: float = field(default_factory=time.time)

class TokenTracker:
    """
    Centralized token accountant tracking LLM usage, token costs, and call latencies.
    """
    def __init__(self):
        self.records: List[TokenUsageRecord] = []

    def record_usage(
        self,
        step_name: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_s: float = 0.0
    ) -> TokenUsageRecord:
        total = prompt_tokens + completion_tokens
        rec = TokenUsageRecord(
            step_name=step_name,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            latency_s=round(latency_s, 3)
        )
        self.records.append(rec)
        return rec

    def get_total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    def get_total_latency(self) -> float:
        return round(sum(r.latency_s for r in self.records), 3)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_calls": len(self.records),
            "total_tokens": self.get_total_tokens(),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "total_completion_tokens": sum(r.completion_tokens for r in self.records),
            "total_latency_s": self.get_total_latency(),
            "records": [
                {
                    "step": r.step_name,
                    "model": r.model_name,
                    "tokens": r.total_tokens,
                    "latency_s": r.latency_s
                }
                for r in self.records
            ]
        }
