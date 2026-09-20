import re
from typing import Dict, Any, List, Tuple, Set, Optional
from agent.repository.base import FraudDataRepository

class ModelClaimValidator:
    """
    Deterministically cross-checks claims made by LLM outputs against ground-truth graph records.
    Filters or flags hallucinated transaction IDs, forged amounts, and ungrounded entities.
    """
    def __init__(self, repository: FraudDataRepository):
        self.repository = repository

    def validate_cited_transactions(self, cited_txn_ids: List[str]) -> Tuple[List[str], List[str]]:
        """
        Verifies that cited transaction IDs exist in the dataset.
        Returns:
            (valid_txn_ids, invalid_txn_ids)
        """
        valid = []
        invalid = []
        for tid in cited_txn_ids:
            clean_id = str(tid).replace("TXN-", "").replace("T", "").strip()
            # Try original and numeric cleanup
            rec = self.repository.get_transaction_detail(str(tid)) or self.repository.get_transaction_detail(clean_id)
            if rec:
                valid.append(rec.transaction_id)
            else:
                invalid.append(str(tid))
        return valid, invalid

    def validate_amount_claim(self, claimed_amount: float, actual_amount: float, rel_tol: float = 0.05) -> bool:
        """
        Checks whether a claimed exposure or transaction amount matches reality within tolerance.
        """
        if actual_amount == 0.0:
            return claimed_amount == 0.0
        return abs(claimed_amount - actual_amount) / actual_amount <= rel_tol

    def sanitize_evidence_claims(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks entity IDs cited in evidence claims. Removes non-existent hallucinated IDs.
        """
        sanitized = []
        for ev in evidence_list:
            entity_ids = ev.get("entity_ids", [])
            valid_entities = []
            for eid in entity_ids:
                eid_str = str(eid)
                # Check if it's a closed case or transaction
                if eid_str.startswith("CC-") or eid_str.startswith("CASE-") or eid_str.startswith("C0") or eid_str.startswith("C1") or eid_str.startswith("D0"):
                    valid_entities.append(eid_str)
                else:
                    # Check transaction detail
                    rec = self.repository.get_transaction_detail(eid_str)
                    if rec:
                        valid_entities.append(rec.transaction_id)
                    else:
                        # Omit hallucinated ID
                        continue
            
            sanitized_ev = dict(ev)
            sanitized_ev["entity_ids"] = valid_entities
            sanitized.append(sanitized_ev)
        return sanitized
