"""
Evidence Classifier Module for Fraud Investigation Agent.
Classifies external evidence and cardholder inquiry responses into canonical CustomerReplyOutcome enums
using regex patterns, sentiment/negation analysis, and optional LLM classification.
"""

import re
import logging
from typing import Optional, Tuple, Any
from agent.policy import CustomerReplyOutcome

logger = logging.getLogger("evidence_classifier")

# -------------------------------------------------------------
# Regex Rules & Typology Patterns
# -------------------------------------------------------------
_CONFIRMED_LEGITIMATE_PATTERNS = [
    r"\b(i\s+(did|made|authorized|recognize|completed|initiated|approve|bought)\s+(this|the|that|these|all|it))\b",
    r"\b(yes[,.]?\s+(it\s+was\s+me|that\s+was\s+me|it\s+is\s+mine|authorized|i\s+did|i\s+made))\b",
    r"\b(my\s+(charge|purchase|transaction|order|payment))\b",
    r"\b(valid\s+(charge|purchase|transaction|activity))\b",
    r"\b(not\s+(fraud|fraudulent|unauthorized|suspicious|stolen|compromised))\b",
    r"\b(authorized|legitimate|confirmed\s+legitimate|recognized)\b",
    r"\b(it\s+was\s+me\b)",
    r"\b(i\s+confirm\b)",
    r"\b(i\s+authorize\b)"
]

_DENIED_UNAUTHORIZED_PATTERNS = [
    r"\b(did\s+not\s+(make|authorize|do|buy|order|initiate|recognize|use))\b",
    r"\b(do\s+not\s+recognize\b)",
    r"\b(never\s+(made|authorized|used|seen|bought|ordered|visited))\b",
    r"\b(?<!not\s)(?<!no\s)(unauthorized|fraud|fraudulent|scam|compromised|stolen|hacked|card\s+stolen)\b",
    r"\b(not\s+my\s+(charge|card|purchase|transaction|order))\b",
    r"\b(not\s+authorized\b)",
    r"\b(denied|deny|rejected\s+by\s+customer)\b",
    r"\b(i\s+did\s+not\b)"
]


_RECURRING_DISPUTE_PATTERNS = [
    r"\b(recurring|subscription|monthly|membership|auto-renew|annual\s+plan)\b",
    r"\b(forgot\s+to\s+cancel|already\s+cancelled|cancel\s+subscription)\b",
    r"\b(billing\s+dispute|duplicate\s+charge|overcharged|wrong\s+amount|refund\s+requested)\b",
    r"\b(gym\s+membership|netflix|spotify|amazon\s+prime|cloud\s+service)\b"
]

_NO_REPLY_PATTERNS = [
    r"\b(no\s+(reply|response|answer)\b)",
    r"\b(timed?\s*out|unreachable|24\s*h(our)?s?|expired\s+window)\b",
    r"\b(no_reply_24h|customer\s+unreachable|no\s+contact)\b"
]

_STEP_UP_PASSED_PATTERNS = [
    r"\b(step[_\s-]?up\s+passed|otp\s+verified|2fa\s+successful|mfa\s+passed|biometric\s+verified|passcode\s+accepted)\b",
    r"\b(challenge\s+completed|code\s+verified|authenticated\s+successfully)\b"
]

_STEP_UP_FAILED_PATTERNS = [
    r"\b(step[_\s-]?up\s+failed|otp\s+failed|wrong\s+otp|incorrect\s+(code|pin|password)|2fa\s+failed)\b",
    r"\b(challenge\s+failed|max\s+attempts\s+exceeded|biometric\s+failed|mfa\s+failed)\b"
]


def classify_evidence_response(
    response_text: str,
    llm_caller: Optional[Any] = None
) -> Tuple[CustomerReplyOutcome, float, str]:
    """
    Classifies a customer response or external evidence string into a canonical CustomerReplyOutcome.
    
    Args:
        response_text: Text string returned by customer or system.
        llm_caller: Optional callable _call_gemini_structured / _call_gemini for ambiguous fallback.
        
    Returns:
        (outcome, confidence, reasoning)
    """
    if not response_text or not response_text.strip():
        return CustomerReplyOutcome.NO_REQUEST, 1.0, "Empty response text"

    text = response_text.strip()
    text_lower = text.lower()

    # 1. Step-up Auth Checks (High priority)
    for p in _STEP_UP_PASSED_PATTERNS:
        if re.search(p, text_lower):
            return CustomerReplyOutcome.STEP_UP_PASSED, 0.98, f"Pattern matched step-up success: '{p}'"

    for p in _STEP_UP_FAILED_PATTERNS:
        if re.search(p, text_lower):
            return CustomerReplyOutcome.STEP_UP_FAILED, 0.98, f"Pattern matched step-up failure: '{p}'"

    # 2. No Reply / Timeout Checks
    for p in _NO_REPLY_PATTERNS:
        if re.search(p, text_lower):
            return CustomerReplyOutcome.NO_REPLY_24H, 0.95, f"Pattern matched 24h timeout/unreachable: '{p}'"

    # 3. Recurring Dispute Checks
    for p in _RECURRING_DISPUTE_PATTERNS:
        if re.search(p, text_lower):
            return CustomerReplyOutcome.RECURRING_DISPUTE, 0.92, f"Pattern matched recurring subscription dispute: '{p}'"

    # 4. Legitimate vs Unauthorized with Negation Disambiguation
    has_denial = any(re.search(p, text_lower) for p in _DENIED_UNAUTHORIZED_PATTERNS)
    has_confirm = any(re.search(p, text_lower) for p in _CONFIRMED_LEGITIMATE_PATTERNS)

    if has_confirm and not has_denial:
        return CustomerReplyOutcome.CONFIRMED_LEGITIMATE, 0.95, "Cardholder confirmed transaction as authorized"
    
    if has_denial and not has_confirm:
        return CustomerReplyOutcome.DENIED_UNAUTHORIZED, 0.95, "Cardholder explicitly denied transaction / reported unauthorized fraud"

    if has_confirm and has_denial:
        if "not authorized" in text_lower or "did not authorize" in text_lower or "not my" in text_lower or "never" in text_lower:
            return CustomerReplyOutcome.DENIED_UNAUTHORIZED, 0.88, "Negated authorization statement indicates unauthorized fraud"
        if "not fraud" in text_lower or "not suspicious" in text_lower or "it was me" in text_lower:
            return CustomerReplyOutcome.CONFIRMED_LEGITIMATE, 0.88, "Negated fraud statement indicates cardholder authorization"

    # 5. LLM Fallback for Ambiguous Statements (if provided)
    if llm_caller:
        try:
            prompt = (
                f"Classify the following customer bank fraud inquiry response into exactly one of: "
                f"CONFIRMED_LEGITIMATE, DENIED_UNAUTHORIZED, RECURRING_DISPUTE, NO_REPLY_24H, "
                f"STEP_UP_FAILED, STEP_UP_PASSED.\n"
                f"Response text: \"{text}\"\n"
                f"Reply with ONLY the exact enum string."
            )
            raw = llm_caller(prompt)
            if raw:
                raw_clean = str(raw).strip().upper()
                for outcome in CustomerReplyOutcome:
                    if outcome.value in raw_clean:
                        return outcome, 0.85, f"LLM classified response as {outcome.value}"
        except Exception as e:
            logger.warning("LLM evidence classification fallback encountered error: %s", e)

    # 6. Fallback Heuristics
    if "yes" in text_lower or "ok" in text_lower or "fine" in text_lower or "legit" in text_lower:
        return CustomerReplyOutcome.CONFIRMED_LEGITIMATE, 0.70, "Heuristic matched affirmative response"
    
    if "no" in text_lower or "stop" in text_lower or "fake" in text_lower or "scam" in text_lower:
        return CustomerReplyOutcome.DENIED_UNAUTHORIZED, 0.70, "Heuristic matched denial response"

    # Safe default: if completely unparseable, do NOT assume fraud and block card; mark as NO_REPLY_24H
    return CustomerReplyOutcome.NO_REPLY_24H, 0.50, f"Unrecognized response text defaulted safely without destructive block: '{text}'"
