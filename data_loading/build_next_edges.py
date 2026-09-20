import os
import sys
import pandas as pd
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
    return conn

def build_temporal_edges(batch_size=50000):
    print("[*] Building NEXT_TXN temporal edges for cards...")
    txn_file = DATASET_DIR / "transactions.csv"
    if not txn_file.exists():
        print(f"[!] File not found: {txn_file}")
        return

    print("[*] Reading transaction timestamps and card keys...")
    df = pd.read_csv(
        txn_file,
        usecols=["TransactionID", "ts", "TransactionDT", "card1", "card2", "card3", "card4", "card5", "card6"]
    )
    df["ts_val"] = df["ts"].fillna(df["TransactionDT"]).astype(int)
    df["card_id"] = (
        "CARD_" + df["card1"].fillna(-1).astype(str) + "_" +
        df["card2"].fillna(-1).astype(str) + "_" +
        df["card3"].fillna(-1).astype(str) + "_" +
        df["card4"].fillna("unknown").astype(str) + "_" +
        df["card5"].fillna(-1).astype(str) + "_" +
        df["card6"].fillna("unknown").astype(str)
    )

    print("[*] Sorting by card_id and timestamp...")
    df.sort_values(by=["card_id", "ts_val"], inplace=True)

    conn = get_tg_connection()
    edges_batch = []
    total_edges = 0

    print("[*] Generating NEXT_TXN edges...")
    prev_row = None
    for _, row in df.iterrows():
        if prev_row is not None and row["card_id"] == prev_row["card_id"]:
            time_delta = int(row["ts_val"] - prev_row["ts_val"])
            edges_batch.append((
                str(prev_row["TransactionID"]),
                str(row["TransactionID"]),
                {"time_delta_sec": time_delta}
            ))

            if len(edges_batch) >= batch_size:
                conn.upsertEdges("Transaction", "NEXT_TXN", "Transaction", edges_batch)
                total_edges += len(edges_batch)
                print(f"[+] Upserted {total_edges} NEXT_TXN edges...")
                edges_batch = []
        prev_row = row

    if edges_batch:
        conn.upsertEdges("Transaction", "NEXT_TXN", "Transaction", edges_batch)
        total_edges += len(edges_batch)

    print(f"[✓] Completed NEXT_TXN edges. Total edges: {total_edges}")

if __name__ == "__main__":
    build_temporal_edges()
