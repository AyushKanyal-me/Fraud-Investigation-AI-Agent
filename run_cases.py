import os
import sys
import json
import time
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import DATASET_DIR, ANSWERS_DIR
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.tools import GraphTools
from agent.workflow import FraudInvestigationWorkflow
from output.validator import CaseValidator

def run_all_cases():
    print("=" * 70)
    print(" TigerGraph Agentic Fraud Investigation System - Hacker House Goa")
    print("=" * 70)

    # 1. Initialize RAG Vector Store
    print("\n[1/5] Initializing GraphRAG Vector Store & Policy Precedents...")
    vector_store = FraudVectorStore()
    vector_store.index_all()

    # 2. Initialize Case Memory
    print("\n[2/5] Initializing Cross-Case Memory System...")
    memory = CaseMemory()

    # 3. Initialize Graph Tools and Workflow
    print("\n[3/5] Loading Graph Tools & Fast Execution Engine...")
    tools = GraphTools(vector_store=vector_store)
    workflow = FraudInvestigationWorkflow(tools=tools, memory=memory)

    # 4. Load Case Pack
    case_pack_file = DATASET_DIR / "case_pack.csv"
    if not case_pack_file.exists():
        print(f"[!] Error: case_pack.csv not found at {case_pack_file}")
        return

    df_cases = pd.read_csv(case_pack_file)
    print(f"\n[4/5] Loaded {len(df_cases)} cases from {case_pack_file.name}. Processing chronologically...")

    # Ensure destination directories exist
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    cases_dir = BASE_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    results = []
    validator = CaseValidator()
    all_valid = True

    # 5. Process Each Case
    print("\n" + "-" * 70)
    for idx, (_, row) in enumerate(df_cases.iterrows(), 1):
        case_id = str(row["case_id"])
        opened_at = str(row["opened_at"])
        trigger_type = str(row["trigger_type"])
        print(f"\n>>> Investigating Case [{idx}/{len(df_cases)}]: {case_id} (Opened: {opened_at}, Trigger: {trigger_type})")

        case_output = workflow.run_investigation(row.to_dict())
        results.append(case_output)

        # Write output file in answers/ and cases/
        out_file_1 = ANSWERS_DIR / f"{case_id}.json"
        out_file_2 = cases_dir / f"{case_id}.json"
        
        with open(out_file_1, "w") as f:
            json.dump(case_output, f, indent=2)
        with open(out_file_2, "w") as f:
            json.dump(case_output, f, indent=2)

        # Validate
        is_valid, errors, warnings = validator.validate_case(case_output, case_id_expected=case_id)
        if not is_valid:
            all_valid = False
            print(f"  [!] Validation FAILED for {case_id}: {errors}")
        else:
            print(f"  [✓] Verdict: {case_output['case']['verdict'].upper()} | Pattern: {case_output['case']['pattern']} | Prob: {case_output['case']['fraud_probability']:.2f} | SAR: {case_output['sar']['file']} | Latency: {case_output['latency_s']}s")
            if warnings:
                print(f"      Warnings: {warnings}")

    print("\n" + "=" * 70)
    print(f" Investigation Complete! {len(results)} cases processed.")
    print(f" Validation Status: {'ALL VALID ✓' if all_valid else 'ERRORS ENCOUNTERED !'}")
    print(f" Output files saved to:")
    print(f"  - {ANSWERS_DIR}")
    print(f"  - {cases_dir}")
    print("=" * 70)

if __name__ == "__main__":
    run_all_cases()
