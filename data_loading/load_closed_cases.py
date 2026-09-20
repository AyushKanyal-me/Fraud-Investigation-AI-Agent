import os
import sys
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME, DATASET_DIR
)

def get_tg_connection():
    import pyTigerGraph as tg
    conn = tg.TigerGraphConnection(
        host=TG_HOST,
        restppPort=TG_RESTPP_PORT,
        gsPort=TG_GS_PORT,
        username=TG_USERNAME,
        password=TG_PASSWORD,
        graphname=TG_GRAPH_NAME
    )
    return conn

def load_closed_cases():
    print(f"[*] Loading closed cases history into TigerGraph...")
    cases_file = DATASET_DIR / "closed_cases_history.csv"
    if not cases_file.exists():
        print(f"[!] File not found: {cases_file}")
        return

    df = pd.read_csv(cases_file)
    print(f"[*] Found {len(df)} historical closed cases.")
    
    conn = get_tg_connection()
    
    case_vertices = []
    involves_card_edges = []
    involves_cust_edges = []
    involves_txn_edges = []

    for _, row in df.iterrows():
        c_id = str(row["case_id"])
        cust_id = str(row["customer_id"]) if pd.notna(row["customer_id"]) else ""
        card_id = str(row["card_id"]) if pd.notna(row["card_id"]) else ""
        opened_at = str(row["opened_at"]) if pd.notna(row["opened_at"]) else ""
        closed_at = str(row["closed_at"]) if pd.notna(row["closed_at"]) else ""
        outcome = str(row["outcome"]) if pd.notna(row["outcome"]) else "fraud"
        pattern = str(row["pattern"]) if pd.notna(row["pattern"]) else "undocumented"
        first_txn = str(row["first_fraud_txn_id"]) if pd.notna(row["first_fraud_txn_id"]) else ""
        exposure = float(row["exposure_usd"]) if pd.notna(row["exposure_usd"]) else 0.0
        actions = str(row["actions_taken"]) if pd.notna(row["actions_taken"]) else ""
        report_filed = str(row["report_filed"]).lower() in ["true", "1", "yes", "sar_filed"]
        notes = str(row["analyst_notes"]) if pd.notna(row["analyst_notes"]) else ""

        case_vertices.append((c_id, {
            "opened_at": opened_at,
            "closed_at": closed_at,
            "outcome": outcome,
            "pattern": pattern,
            "fraud_probability": 1.0 if outcome == "fraud" else 0.0,
            "exposure_usd": exposure,
            "actions_taken": actions,
            "sar_filed": report_filed,
            "analyst_notes": notes,
            "trigger_type": "historical_trigger",
            "trigger_text": notes,
            "first_fraud_txn_id": first_txn
        }))

        if card_id:
            involves_card_edges.append((c_id, card_id, {}))
        if cust_id:
            involves_cust_edges.append((c_id, cust_id, {}))
        
        # Link transaction IDs if available
        if pd.notna(row.get("txn_ids")):
            for tid in str(row["txn_ids"]).split("|"):
                tid = tid.strip()
                if tid:
                    involves_txn_edges.append((c_id, tid, {}))

    print(f"[*] Upserting {len(case_vertices)} FraudCase vertices...")
    conn.upsertVertices("FraudCase", case_vertices)
    if involves_card_edges:
        conn.upsertEdges("FraudCase", "INVOLVES_CARD", "Card", involves_card_edges)
    if involves_cust_edges:
        conn.upsertEdges("FraudCase", "INVOLVES_CUSTOMER", "Customer", involves_cust_edges)
    if involves_txn_edges:
        conn.upsertEdges("FraudCase", "INVOLVES_TXN", "Transaction", involves_txn_edges)
        
    print(f"[+] Loaded {len(case_vertices)} closed cases and all their graph links.")

if __name__ == "__main__":
    load_closed_cases()
