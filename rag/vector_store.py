import os
import sys
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import REGULATIONS_DIR, DATASET_DIR, POLICY_RULES, PATTERNS

class FraudVectorStore:
    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            self.persist_dir = str(BASE_DIR / "rag" / "chroma_db")
        else:
            self.persist_dir = persist_dir

        self.client = None
        self.collection = None
        self.documents = []
        self.metadatas = []
        self.ids = []
        self._init_store()

    def _init_store(self):
        try:
            import chromadb
            from chromadb.utils import embedding_functions
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name="fraud_knowledge",
                metadata={"description": "Fraud policy, regulations, and historical closed cases"}
            )
            print(f"[+] Initialized ChromaDB at {self.persist_dir}. Current document count: {self.collection.count()}")
        except Exception as e:
            print(f"[!] ChromaDB init notice: {e}. Fallback to in-memory store.")
            self.client = None

    def index_all(self):
        if self.collection is not None and self.collection.count() > 0:
            print(f"[+] Knowledge base already indexed ({self.collection.count()} docs in ChromaDB). Skipping re-embedding.")
            return

        print("[*] Indexing Policy, Historical Closed Cases, and Regulatory Guidance...")
        docs = []
        metas = []
        ids = []

        # 1. Index Bank Fraud Policy Rules
        for rule_id, rule_info in POLICY_RULES.items():
            text = f"Policy Rule {rule_id}: {rule_info['title']}.\nDescription: {rule_info['description']}\nRecommended Actions: {', '.join(rule_info['actions'])}\nSAR Trigger: {rule_info['sar_trigger']}"
            docs.append(text)
            metas.append({"category": "policy_rule", "rule_id": rule_id, "title": rule_info["title"]})
            ids.append(f"policy_{rule_id}")

        # 2. Index Fraud Pattern Definitions
        pattern_descriptions = {
            "card_testing": "Card testing involves a rapid succession of multiple small online authorizations (often <$15) within a short time window (under 1 hour) to test stolen card viability, followed by larger purchases.",
            "card_not_present_fraud": "Card Not Present (CNP) fraud involves unauthorized eCommerce / online purchases where physical card is not presented, often with mismatched billing or high velocity.",
            "card_not_present_new_device": "CNP transaction executed from an unprecedented / new DeviceID, OS, or browser profile, especially with high dollar amount or unexpected product category.",
            "out_of_region_use": "Geographic anomaly where transaction occurs in a distinct billing address (addr1/addr2) or distant region within impossible travel time from home region.",
            "account_takeover": "Account takeover occurs when credentials/emails/devices are modified or unauthorized logins occur, followed by high-value transactions or password changes.",
            "undocumented": "Emerging or coordinated multi-party fraud patterns not falling into standard known categories (e.g. cross-card merchant rings, synthetic identity clusters).",
            "none": "Legitimate transaction conforming to historical customer behavior, known devices, and regular geographic patterns."
        }
        for pat, desc in pattern_descriptions.items():
            docs.append(f"Fraud Pattern: {pat}\nCharacteristics: {desc}")
            metas.append({"category": "fraud_pattern", "pattern": pat})
            ids.append(f"pattern_{pat}")

        # 3. Index ALL Historical Closed Cases
        closed_cases_file = DATASET_DIR / "closed_cases_history.csv"
        if closed_cases_file.exists():
            print(f"[*] Indexing all historical closed cases from {closed_cases_file}...")
            df = pd.read_csv(closed_cases_file)
            for _, row in df.iterrows():
                cid = str(row["case_id"])
                notes = str(row["analyst_notes"]) if pd.notna(row["analyst_notes"]) else ""
                pattern = str(row["pattern"]) if pd.notna(row["pattern"]) else "undocumented"
                outcome = str(row["outcome"]) if pd.notna(row["outcome"]) else "fraud"
                exp = float(row.get("exposure_usd", 0.0)) if pd.notna(row.get("exposure_usd")) else 0.0
                card_id = str(row.get("card_id", ""))
                cust_id = str(row.get("customer_id", ""))
                
                text = f"Closed Case {cid} (Card: {card_id}, Customer: {cust_id}):\nOutcome: {outcome}\nPattern: {pattern}\nExposure: ${exp:.2f}\nNotes: {notes}"
                docs.append(text)
                metas.append({
                    "category": "closed_case",
                    "case_id": cid,
                    "card_id": card_id,
                    "customer_id": cust_id,
                    "pattern": pattern,
                    "outcome": outcome,
                    "exposure_usd": exp
                })
                ids.append(f"case_{cid}")

        # 4. Index Regulatory Guidelines (FinCEN SAR Guidance)
        fincen_summary = (
            "FinCEN Suspicious Activity Report (SAR) Narrative Standards: "
            "A complete and sufficient SAR narrative must stand on its own and clearly articulate "
            "the 5 Ws and H: Who conducted the activity (subjects, cards, accounts), What took place (specific transactions, amounts), "
            "When did it happen (exact dates/times), Where did it occur (channels, IP addresses, billing regions), "
            "How was the suspicious activity executed (card testing sequence, device spoofing, rapid velocity), "
            "and Why is it suspicious (violation of policy, deviation from baseline, connection to confirmed fraud rings)."
        )
        docs.append(fincen_summary)
        metas.append({"category": "regulation", "source": "FinCEN"})
        ids.append("reg_fincen_sar_narrative")

        # Add to ChromaDB if available
        if self.collection is not None:
            batch_size = 500
            for i in range(0, len(docs), batch_size):
                end_i = min(i + batch_size, len(docs))
                self.collection.upsert(
                    documents=docs[i:end_i],
                    metadatas=metas[i:end_i],
                    ids=ids[i:end_i]
                )
            print(f"[✓] Successfully indexed {len(docs)} documents in Vector Store.")
        else:
            self.documents = docs
            self.metadatas = metas
            self.ids = ids
            print(f"[✓] Stored {len(docs)} documents in-memory.")

    def search(self, query: str, n_results: int = 5, category: str = None) -> List[Dict[str, Any]]:
        results = []
        if self.collection is not None and self.collection.count() > 0:
            where_clause = {"category": category} if category else None
            try:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_clause
                )
                if res and "documents" in res and res["documents"]:
                    docs = res["documents"][0]
                    metas = res["metadatas"][0] if "metadatas" in res else [{}] * len(docs)
                    for d, m in zip(docs, metas):
                        results.append({"text": d, "metadata": m})
                return results
            except Exception as e:
                print(f"[!] Vector query error: {e}")

        # Fallback simple keyword match if ChromaDB unavailable
        q_lower = query.lower()
        scored = []
        for d, m in zip(self.documents, self.metadatas):
            if category and m.get("category") != category:
                continue
            words = q_lower.split()
            score = sum(1 for w in words if w in d.lower())
            if score > 0:
                scored.append((score, d, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, d, m in scored[:n_results]:
            results.append({"text": d, "metadata": m})
        return results

if __name__ == "__main__":
    store = FraudVectorStore()
    store.index_all()
    test_results = store.search("card testing small amounts under 15 dollars", n_results=2)
    print("\n--- Search Test Result ---")
    for r in test_results:
        print(f"[{r['metadata'].get('category')}] {r['text'][:150]}...\n")
