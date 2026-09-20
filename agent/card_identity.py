import os
import sys
import pickle
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import DATASET_DIR

CACHE_FILE = BASE_DIR / "agent" / "canonical_card_map.pkl"

class CanonicalCardMapper:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CanonicalCardMapper, cls).__new__(cls)
            cls._instance._init_mapping()
        return cls._instance

    def _init_mapping(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "rb") as f:
                    self.tuple_to_card, self.txn_to_card = pickle.load(f)
                return
            except Exception:
                pass

        print("[*] Generating canonical card mapping from dataset...")
        txn_file = DATASET_DIR / "transactions.csv"
        closed_file = DATASET_DIR / "closed_cases_history.csv"
        pack_file = DATASET_DIR / "case_pack.csv"

        df_txn = pd.read_csv(txn_file, usecols=['TransactionID', 'TransactionDT', 'customer_id', 'card1', 'card2', 'card3', 'card4', 'card5', 'card6'])
        df_closed = pd.read_csv(closed_file)
        df_pack = pd.read_csv(pack_file)

        # 1. Direct anchoring from closed cases and case pack
        txn_to_card = {}
        for _, row in df_closed.iterrows():
            cid = row['card_id']
            txns = str(row.get('txn_ids', '')).split('|')
            if row.get('first_fraud_txn_id') and pd.notna(row['first_fraud_txn_id']):
                txns.append(str(int(float(row['first_fraud_txn_id']))))
            for t in txns:
                t_str = t.strip()
                if t_str:
                    txn_to_card[t_str] = cid

        for _, row in df_pack.iterrows():
            txn_to_card[str(row['flagged_txn_id'])] = row['card_id']

        # 2. Map card tuples
        df_txn['card_tuple'] = list(zip(
            df_txn['customer_id'].fillna("CUST_UNK"),
            df_txn['card1'].fillna(-1).astype(str),
            df_txn['card2'].fillna(-1).astype(str),
            df_txn['card3'].fillna(-1).astype(str),
            df_txn['card4'].fillna('unk').astype(str),
            df_txn['card5'].fillna(-1).astype(str),
            df_txn['card6'].fillna('unk').astype(str)
        ))

        tuple_to_card = {}
        for tid_str, cid in txn_to_card.items():
            try:
                tid = int(tid_str)
                m = df_txn[df_txn['TransactionID'] == tid]
                if not m.empty:
                    tuple_to_card[m.iloc[0]['card_tuple']] = cid
            except Exception:
                pass

        # 3. Assign sequential -K1, -K2 for remaining cards per customer
        cust_used_k = {}
        for (cust, *rest), cid in tuple_to_card.items():
            if cust not in cust_used_k:
                cust_used_k[cust] = set()
            try:
                k_num = int(cid.split('-K')[1])
                cust_used_k[cust].add(k_num)
            except Exception:
                pass

        for _, row in df_txn.sort_values(by='TransactionDT').iterrows():
            ctuple = row['card_tuple']
            cust = str(row['customer_id'])
            if ctuple not in tuple_to_card:
                if cust not in cust_used_k:
                    cust_used_k[cust] = set()
                next_k = 1
                while next_k in cust_used_k[cust]:
                    next_k += 1
                cust_used_k[cust].add(next_k)
                tuple_to_card[ctuple] = f"{cust}-K{next_k}"

        self.tuple_to_card = tuple_to_card
        self.txn_to_card = txn_to_card

        # Cache to disk for instant subsequent loads
        try:
            with open(CACHE_FILE, "wb") as f:
                pickle.dump((self.tuple_to_card, self.txn_to_card), f)
            print(f"[+] Canonical card map cached to {CACHE_FILE.name}")
        except Exception as e:
            print(f"[!] Cache write note: {e}")

    def get_card_id(self, customer_id: str, card1=-1, card2=-1, card3=-1, card4='unk', card5=-1, card6='unk') -> str:
        key = (
            str(customer_id) if customer_id else "CUST_UNK",
            str(card1), str(card2), str(card3), str(card4), str(card5), str(card6)
        )
        return self.tuple_to_card.get(key, f"{customer_id}-K1")

    def get_card_id_for_txn(self, txn_id: str, row: dict = None) -> str:
        if str(txn_id) in self.txn_to_card:
            return self.txn_to_card[str(txn_id)]
        if row:
            return self.get_card_id(
                row.get('customer_id'),
                row.get('card1', -1),
                row.get('card2', -1),
                row.get('card3', -1),
                row.get('card4', 'unk'),
                row.get('card5', -1),
                row.get('card6', 'unk')
            )
        return f"{row.get('customer_id', 'CUST')}-K1" if row else "CUST-K1"

def get_canonical_card_mapper():
    return CanonicalCardMapper()

if __name__ == "__main__":
    mapper = CanonicalCardMapper()
    print("Mapper test C12382:", mapper.get_card_id("C12382", 21139, 242.0, 150.0, "visa", 166.0, "debit"))
