import enum
from typing import List, Dict, Any, Tuple, Optional

POLICY_VERSION = "2026.1.0"

class CaseStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED_FRAUD = "closed_fraud"
    CLOSED_LEGITIMATE = "closed_legitimate"
    ESCALATED = "escalated"

class CaseVerdict(str, enum.Enum):
    FRAUD = "fraud"
    LEGITIMATE = "legitimate"
    UNCERTAIN = "uncertain"

class FraudPattern(str, enum.Enum):
    CARD_TESTING = "card_testing"
    CARD_NOT_PRESENT_FRAUD = "card_not_present_fraud"
    CARD_NOT_PRESENT_NEW_DEVICE = "card_not_present_new_device"
    OUT_OF_REGION_USE = "out_of_region_use"
    ACCOUNT_TAKEOVER = "account_takeover"
    UNDOCUMENTED = "undocumented"
    NONE = "none"

class ActionType(str, enum.Enum):
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"

class ApprovalRoute(str, enum.Enum):
    AUTO = "auto"
    L1 = "L1"
    L2 = "L2"

class CustomerReplyOutcome(str, enum.Enum):
    CONFIRMED_LEGITIMATE = "CONFIRMED_LEGITIMATE"
    DENIED_UNAUTHORIZED = "DENIED_UNAUTHORIZED"
    NO_REPLY_24H = "NO_REPLY_24H"
    RECURRING_DISPUTE = "RECURRING_DISPUTE"
    STEP_UP_FAILED = "STEP_UP_FAILED"
    STEP_UP_PASSED = "STEP_UP_PASSED"
    NO_REQUEST = "NO_REQUEST"

class EvidenceSource(str, enum.Enum):
    GRAPH = "graph"
    DOCUMENT = "document"
    CUSTOMER = "customer"
    EXTERNAL = "external"
    SIMULATOR = "simulator"

# Canonical lists derived directly from enums (single-source of truth)
PATTERNS: List[str] = [p.value for p in FraudPattern]
ACTION_TYPES: List[str] = [a.value for a in ActionType]
APPROVAL_ROUTES: List[str] = [r.value for r in ApprovalRoute]

# Canonical Policy Rules Definition (Dataset/README.md R1-R10)
POLICY_RULES: Dict[str, Dict[str, Any]] = {
    "R1": {
        "id": "R1",
        "title": "Verify Before Blocking on Weak Signal",
        "description": "If the case rests on a single signal (including risk score alone) and assessed fraud probability is below 0.70, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate customer on one signal is a policy breach.",
        "actions": [ActionType.VERIFY_WITH_CUSTOMER.value, ActionType.STEP_UP_AUTH.value],
        "sar_trigger": False
    },
    "R2": {
        "id": "R2",
        "title": "Customer Denies Transaction",
        "description": "Customer denies the transaction. Recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud.",
        "actions": [ActionType.BLOCK_CARD.value, ActionType.CREATE_CASE.value, ActionType.FILE_REPORT.value],
        "sar_trigger": True
    },
    "R3": {
        "id": "R3",
        "title": "Customer Confirms Transaction",
        "description": "Customer confirms the transaction. Recommend CLOSE_NO_FRAUD and ALLOW_TRANSACTION. Note the confirmation in the case file.",
        "actions": [ActionType.ALLOW_TRANSACTION.value, ActionType.CLOSE_NO_FRAUD.value],
        "sar_trigger": False
    },
    "R4": {
        "id": "R4",
        "title": "No Customer Reply Within 24 Hours",
        "description": "No reply within 24 hours. Recommend MONITOR_CARD and DECLINE_TRANSACTION for pending authorizations. Escalate (ESCALATE_TO_ANALYST) if exposure exceeds $500.",
        "actions": [ActionType.MONITOR_CARD.value, ActionType.DECLINE_TRANSACTION.value, ActionType.ESCALATE_TO_ANALYST.value],
        "sar_trigger": False
    },
    "R5": {
        "id": "R5",
        "title": "Card Testing Pattern",
        "description": "Three or more small online authorizations on one card within an hour, followed by a larger purchase: recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a purchase over $100 has already cleared, recommend BLOCK_CARD.",
        "actions": [ActionType.DECLINE_TRANSACTION.value, ActionType.STEP_UP_AUTH.value, ActionType.BLOCK_CARD.value],
        "sar_trigger": False
    },
    "R6": {
        "id": "R6",
        "title": "Shared Origin Across Cards",
        "description": "When several cards show fraud from the same device profile, billing region, or recipient email in one window, name shared element, recommend CREATE_CASE, FILE_REPORT, and MONITOR_CONNECTED_CARDS for every card that shares it.",
        "actions": [ActionType.CREATE_CASE.value, ActionType.FILE_REPORT.value, ActionType.MONITOR_CONNECTED_CARDS.value],
        "sar_trigger": True
    },
    "R7": {
        "id": "R7",
        "title": "Disputed But Legitimate Recurring Pattern",
        "description": "When customer disputes a charge that matches their recurring pattern (same merchant, amount, monthly), recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, and WARN_CUSTOMER. Do not block. Final resolution closes as CLOSE_NO_FRAUD.",
        "actions": [ActionType.CREATE_CASE.value, ActionType.VERIFY_WITH_CUSTOMER.value, ActionType.WARN_CUSTOMER.value, ActionType.CLOSE_NO_FRAUD.value],
        "sar_trigger": False
    },
    "R8": {
        "id": "R8",
        "title": "Escalate When Uncertain and Exposed",
        "description": "If verdict is uncertain and exposure exceeds $500, or evidence conflicts, recommend ESCALATE_TO_ANALYST.",
        "actions": [ActionType.CREATE_CASE.value, ActionType.MONITOR_CARD.value, ActionType.ESCALATE_TO_ANALYST.value],
        "sar_trigger": False
    },
    "R9": {
        "id": "R9",
        "title": "Undocumented Fraud Patterns",
        "description": "When activity fits none of the known patterns but evidence shows coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST, and describe pattern in own words.",
        "actions": [ActionType.CREATE_CASE.value, ActionType.FILE_REPORT.value, ActionType.ESCALATE_TO_ANALYST.value],
        "sar_trigger": True
    },
    "R10": {
        "id": "R10",
        "title": "Restrictions on Blocking All Cards",
        "description": "Never BLOCK_ALL_CARDS unless at least two of customer's cards show confirmed fraud or customer's credentials are confirmed compromised.",
        "actions": [ActionType.BLOCK_ALL_CARDS.value],
        "sar_trigger": False
    }
}

def generate_policy_prompt_section() -> str:
    """Generates a formatted summary of canonical policy rules for LLM prompts."""
    lines = ["CANONICAL POLICY RULES (R1-R10):"]
    for rid, rdata in sorted(POLICY_RULES.items()):
        lines.append(f"- {rdata['id']}: {rdata['title']} -> {rdata['description']}")
    return "\n".join(lines)


def get_action_route(action: str, exposure_usd: float = 0.0) -> str:
    """
    Returns exact approval route ('auto', 'L1', 'L2') strictly defined by Section 2:
    - auto: ALLOW_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER, 
            VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, GENERATE_REPORT, CREATE_CASE, 
            ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD
    - L1:   DECLINE_TRANSACTION; BLOCK_CARD when exposure <= $2,500
    - L2:   BLOCK_CARD when exposure > $2,500; BLOCK_ALL_CARDS always; FILE_REPORT always
    """
    action_str = str(action)
    if action_str in [
        ActionType.ALLOW_TRANSACTION.value,
        ActionType.MONITOR_CARD.value,
        ActionType.MONITOR_CONNECTED_CARDS.value,
        ActionType.WARN_CUSTOMER.value,
        ActionType.VERIFY_WITH_CUSTOMER.value,
        ActionType.STEP_UP_AUTH.value,
        ActionType.GENERATE_REPORT.value,
        ActionType.CREATE_CASE.value,
        ActionType.ESCALATE_TO_ANALYST.value,
        ActionType.CLOSE_NO_FRAUD.value,
    ]:
        return ApprovalRoute.AUTO.value
    elif action_str == ActionType.DECLINE_TRANSACTION.value:
        return ApprovalRoute.L1.value
    elif action_str == ActionType.BLOCK_CARD.value:
        if exposure_usd > 2500.0:
            return ApprovalRoute.L2.value
        return ApprovalRoute.L1.value
    elif action_str in [ActionType.BLOCK_ALL_CARDS.value, ActionType.FILE_REPORT.value]:
        return ApprovalRoute.L2.value
    return ApprovalRoute.AUTO.value

def evaluate_policy_rules(
    stage: str,  # "initial" or "final"
    verdict: str,  # "fraud", "legitimate", "uncertain"
    fraud_prob: float,
    pattern: str,
    exposure_usd: float,
    connected_cards: Optional[List[str]] = None,
    has_shared_device_ring: bool = False,
    is_card_testing: bool = False,
    testing_cleared_gt_100: bool = False,
    is_recurring_dispute: bool = False,
    customer_outcome: CustomerReplyOutcome = CustomerReplyOutcome.NO_REQUEST,
    multi_card_compromised: bool = False
) -> Tuple[List[Dict[str, str]], bool, str]:
    """
    Evaluates bank policy rules R1-R10 to produce exact actions, approval routes, and SAR decisions.
    
    Returns:
        (actions, sar_file, sar_reason)
    """
    connected_cards = connected_cards or []
    actions: List[Dict[str, str]] = []
    sar_file = False
    sar_reason = ""

    if stage == "initial":
        # Initial recommendation (before evidence request reply)
        if is_recurring_dispute:
            actions.append({
                "action": ActionType.CREATE_CASE.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Recurring subscription dispute investigation"
            })
            actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Verify recurring transaction terms with customer before blocking"
            })
            actions.append({
                "action": ActionType.WARN_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Send recurring charge notice to customer"
            })
        elif verdict == CaseVerdict.LEGITIMATE.value or (fraud_prob <= 0.15 and customer_outcome == CustomerReplyOutcome.NO_REQUEST):
            actions.append({
                "action": ActionType.ALLOW_TRANSACTION.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "Policy Section 1: Transaction conforms to historical spending baseline"
            })
            actions.append({
                "action": ActionType.CLOSE_NO_FRAUD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "Policy Section 1: Alert evaluated as legitimate cardholder activity"
            })
        elif is_card_testing or pattern == FraudPattern.CARD_TESTING.value:
            actions.append({
                "action": ActionType.DECLINE_TRANSACTION.value,
                "route": ApprovalRoute.L1.value,
                "reason": "R5: Micro-authorization testing sequence observed; decline pending authorizations"
            })
            if testing_cleared_gt_100:
                actions.append({
                    "action": ActionType.BLOCK_CARD.value,
                    "route": get_action_route(ActionType.BLOCK_CARD.value, exposure_usd),
                    "reason": "R5: Testing sequence observed and purchase over $100 has already cleared"
                })
            else:
                actions.append({
                    "action": ActionType.STEP_UP_AUTH.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": "R5: Require step-up multi-factor authentication following card testing activity"
                })
        elif fraud_prob < 0.70:
            # Rule R1: Verify before you block on a weak signal
            actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": f"R1: Assessed fraud probability {fraud_prob:.2f} is below 0.70 on initial alert; verify before blocking to prevent policy breach"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": ActionType.MONITOR_CARD.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": "Policy Section 1: Elevate card monitoring sensitivity for 72 hours pending reply"
                })
        else:
            # High probability initial signal (>= 0.70)
            actions.append({
                "action": ActionType.DECLINE_TRANSACTION.value,
                "route": ApprovalRoute.L1.value,
                "reason": "Policy Section 1: Decline authorization on high risk alert"
            })
            actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R1: Verify with customer to confirm unauthorized compromise"
            })

    elif stage == "final":
        # Final recommendation after evidence request response
        if is_recurring_dispute:
            actions.append({
                "action": ActionType.CREATE_CASE.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Record recurring billing dispute in internal graph case"
            })
            actions.append({
                "action": ActionType.WARN_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Customer reminded of recurring merchant billing terms"
            })
            actions.append({
                "action": ActionType.CLOSE_NO_FRAUD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R7: Activity matches monthly recurring schedule; closed without card block"
            })
            sar_file = False
            sar_reason = "Recurring subscription billing dispute resolved without fraud indicator"

        elif customer_outcome == CustomerReplyOutcome.CONFIRMED_LEGITIMATE or verdict == CaseVerdict.LEGITIMATE.value:
            actions.append({
                "action": ActionType.ALLOW_TRANSACTION.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R3: Customer confirmed the transaction as authorized"
            })
            actions.append({
                "action": ActionType.CLOSE_NO_FRAUD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R3: Alert closed as legitimate following cardholder confirmation"
            })
            sar_file = False
            sar_reason = "Transaction confirmed legitimate by cardholder; no suspicious activity report filed"

        elif customer_outcome == CustomerReplyOutcome.NO_REPLY_24H:
            # Rule R4: No reply within 24 hours
            actions.append({
                "action": ActionType.MONITOR_CARD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R4: Cardholder unreachable within 24 hours; elevate card monitoring"
            })
            actions.append({
                "action": ActionType.DECLINE_TRANSACTION.value,
                "route": ApprovalRoute.L1.value,
                "reason": "R4: Decline pending authorizations pending contact"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": ActionType.ESCALATE_TO_ANALYST.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R4/R8: No reply within 24h and exposure ${exposure_usd:.2f} exceeds $500 threshold"
                })
            sar_file = False
            sar_reason = "No customer reply received within 24 hours; escalated to analyst for manual review"

        elif verdict == CaseVerdict.UNCERTAIN.value:
            # Rule R8: Escalate when uncertain and exposed
            actions.append({
                "action": ActionType.CREATE_CASE.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "Section 3a: Open internal fraud case to record ongoing investigation"
            })
            actions.append({
                "action": ActionType.MONITOR_CARD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "Policy Section 1: Place card under 72h elevated monitoring"
            })
            if exposure_usd > 500.0:
                actions.append({
                    "action": ActionType.ESCALATE_TO_ANALYST.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R8: Verdict is uncertain and exposure ${exposure_usd:.2f} exceeds $500 threshold"
                })
            sar_file = False
            sar_reason = f"Investigation verdict uncertain with exposure ${exposure_usd:.2f}; referred for analyst evaluation"

        elif verdict == CaseVerdict.FRAUD.value or customer_outcome in [
            CustomerReplyOutcome.DENIED_UNAUTHORIZED,
            CustomerReplyOutcome.STEP_UP_FAILED
        ]:
            # Rule R2: Customer denies the transaction
            block_route = get_action_route(ActionType.BLOCK_CARD.value, exposure_usd)
            actions.append({
                "action": ActionType.BLOCK_CARD.value,
                "route": block_route,
                "reason": f"R2: Confirmed unauthorized fraud; exposure ${exposure_usd:.2f} ({'exceeds $2,500 threshold (L2)' if exposure_usd > 2500 else 'is under $2,500 threshold (L1)'})"
            })
            actions.append({
                "action": ActionType.CREATE_CASE.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R2 and Section 3a: Open internal fraud case and persist evidence to graph"
            })

            # Check Rule R10: Block all cards if multi-card compromised
            if multi_card_compromised:
                actions.append({
                    "action": ActionType.BLOCK_ALL_CARDS.value,
                    "route": ApprovalRoute.L2.value,
                    "reason": "R10: Multiple cards belonging to customer show confirmed compromise"
                })

            # Check SAR trigger rules (R2, R6, R9, Section 3a)
            # SAR is mandatory when: exposure > $1,000 OR shared origin (R6) OR undocumented pattern (R9)
            if exposure_usd > 1000.0 or has_shared_device_ring or len(connected_cards) > 0 or pattern == FraudPattern.UNDOCUMENTED.value:
                sar_file = True
                actions.append({
                    "action": ActionType.FILE_REPORT.value,
                    "route": ApprovalRoute.L2.value,
                    "reason": f"R2/R6/Section 3a: Mandatory SAR filing ({'Shared origin cluster detected' if (has_shared_device_ring or connected_cards) else ('Undocumented coordinated pattern' if pattern == FraudPattern.UNDOCUMENTED.value else f'Exposure ${exposure_usd:.2f} > $1,000')})"
                })
                if has_shared_device_ring or len(connected_cards) > 0:
                    sar_reason = f"R6 and Section 3a: Confirmed fraud linked to shared origin infrastructure across {len(connected_cards) + 1} cards with total exposure ${exposure_usd:.2f}"
                elif pattern == FraudPattern.UNDOCUMENTED.value:
                    sar_reason = f"R9 and Section 3a: Undocumented coordinated fraud pattern with exposure ${exposure_usd:.2f}"
                else:
                    sar_reason = f"R2 and Section 3a: Confirmed unauthorized fraud with total exposure ${exposure_usd:.2f} exceeding $1,000 threshold"
            else:
                sar_file = False
                sar_reason = f"Confirmed fraud exposure of ${exposure_usd:.2f} is under $1,000 threshold and no shared ring was identified"

            # Rule R6: Monitor connected cards sharing device/region/email
            if connected_cards:
                actions.append({
                    "action": ActionType.MONITOR_CONNECTED_CARDS.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R6: Place {len(connected_cards)} connected card(s) sharing compromised device/ring infrastructure under monitoring"
                })

            # Rule R9: Escalate undocumented pattern
            if pattern == FraudPattern.UNDOCUMENTED.value:
                actions.append({
                    "action": ActionType.ESCALATE_TO_ANALYST.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": "R9: Undocumented fraud pattern escalated with descriptive analyst report"
                })

    return actions, sar_file, sar_reason
