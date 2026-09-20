import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CASES_DIR = BASE_DIR / "cases"
BASELINE_DIR = BASE_DIR / "tests" / "baseline"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

def record_pre_migration_baseline():
    results = {}
    summary_lines = [
        "# Pre-Migration Baseline Benchmark Summary",
        "",
        "| Case ID | Trigger Type | Verdict | Probability | Pattern | Exposure ($) | SAR File | Initial Actions | Final Actions | Approval Routes |",
        "|---|---|---|---|---|---|---|---|---|---|"
    ]

    for i in range(1, 21):
        case_id = f"HHG-{i:03d}"
        case_file = CASES_DIR / f"{case_id}.json"
        if not case_file.exists():
            continue
        with open(case_file, "r") as f:
            data = json.load(f)
        
        results[case_id] = data
        c = data.get("case", {})
        nba = data.get("next_best_actions", {})
        sar = data.get("sar", {})

        init_acts = ", ".join([a["action"] for a in nba.get("initial", [])])
        final_acts = ", ".join([a["action"] for a in nba.get("final", [])])
        routes = ", ".join([f"{a['action']}:{a['route']}" for a in nba.get("final", [])])

        summary_lines.append(
            f"| {case_id} | {data.get('case_id')} | {c.get('verdict')} | {c.get('fraud_probability'):.2f} | {c.get('pattern')} | {c.get('exposure_usd', 0.0):.2f} | {sar.get('file')} | {init_acts} | {final_acts} | {routes} |"
        )

    out_json = BASELINE_DIR / "pre_migration_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    out_md = BASELINE_DIR / "pre_migration_summary.md"
    with open(out_md, "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    print(f"Recorded {len(results)} baseline cases to {out_json} and {out_md}")

if __name__ == "__main__":
    record_pre_migration_baseline()
