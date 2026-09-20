import enum
from typing import List, Dict, Any, Tuple, Optional

class CustomerReplyOutcome(str, enum.Enum):
    CONFIRMED_LEGITIMATE = "CONFIRMED_LEGITIMATE"
    DENIED_UNAUTHORIZED = "DENIED_UNAUTHORIZED"
    NO_REPLY_24H = "NO_REPLY_24H"
    RECURRING_DISPUTE = "RECURRING_DISPUTE"
    STEP_UP_FAILED = "STEP_UP_FAILED"
    STEP_UP_PASSED = "STEP_UP_PASSED"
    NO_REQUEST = "NO_REQUEST"

def get_action_route(action: str, exposure_usd: float = 0.0) -> str:
    """
    Returns exact approval route ('auto', 'L1', 'L2') strictly defined by Section 2:
    - auto: ALLOW_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER, 
            VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, GENERATE_REPORT, CREATE_CASE, 
            ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD
    - L1:   DECLINE_TRANSACTION; BLOCK_CARD when exposure <= $2,500
    - L2:   BLOCK_CARD when exposure > $2,500; BLOCK_ALL_CARDS always; FILE_REPORT always
    """
    if action in [
        "ALLOW_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS",
        "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH",
        "GENERATE_REPORT", "CREATE_CASE", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD"
    ]:
        return "auto"
    elif action == "DECLINE_TRANSACTION":
        return "L1"
    elif action == "BLOCK_CARD":
        if exposure_usd > 2500.0:
            return "L2"
        return "L1"
    elif action in ["BLOCK_ALL_CARDS", "FILE_REPORT"]:
        return "L2"
    return "auto"

def evaluate_policy_rules(
    stage: str,  # "initial" or "final"
    verdict: str,  # "fraud", "legitimate", "uncertain"
    fraud_prob: float,
    pattern: str,
    exposure_usd: float,
    connected_cards: List[str],
    has_shared_device_ring: bool = False,
    is_card_testing: bool = False,
    testing_cleared_gt_100: bool = False,
    is_recurring_dispute: bool = False,
    customer_outcome: CustomerReplyOutcome = CustomerReplyOutcome.NO_REQUEST,
    multi_card_compromised: bool = False
) -> Tuple[List[Dict[str, str]], bool, str]:
    """
    Evaluates bank policy rules R1-R10 to produce exact actions, approval routes, and SAR decisions.
    """
    actions = []
    sar_file = False
    sar_reason = ""

    if stage == "initial":
        # Initial recommendation (before evidence request reply)
        if verdict == "legitimate" or (fraud_prob <= 0.15 and customer_outcome == CustomerReplyOutcome.NO_REQUEST):
            actions.append({
                "action": "ALLOW_TRANSACTION",
                "route": "auto",
                "reason": "Policy Section 1: Transaction conforms to historical spending baseline"
            })
            actions.append({
                "action": "CLOSE_NO_FRAUD",
                "route": "auto",
                "reason": "Policy Section 1: Alert evaluated as legitimate cardholder activity"
            })
        elif is_recurring_dispute:
            actions.append({
                "action": "CREATE_CASE",
                "route": "auto",
                "reason": "R7: Recurring subscription dispute investigation"
            })
            actions.append({
                "action": "VERIFY_WITH_CUSTOMER",
                "route": "auto",
                "reason": "R7: Verify recurring transaction terms with customer before blocking"
            })
            actions.append({
                "action": "WARN_CUSTOMER",
                "route": "auto",
                "reason": "R7: Send recurring charge notice to customer"
            })
        elif is_card_testing:
            actions.append({
                "action": "DECLINE_TRANSACTION",
                "route": "L1",
                "reason": "R5: Micro-authorization testing sequence observed; decline pending authorizations"
            })
            if testing_cleared_gt_100:
                actions.append({
                    "action": "BLOCK_CARD",
                    "route": get_action_route("BLOCK_CARD", exposure_usd),
                    "reason": "R5: Testing sequence observed and purchase over $100 has already cleared"
                })
            else:
                actions.append({
                    "action": "STEP_UP_AUTH",
                    "route": "auto",
                    "reason": "R5: Require step-up multi-factor authentication following card testing activity"
                })
        elif fraud_prob < 0.70:
            # Rule R1: Verify before you block on a weak signal
            actions.append({
                "action": "VERIFY_WITH_CUSTOMER",
                "route": "auto",
                "reason": f"R1: Assessed fraud probability {fraud_prob:.2f} is below 0.70 on initial alert; verify before blocking to prevent policy breach"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": "MONITOR_CARD",
                    "route": "auto",
                    "reason": "Policy Section 1: Elevate card monitoring sensitivity for 72 hours pending reply"
                })
        else:
            # High probability initial signal
            actions.append({
                "action": "DECLINE_TRANSACTION",
                "route": "L1",
                "reason": "Policy Section 1: Decline authorization on high risk alert"
            })
            actions.append({
                "action": "VERIFY_WITH_CUSTOMER",
                "route": "auto",
                "reason": "R1: Verify with customer to confirm unauthorized compromise"
            })

    elif stage == "final":
        # Final recommendation after evidence request response
        if customer_outcome == CustomerReplyOutcome.CONFIRMED_LEGITIMATE or verdict == "legitimate":
            actions.append({
                "action": "ALLOW_TRANSACTION",
                "route": "auto",
                "reason": "R3: Customer confirmed the transaction as authorized"
            })
            actions.append({
                "action": "CLOSE_NO_FRAUD",
                "route": "auto",
                "reason": "R3: Alert closed as legitimate following cardholder confirmation"
            })
            sar_file = False
            sar_reason = "Transaction confirmed legitimate by cardholder; no suspicious activity report filed"

        elif is_recurring_dispute:
            actions.append({
                "action": "CREATE_CASE",
                "route": "auto",
                "reason": "R7: Record recurring billing dispute in internal graph case"
            })
            actions.append({
                "action": "WARN_CUSTOMER",
                "route": "auto",
                "reason": "R7: Customer reminded of recurring merchant billing terms"
            })
            actions.append({
                "action": "CLOSE_NO_FRAUD",
                "route": "auto",
                "reason": "R7: Activity matches monthly recurring schedule; closed without card block"
            })
            sar_file = False

        elif customer_outcome == CustomerReplyOutcome.NO_REPLY_24H:
            # Rule R4: No reply within 24 hours
            actions.append({
                "action": "MONITOR_CARD",
                "route": "auto",
                "reason": "R4: Cardholder unreachable within 24 hours; elevate card monitoring"
            })
            actions.append({
                "action": "DECLINE_TRANSACTION",
                "route": "L1",
                "reason": "R4: Decline pending authorizations pending contact"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": "ESCALATE_TO_ANALYST",
                    "route": "auto",
                    "reason": f"R4/R8: No reply within 24h and exposure ${exposure_usd:.2f} exceeds $500 threshold"
                })

        elif verdict == "uncertain":
            # Rule R8: Escalate when uncertain and exposed
            actions.append({
                "action": "CREATE_CASE",
                "route": "auto",
                "reason": "Section 3a: Open internal fraud case to record ongoing investigation"
            })
            actions.append({
                "action": "MONITOR_CARD",
                "route": "auto",
                "reason": "Policy Section 1: Place card under 72h elevated monitoring"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": "ESCALATE_TO_ANALYST",
                    "route": "auto",
                    "reason": f"R8: Verdict is uncertain and exposure ${exposure_usd:.2f} exceeds $500 threshold"
                })

        elif verdict == "fraud" or customer_outcome in [CustomerReplyOutcome.DENIED_UNAUTHORIZED, CustomerReplyOutcome.STEP_UP_FAILED]:
            # Rule R2: Customer denies the transaction
            block_route = get_action_route("BLOCK_CARD", exposure_usd)
            actions.append({
                "action": "BLOCK_CARD",
                "route": block_route,
                "reason": f"R2: Confirmed unauthorized fraud; exposure ${exposure_usd:.2f} ({'exceeds $2,500 threshold (L2)' if exposure_usd > 2500 else 'is under $2,500 threshold (L1)'})"
            })
            actions.append({
                "action": "CREATE_CASE",
                "route": "auto",
                "reason": "R2 and Section 3a: Open internal fraud case and persist evidence to graph"
            })

            # Check Rule R10: Block all cards if multi-card compromised
            if multi_card_compromised:
                actions.append({
                    "action": "BLOCK_ALL_CARDS",
                    "route": "L2",
                    "reason": "R10: Multiple cards belonging to customer show confirmed compromise"
                })

            # Check SAR trigger rules (R2, R6, R9, Section 3a)
            # SAR is mandatory when: exposure > $1,000 OR shared origin (R6) OR undocumented pattern (R9)
            if exposure_usd > 1000.0 or has_shared_device_ring or len(connected_cards) > 0 or pattern == "undocumented":
                sar_file = True
                actions.append({
                    "action": "FILE_REPORT",
                    "route": "L2",
                    "reason": f"R2/R6/Section 3a: Mandatory SAR filing ({'Shared origin cluster detected' if (has_shared_device_ring or connected_cards) else ('Undocumented coordinated pattern' if pattern == 'undocumented' else f'Exposure ${exposure_usd:.2f} > $1,000')})"
                })
                if has_shared_device_ring or len(connected_cards) > 0:
                    sar_reason = f"R6 and Section 3a: Confirmed fraud linked to shared origin infrastructure across {len(connected_cards) + 1} cards with total exposure ${exposure_usd:.2f}"
                elif pattern == "undocumented":
                    sar_reason = f"R9 and Section 3a: Undocumented coordinated fraud pattern with exposure ${exposure_usd:.2f}"
                else:
                    sar_reason = f"R2 and Section 3a: Confirmed unauthorized fraud with total exposure ${exposure_usd:.2f} exceeding $1,000 threshold"
            else:
                sar_file = False
                sar_reason = f"Confirmed fraud exposure of ${exposure_usd:.2f} is under $1,000 threshold and no shared ring was identified"

            # Rule R6: Monitor connected cards sharing device/region/email
            if connected_cards:
                actions.append({
                    "action": "MONITOR_CONNECTED_CARDS",
                    "route": "auto",
                    "reason": f"R6: Place {len(connected_cards)} connected card(s) sharing compromised device/ring infrastructure under monitoring"
                })

            # Rule R9: Escalate undocumented pattern
            if pattern == "undocumented":
                actions.append({
                    "action": "ESCALATE_TO_ANALYST",
                    "route": "auto",
                    "reason": "R9: Undocumented fraud pattern escalated with descriptive analyst report"
                })

    return actions, sar_file, sar_reason
