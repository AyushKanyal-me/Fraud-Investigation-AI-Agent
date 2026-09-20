import os
import sys
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import REGULATIONS_DIR

REG_URLS = {
    "sar_guidance_narrative.pdf": "https://www.fincen.gov/system/files/shared/sar_guidance_narrative.pdf",
    "sarnarrcompletguidfinal_112003.pdf": "https://www.fincen.gov/system/files/shared/sarnarrcompletguidfinal_112003.pdf",
    "fin_2007_g003.pdf": "https://www.fincen.gov/system/files/shared/fin-2007-g003.pdf",
    "fincen_identity_2021.pdf": "https://www.fincen.gov/system/files/shared/FTA_Identity_Final508.pdf",
    "fatf_cyber_fraud.pdf": "https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Illicit-financial-flows-cyber-enabled-fraud.pdf.coredownload.inline.pdf"
}

def download_regulations():
    print(f"[*] Downloading regulatory reference documents to {REGULATIONS_DIR}...")
    REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for filename, url in REG_URLS.items():
        dest = REGULATIONS_DIR / filename
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"[i] Already downloaded: {filename}")
            continue
        print(f"[*] Fetching {filename} from {url}...")
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                with open(dest, "wb") as f:
                    f.write(resp.content)
                print(f"[+] Saved {filename} ({len(resp.content)} bytes)")
            else:
                print(f"[!] HTTP {resp.status_code} for {filename}")
        except Exception as e:
            print(f"[!] Could not download {filename}: {e}")

if __name__ == "__main__":
    download_regulations()
