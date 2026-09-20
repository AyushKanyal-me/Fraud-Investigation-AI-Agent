import pytest
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.policy import (
    evaluate_policy_rules,
    get_action_route,
    CaseVerdict,
    CaseStatus,
    FraudPattern,
    ActionType,
    ApprovalRoute,
    CustomerReplyOutcome,
    POLICY_VERSION
)

def test_policy_version():
    assert POLICY_VERSION == "2026.1.0"

def test_approval_routes():
    # Test Auto actions
    auto_actions = [
        "ALLOW_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS",
        "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH",
        "GENERATE_REPORT", "CREATE_CASE", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD"
    ]
    for action in auto_actions:
        assert get_action_route(action, exposure_usd=10000.0) == ApprovalRoute.AUTO.value

    # Test L1 actions
    assert get_action_route("DECLINE_TRANSACTION", exposure_usd=0.0) == ApprovalRoute.L1.value
    assert get_action_route("BLOCK_CARD", exposure_usd=500.0) == ApprovalRoute.L1.value
    assert get_action_route("BLOCK_CARD", exposure_usd=2500.0) == ApprovalRoute.L1.value

    # Test L2 actions
    assert get_action_route("BLOCK_CARD", exposure_usd=2500.01) == ApprovalRoute.L2.value
    assert get_action_route("BLOCK_CARD", exposure_usd=10000.0) == ApprovalRoute.L2.value
    assert get_action_route("BLOCK_ALL_CARDS", exposure_usd=100.0) == ApprovalRoute.L2.value
    assert get_action_route("FILE_REPORT", exposure_usd=100.0) == ApprovalRoute.L2.value

def test_r1_verify_before_block_weak_signal():
    # Initial stage, prob < 0.70 -> VERIFY_WITH_CUSTOMER
    actions, sar_file, _ = evaluate_policy_rules(
        stage="initial",
        verdict=CaseVerdict.UNCERTAIN.value,
        fraud_prob=0.45,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=100.0,
        connected_cards=[]
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.VERIFY_WITH_CUSTOMER.value in action_names
    assert ActionType.BLOCK_CARD.value not in action_names
    assert not sar_file

    # High exposure > 500 under R1 adds MONITOR_CARD
    actions_exp, _, _ = evaluate_policy_rules(
        stage="initial",
        verdict=CaseVerdict.UNCERTAIN.value,
        fraud_prob=0.55,
        pattern=FraudPattern.OUT_OF_REGION_USE.value,
        exposure_usd=600.0,
        connected_cards=[]
    )
    action_names_exp = [a["action"] for a in actions_exp]
    assert ActionType.VERIFY_WITH_CUSTOMER.value in action_names_exp
    assert ActionType.MONITOR_CARD.value in action_names_exp

def test_r2_customer_denies_transaction():
    # Customer denial -> BLOCK_CARD (L1 when <= 2500) + CREATE_CASE
    actions, sar_file, sar_reason = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.90,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=300.0,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.BLOCK_CARD.value in action_names
    assert ActionType.CREATE_CASE.value in action_names
    assert not sar_file  # Exposure <= 1000 and no shared ring

    # Denial with exposure > 1000 triggers FILE_REPORT (L2)
    actions_sar, sar_file_sar, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.90,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=1500.0,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names_sar = [a["action"] for a in actions_sar]
    assert ActionType.FILE_REPORT.value in action_names_sar
    assert sar_file_sar is True

def test_r3_customer_confirms_transaction():
    # Customer confirms -> ALLOW_TRANSACTION + CLOSE_NO_FRAUD
    actions, sar_file, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.LEGITIMATE.value,
        fraud_prob=0.05,
        pattern=FraudPattern.NONE.value,
        exposure_usd=0.0,
        customer_outcome=CustomerReplyOutcome.CONFIRMED_LEGITIMATE
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.ALLOW_TRANSACTION.value in action_names
    assert ActionType.CLOSE_NO_FRAUD.value in action_names
    assert not sar_file

def test_r4_no_reply_24_hours():
    # No reply within 24h -> MONITOR_CARD + DECLINE_TRANSACTION
    actions, _, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.UNCERTAIN.value,
        fraud_prob=0.50,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=200.0,
        customer_outcome=CustomerReplyOutcome.NO_REPLY_24H
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.MONITOR_CARD.value in action_names
    assert ActionType.DECLINE_TRANSACTION.value in action_names
    assert ActionType.ESCALATE_TO_ANALYST.value not in action_names

    # If exposure > 500, escalate to analyst
    actions_esc, _, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.UNCERTAIN.value,
        fraud_prob=0.50,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=750.0,
        customer_outcome=CustomerReplyOutcome.NO_REPLY_24H
    )
    action_names_esc = [a["action"] for a in actions_esc]
    assert ActionType.ESCALATE_TO_ANALYST.value in action_names_esc

def test_r5_card_testing():
    # Card testing initial without cleared > 100 -> DECLINE_TRANSACTION + STEP_UP_AUTH
    actions, _, _ = evaluate_policy_rules(
        stage="initial",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.85,
        pattern=FraudPattern.CARD_TESTING.value,
        exposure_usd=50.0,
        is_card_testing=True,
        testing_cleared_gt_100=False
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.DECLINE_TRANSACTION.value in action_names
    assert ActionType.STEP_UP_AUTH.value in action_names
    assert ActionType.BLOCK_CARD.value not in action_names

    # Card testing with cleared > 100 -> DECLINE_TRANSACTION + BLOCK_CARD
    actions_cleared, _, _ = evaluate_policy_rules(
        stage="initial",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.85,
        pattern=FraudPattern.CARD_TESTING.value,
        exposure_usd=250.0,
        is_card_testing=True,
        testing_cleared_gt_100=True
    )
    action_names_cleared = [a["action"] for a in actions_cleared]
    assert ActionType.DECLINE_TRANSACTION.value in action_names_cleared
    assert ActionType.BLOCK_CARD.value in action_names_cleared

def test_r6_shared_origin_across_cards():
    # Shared device/ring -> CREATE_CASE + FILE_REPORT + MONITOR_CONNECTED_CARDS
    actions, sar_file, sar_reason = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.90,
        pattern=FraudPattern.ACCOUNT_TAKEOVER.value,
        exposure_usd=75.0,  # Under 1000, but shared ring triggers SAR
        connected_cards=["C00877-K1"],
        has_shared_device_ring=True,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.BLOCK_CARD.value in action_names
    assert ActionType.CREATE_CASE.value in action_names
    assert ActionType.FILE_REPORT.value in action_names
    assert ActionType.MONITOR_CONNECTED_CARDS.value in action_names
    assert sar_file is True

def test_r7_recurring_dispute():
    # Initial stage for recurring dispute: CREATE_CASE, VERIFY_WITH_CUSTOMER, WARN_CUSTOMER
    actions_init, _, _ = evaluate_policy_rules(
        stage="initial",
        verdict=CaseVerdict.LEGITIMATE.value,
        fraud_prob=0.10,
        pattern=FraudPattern.NONE.value,
        exposure_usd=49.0,
        is_recurring_dispute=True
    )
    action_names_init = [a["action"] for a in actions_init]
    assert ActionType.CREATE_CASE.value in action_names_init
    assert ActionType.VERIFY_WITH_CUSTOMER.value in action_names_init
    assert ActionType.WARN_CUSTOMER.value in action_names_init
    assert ActionType.BLOCK_CARD.value not in action_names_init

    # Final stage for recurring dispute: CREATE_CASE, WARN_CUSTOMER, CLOSE_NO_FRAUD
    actions_final, sar_file, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.LEGITIMATE.value,
        fraud_prob=0.05,
        pattern=FraudPattern.NONE.value,
        exposure_usd=0.0,
        is_recurring_dispute=True,
        customer_outcome=CustomerReplyOutcome.RECURRING_DISPUTE
    )
    action_names_final = [a["action"] for a in actions_final]
    assert ActionType.CREATE_CASE.value in action_names_final
    assert ActionType.WARN_CUSTOMER.value in action_names_final
    assert ActionType.CLOSE_NO_FRAUD.value in action_names_final
    assert not sar_file

def test_r8_escalate_when_uncertain_and_exposed():
    # Uncertain verdict with exposure > 500 -> ESCALATE_TO_ANALYST
    actions, _, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.UNCERTAIN.value,
        fraud_prob=0.50,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=800.0
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.CREATE_CASE.value in action_names
    assert ActionType.MONITOR_CARD.value in action_names
    assert ActionType.ESCALATE_TO_ANALYST.value in action_names

def test_r9_undocumented_pattern():
    # Undocumented pattern -> CREATE_CASE + FILE_REPORT + ESCALATE_TO_ANALYST
    actions, sar_file, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.90,
        pattern=FraudPattern.UNDOCUMENTED.value,
        exposure_usd=400.0,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names = [a["action"] for a in actions]
    assert ActionType.CREATE_CASE.value in action_names
    assert ActionType.FILE_REPORT.value in action_names
    assert ActionType.ESCALATE_TO_ANALYST.value in action_names
    assert sar_file is True

def test_r10_block_all_cards_restriction():
    # Single card compromise must NOT trigger BLOCK_ALL_CARDS
    actions_single, _, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.90,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD.value,
        exposure_usd=1000.0,
        multi_card_compromised=False,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names_single = [a["action"] for a in actions_single]
    assert ActionType.BLOCK_CARD.value in action_names_single
    assert ActionType.BLOCK_ALL_CARDS.value not in action_names_single

    # Multi-card compromised triggers BLOCK_ALL_CARDS (L2)
    actions_multi, _, _ = evaluate_policy_rules(
        stage="final",
        verdict=CaseVerdict.FRAUD.value,
        fraud_prob=0.95,
        pattern=FraudPattern.ACCOUNT_TAKEOVER.value,
        exposure_usd=3500.0,
        multi_card_compromised=True,
        customer_outcome=CustomerReplyOutcome.DENIED_UNAUTHORIZED
    )
    action_names_multi = [a["action"] for a in actions_multi]
    assert ActionType.BLOCK_ALL_CARDS.value in action_names_multi
    for a in actions_multi:
        if a["action"] == ActionType.BLOCK_ALL_CARDS.value:
            assert a["route"] == ApprovalRoute.L2.value
