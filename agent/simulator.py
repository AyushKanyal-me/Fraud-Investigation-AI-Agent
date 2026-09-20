"""
Dynamic Customer & Authentication Simulation Engine.
Simulates realistic cardholder responses and 2FA step-up authentication interactions
using LLM reasoning and contextual scenario ground truth with explicit provenance tagging.
"""

import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.policy import CustomerReplyOutcome
from agent.prompts import CUSTOMER_SIMULATOR_PROMPT

class CustomerSimulator:
    def __init__(self, llm_caller=None):
        self.llm_caller = llm_caller

    def simulate_inquiry(
        self,
        customer_id: str,
        card_id: str,
        flagged_txn_id: str,
        txn_amt: float,
        product_cd: str,
        trigger_type: str,
        risk_score: float,
        is_recurring_dispute: bool = False,
        is_new_device: bool = False,
        is_region_anomaly: bool = False,
        is_card_testing: bool = False,
        has_shared_device_ring: bool = False
    ) -> Tuple[CustomerReplyOutcome, str, str, Dict[str, Any]]:
        """
        Simulates customer interaction or 2FA step-up authentication.
        Returns:
            - outcome: CustomerReplyOutcome enum
            - inquiry_type: "customer_validation" or "step_up_auth"
            - response_text: Natural language response from customer / auth system
            - provenance: Provenance metadata dict (source, request_id, timestamp, actor_id)
        """
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Determine scenario ground truth and inquiry type
        if is_recurring_dispute:
            outcome = CustomerReplyOutcome.RECURRING_DISPUTE
            inquiry_type = "customer_validation"
            scenario_truth = f"Customer confirms they have a recurring monthly subscription agreement of ${txn_amt:.2f} with this merchant."
            default_text = f"Cardholder clarifies they recognize the recurring subscription charge of ${txn_amt:.2f} after checking their billing agreement."

        elif trigger_type == "customer_report":
            outcome = CustomerReplyOutcome.DENIED_UNAUTHORIZED
            inquiry_type = "customer_validation"
            scenario_truth = f"Customer received an SMS notification for ${txn_amt:.2f} on transaction {flagged_txn_id} and denies initiating it."
            default_text = f"Customer explicitly denies authorizing transaction {flagged_txn_id} (${txn_amt:.2f}) and states they remain in physical possession of card {card_id}."

        elif trigger_type == "analyst_request" or (has_shared_device_ring and is_new_device):
            outcome = CustomerReplyOutcome.STEP_UP_FAILED
            inquiry_type = "step_up_auth"
            scenario_truth = "High-risk device cluster activity. Automated step-up multi-factor SMS/app authentication was attempted and failed to verify."
            default_text = "Step-up multi-factor authentication failed; cardholder device fingerprint does not match authorized credentials and one-time passcode expired."

        elif is_card_testing:
            outcome = CustomerReplyOutcome.STEP_UP_FAILED
            inquiry_type = "step_up_auth"
            scenario_truth = "Micro-authorization card testing sequence observed on card. Two-factor authentication failed on primary channel."
            default_text = "Automated step-up challenge timed out without cardholder confirmation following rapid micro-authorization sequence."

        elif risk_score < 0.60 and not is_new_device and not is_region_anomaly:
            outcome = CustomerReplyOutcome.CONFIRMED_LEGITIMATE
            inquiry_type = "customer_validation"
            scenario_truth = f"Cardholder executed transaction {flagged_txn_id} (${txn_amt:.2f}) as a legitimate personal purchase."
            default_text = f"Customer validates transaction {flagged_txn_id} (${txn_amt:.2f}) as an authorized purchase made online."

        else:
            # Default suspicious alert requiring verification
            outcome = CustomerReplyOutcome.DENIED_UNAUTHORIZED
            inquiry_type = "customer_validation"
            scenario_truth = f"Customer was contacted regarding unexpected transaction {flagged_txn_id} (${txn_amt:.2f}) and reports not recognizing it."
            default_text = f"Customer states they received the fraud inquiry SMS and did not authorize the ${txn_amt:.2f} purchase on card {card_id}."

        provenance = {
            "source": "simulator",
            "request_id": request_id,
            "timestamp": timestamp,
            "actor_id": "customer_simulator_v2",
            "scenario_truth": scenario_truth
        }

        # 2. Try LLM simulation for rich conversational fidelity if LLM is callable
        if self.llm_caller:
            prompt = CUSTOMER_SIMULATOR_PROMPT.format(
                customer_id=customer_id or "CUST_UNKNOWN",
                card_id=card_id or "CARD_UNKNOWN",
                txn_id=flagged_txn_id,
                txn_amt=txn_amt,
                product_cd=product_cd or "eCommerce",
                inquiry_reason=f"Risk verification alert (score: {risk_score:.2f})",
                scenario_truth=scenario_truth
            )
            llm_reply = self.llm_caller(prompt)
            if llm_reply and len(llm_reply.strip()) > 10:
                return outcome, inquiry_type, llm_reply.strip(), provenance

        return outcome, inquiry_type, default_text, provenance
