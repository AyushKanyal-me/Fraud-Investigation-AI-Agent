import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

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
    try:
        secret = conn.createSecret()
        conn.getToken(secret)
    except Exception as e:
        pass
    return conn

def load_transactions_and_entities(batch_size=50000, limit=None):
    print(f"[*] Starting Data Loading from {DATASET_DIR}...")
    conn = get_tg_connection()

    # Load Identity Data first for fast lookup
    identity_file = DATASET_DIR / "identity.csv"
    id_map = {}
    if identity_file.exists():
        print(f"[*] Loading identity.csv into memory...")
        id_df = pd.read_csv(identity_file, usecols=["TransactionID", "DeviceType", "DeviceInfo"])
        id_df["DeviceType"] = id_df["DeviceType"].fillna("unknown")
        id_df["DeviceInfo"] = id_df["DeviceInfo"].fillna("unknown")
        for _, row in id_df.iterrows():
            id_map[str(row["TransactionID"])] = (str(row["DeviceType"]), str(row["DeviceInfo"]))
        print(f"[+] Loaded {len(id_map)} identity records.")

    # Load Transactions
    txn_file = DATASET_DIR / "transactions.csv"
    if not txn_file.exists():
        print(f"[!] File not found: {txn_file}")
        return

    print(f"[*] Streaming transactions from {txn_file}...")
    chunk_iter = pd.read_csv(
        txn_file,
        chunksize=batch_size,
        dtype={
            "TransactionID": str,
            "TransactionAmt": float,
            "ts": "Int64",
            "channel": str,
            "risk_score": float,
            "ProductCD": str,
            "card1": "Int64",
            "card2": "Int64",
            "card3": "Int64",
            "card4": str,
            "card5": "Int64",
            "card6": str,
            "addr1": "Int64",
            "addr2": "Int64",
            "dist1": float,
            "dist2": float,
            "P_emaildomain": str,
            "R_emaildomain": str,
            "customer_id": str
        },
        nrows=limit
    )

    total_loaded = 0
    cards_dict = {}
    customers_dict = {}
    devices_dict = {}
    emails_set = set()
    addresses_set = set()

    for chunk in chunk_iter:
        txn_vertices = []
        card_vertices = {}
        cust_vertices = {}
        dev_vertices = {}
        email_vertices = {}
        addr_vertices = {}

        # Edges
        perf_edges = []
        owned_edges = []
        dev_edges = []
        email_edges = []
        addr_edges = []

        for _, row in chunk.iterrows():
            txn_id = str(row["TransactionID"])
            amt = float(row["TransactionAmt"]) if pd.notna(row["TransactionAmt"]) else 0.0
            ts = int(row["ts"]) if pd.notna(row["ts"]) else int(row.get("TransactionDT", 0))
            channel = str(row["channel"]) if pd.notna(row["channel"]) else "web"
            risk_score = float(row["risk_score"]) if pd.notna(row["risk_score"]) else 0.0
            product_cd = str(row["ProductCD"]) if pd.notna(row["ProductCD"]) else "W"
            
            c1 = int(row["card1"]) if pd.notna(row["card1"]) else -1
            c2 = int(row["card2"]) if pd.notna(row["card2"]) else -1
            c3 = int(row["card3"]) if pd.notna(row["card3"]) else -1
            c4 = str(row["card4"]) if pd.notna(row["card4"]) else "unknown"
            c5 = int(row["card5"]) if pd.notna(row["card5"]) else -1
            c6 = str(row["card6"]) if pd.notna(row["card6"]) else "unknown"
            
            a1 = int(row["addr1"]) if pd.notna(row["addr1"]) else -1
            a2 = int(row["addr2"]) if pd.notna(row["addr2"]) else -1
            d1 = float(row["dist1"]) if pd.notna(row["dist1"]) else -1.0
            d2 = float(row["dist2"]) if pd.notna(row["dist2"]) else -1.0
            
            p_email = str(row["P_emaildomain"]) if pd.notna(row["P_emaildomain"]) else "unknown"
            r_email = str(row["R_emaildomain"]) if pd.notna(row["R_emaildomain"]) else "unknown"
            cust_id = str(row["customer_id"]) if pd.notna(row["customer_id"]) else f"CUST_{c1}"
            
            # Card ID construction
            card_id = f"CARD_{c1}_{c2}_{c3}_{c4}_{c5}_{c6}"
            
            # Device Info from identity
            dev_type, dev_info = id_map.get(txn_id, ("unknown", "unknown"))
            dev_id = f"DEV_{dev_type}_{dev_info}".replace(" ", "_")

            # Vertices
            txn_vertices.append((txn_id, {
                "amount": amt,
                "ts": ts,
                "channel": channel,
                "risk_score": risk_score,
                "ProductCD": product_cd,
                "card1": c1,
                "card2": c2,
                "card3": c3,
                "card4": c4,
                "card5": c5,
                "card6": c6,
                "addr1": a1,
                "addr2": a2,
                "dist1": d1,
                "dist2": d2,
                "P_emaildomain": p_email,
                "R_emaildomain": r_email,
                "DeviceType": dev_type,
                "DeviceInfo": dev_info,
                "customer_id": cust_id
            }))

            if card_id not in card_vertices:
                card_vertices[card_id] = {
                    "card1": c1, "card2": c2, "card3": c3,
                    "card4": c4, "card5": c5, "card6": c6,
                    "primary_addr1": a1, "primary_addr2": a2
                }

            if cust_id not in cust_vertices:
                cust_vertices[cust_id] = {
                    "primary_email": p_email,
                    "primary_device": dev_id,
                    "total_cases": 0,
                    "risk_profile": "standard"
                }

            if dev_id not in dev_vertices and dev_id != "DEV_unknown_unknown":
                dev_vertices[dev_id] = {
                    "device_type": dev_type,
                    "device_info": dev_info,
                    "first_seen": ts,
                    "last_seen": ts
                }

            if p_email not in email_vertices and p_email != "unknown":
                email_vertices[p_email] = {
                    "domain": p_email,
                    "is_disposable": False
                }

            if a1 != -1 or a2 != -1:
                addr_id = f"ADDR_{a1}_{a2}"
                if addr_id not in addr_vertices:
                    addr_vertices[addr_id] = {"addr1": a1, "addr2": a2}
                addr_edges.append((txn_id, addr_id, {}))

            # Edges
            perf_edges.append((txn_id, card_id, {}))
            owned_edges.append((card_id, cust_id, {}))
            if dev_id != "DEV_unknown_unknown":
                dev_edges.append((txn_id, dev_id, {}))
            if p_email != "unknown":
                email_edges.append((txn_id, p_email, {}))

        # Bulk upsert to TigerGraph
        try:
            conn.upsertVertices("Transaction", txn_vertices)
            conn.upsertVertices("Card", list(card_vertices.items()))
            conn.upsertVertices("Customer", list(cust_vertices.items()))
            if dev_vertices:
                conn.upsertVertices("Device", list(dev_vertices.items()))
            if email_vertices:
                conn.upsertVertices("EmailDomain", list(email_vertices.items()))
            if addr_vertices:
                conn.upsertVertices("Address", list(addr_vertices.items()))

            conn.upsertEdges("Transaction", "PERFORMED_BY", "Card", [(e[0], e[1], e[2]) for e in perf_edges])
            conn.upsertEdges("Card", "OWNED_BY", "Customer", [(e[0], e[1], e[2]) for e in owned_edges])
            if dev_edges:
                conn.upsertEdges("Transaction", "USED_DEVICE", "Device", [(e[0], e[1], e[2]) for e in dev_edges])
            if email_edges:
                conn.upsertEdges("Transaction", "USED_EMAIL", "EmailDomain", [(e[0], e[1], e[2]) for e in email_edges])
            if addr_edges:
                conn.upsertEdges("Transaction", "LOCATED_AT", "Address", [(e[0], e[1], e[2]) for e in addr_edges])

            total_loaded += len(chunk)
            print(f"[+] Loaded batch: {len(chunk)} transactions. Cumulative: {total_loaded}")
        except Exception as err:
            print(f"[!] Batch upsert error: {err}")

    print(f"[✓] Data loading complete. Total transactions processed: {total_loaded}")

if __name__ == "__main__":
    load_transactions_and_entities()
