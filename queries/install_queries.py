import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME
)

QUERY_FILES = [
    "card_history.gsql",
    "card_window.gsql",
    "customer_profile.gsql",
    "device_neighbors.gsql",
    "region_anomaly.gsql",
    "similar_closed_cases.gsql",
    "email_ring.gsql",
    "transaction_detail.gsql",
    "card_testing_detection.gsql",
    "write_case.gsql"
]

def install_queries():
    print(f"[*] Installing GSQL queries on TigerGraph ({TG_GRAPH_NAME})...")
    queries_dir = BASE_DIR / "queries"
    
    try:
        import pyTigerGraph as tg
        conn = tg.TigerGraphConnection(
            host=TG_HOST,
            restppPort=TG_RESTPP_PORT,
            gsPort=TG_GS_PORT,
            username=TG_USERNAME,
            password=TG_PASSWORD,
            graphname=TG_GRAPH_NAME
        )
        
        all_query_content = f"USE GRAPH {TG_GRAPH_NAME}\n"
        for q_file in QUERY_FILES:
            filepath = queries_dir / q_file
            if filepath.exists():
                with open(filepath, "r") as f:
                    all_query_content += f.read() + "\n"
        
        all_query_content += "\nINSTALL QUERY ALL\n"
        
        # Write consolidated query install script
        install_script_path = queries_dir / "all_queries.gsql"
        with open(install_script_path, "w") as f:
            f.write(all_query_content)
            
        print("[*] Running GSQL INSTALL QUERY ALL...")
        res = conn.gsql(all_query_content)
        print("[+] Query installation result:")
        print(res)
        return True
    except Exception as ex:
        print(f"[!] Error installing queries via pyTigerGraph: {ex}")
        print("[*] Attempting fallback via docker exec...")
        import subprocess
        try:
            cmd = f"docker exec -i tigergraph gsql < '{queries_dir}/all_queries.gsql'"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            print("[+] Fallback Docker GSQL execution succeeded:")
            print(out.decode())
            return True
        except Exception as dex:
            print(f"[!] Docker exec failed: {dex}")
            return False

if __name__ == "__main__":
    install_queries()
