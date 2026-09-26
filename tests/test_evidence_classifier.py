import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.policy import CustomerReplyOutcome
from agent.evidence_classifier import classify_evidence_response

def test_classify_confirmed_legitimate():
    examples = [
        "Yes, that was me. I bought a coffee and lunch at the airport.",
        "I confirm this transaction is legitimate.",
        "I made this purchase yesterday on Amazon.",
        "This is valid charge, not fraud at all.",
        "I authorize this payment, it was completed by me."
    ]
    for text in examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.CONFIRMED_LEGITIMATE
        assert conf >= 0.85

def test_classify_denied_unauthorized():
    examples = [
        "I did not make this transaction! My card is in my wallet.",
        "I do not recognize this merchant and never visited Singapore.",
        "Unauthorized charge! Please block my card immediately, it's stolen.",
        "This is a fraudulent charge, I never authorized $499.",
        "Not my purchase. Card compromised."
    ]
    for text in examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.DENIED_UNAUTHORIZED
        assert conf >= 0.85

def test_classify_recurring_dispute():
    examples = [
        "This is my monthly gym membership but I thought I cancelled it.",
        "Recurring subscription to Netflix that I forgot to cancel.",
        "Disputing this billing charge - annual subscription auto-renewed.",
        "Duplicate monthly cloud service charge, requesting refund."
    ]
    for text in examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.RECURRING_DISPUTE
        assert conf >= 0.85

def test_classify_step_up_auth():
    passed_examples = [
        "Step-up passed successfully via SMS OTP.",
        "2FA successful, biometric verified.",
        "OTP verified and challenge completed."
    ]
    for text in passed_examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.STEP_UP_PASSED
        assert conf >= 0.90

    failed_examples = [
        "Step-up failed: incorrect OTP entered 3 times.",
        "2FA failed, max attempts exceeded.",
        "Biometric failed, wrong passcode entered."
    ]
    for text in failed_examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.STEP_UP_FAILED
        assert conf >= 0.90

def test_classify_no_reply_24h():
    examples = [
        "No reply received from cardholder within 24 hours.",
        "Customer unreachable, SMS delivery timed out.",
        "NO_REPLY_24H: 24-hour verification window expired."
    ]
    for text in examples:
        outcome, conf, reason = classify_evidence_response(text)
        assert outcome == CustomerReplyOutcome.NO_REPLY_24H
        assert conf >= 0.90

def test_classify_safe_default_unrecognized():
    text = "Lorem ipsum dolor sit amet, arbitrary unparseable text here."
    outcome, conf, reason = classify_evidence_response(text)
    # Must NOT blindly assume DENIED_UNAUTHORIZED and block card
    assert outcome == CustomerReplyOutcome.NO_REPLY_24H
    assert conf <= 0.60
