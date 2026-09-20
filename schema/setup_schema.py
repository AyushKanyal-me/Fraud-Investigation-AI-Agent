import os
import sys
import time
import requests
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    TG_HOST, TG_RESTPP_PORT, TG_GS_PORT, TG_USERNAME, TG_PASSWORD, TG_GRAPH_NAME
)

def create_schema():
    print(f"[*] Initializing Schema on TigerGraph at {TG_HOST}...")
    try:
        import pyTigerGraph as tg
        conn = tg.TigerGraphConnection(
            host=TG_HOST,
            restppPort=TG_RESTPP_PORT,
            gsPort=TG_GS_PORT,
            username=TG_USERNAME,
            password=TG_PASSWORD
        )
        
        schema_file = BASE_DIR / "schema" / "create_schema.gsql"
        with open(schema_file, "r") as f:
            gsql_script = f.read()

        print("[*] Executing GSQL schema script...")
        res = conn.gsql(gsql_script)
        print("[+] Schema creation response:")
        print(res)
        
        # Test connection with graph name
        conn.graphname = TG_GRAPH_NAME
        # Get secret / token if required
        try:
            secret = conn.createSecret()
            token = conn.getToken(secret)
            print(f"[+] Successfully authenticated to graph '{TG_GRAPH_NAME}'. Token acquired.")
        except Exception as e:
            print(f"[i] Note on secret/token: {e}")
            
        print("[+] Schema setup completed successfully.")
        return True
    except Exception as ex:
        print(f"[!] Error creating schema via pyTigerGraph: {ex}")
        print("[*] Attempting fallback via docker exec...")
        import subprocess
        try:
            cmd = f"docker exec -i tigergraph gsql < '{BASE_DIR}/schema/create_schema.gsql'"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            print("[+] Fallback Docker GSQL execution succeeded:")
            print(out.decode())
            return True
        except Exception as dex:
            print(f"[!] Docker exec failed: {dex}")
            return False

if __name__ == "__main__":
    create_schema()
