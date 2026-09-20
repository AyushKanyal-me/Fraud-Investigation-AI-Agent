import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME
)

def verify_graph():
    print(f"[*] Verifying TigerGraph graph '{TG_GRAPH_NAME}'...")
    import pyTigerGraph as tg
    conn = tg.TigerGraphConnection(
        host=TG_HOST,
        restppPort=TG_RESTPP_PORT,
        gsPort=TG_GS_PORT,
        username=TG_USERNAME,
        password=TG_PASSWORD,
        graphname=TG_GRAPH_NAME
    )
    
    vertices = ["Transaction", "Card", "Customer", "Device", "EmailDomain", "Address", "Case", "EvidenceItem"]
    print("--- Vertex Counts ---")
    for v in vertices:
        try:
            cnt = conn.getVertexCount(v)
            print(f"  {v:<15}: {cnt}")
        except Exception as e:
            print(f"  {v:<15}: Error ({e})")

    edges = ["PERFORMED_BY", "OWNED_BY", "USED_DEVICE", "USED_EMAIL", "LOCATED_AT", "NEXT_TXN", "INVOLVES_CARD", "INVOLVES_CUSTOMER", "INVOLVES_TXN", "HAS_EVIDENCE"]
    print("\n--- Edge Counts ---")
    for e in edges:
        try:
            cnt = conn.getEdgeCount(e)
            print(f"  {e:<18}: {cnt}")
        except Exception as ex:
            print(f"  {e:<18}: Error ({ex})")

if __name__ == "__main__":
    verify_graph()
