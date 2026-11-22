"""Measure current low-speaker-count winners against a running local llama.cpp server."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import roundtrip
import tense_matrix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-receipt", required=True, type=Path)
    parser.add_argument("--runtime", required=True, help="llama.cpp build or image digest")
    args = parser.parse_args()
    root = roundtrip.ROOT
    checkout = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], cwd=root, text=True).strip()
    data = roundtrip.load()
    bank = tense_matrix.build()[0]
    entries = [e for e in bank["entries"] if e["lang"] not in data["ge100m_langs"]]
    # Only official English sources for the current winner are eligible.
    sources = {}
    for entry in entries:
        key = roundtrip.key(entry["lang"], entry["to"])
        sources.setdefault(key, []).extend(entry["from"])
    cmd = [sys.executable, str(root / "shared" / "llama_cmd.py")]
    receipt = json.loads(args.model_receipt.read_text())
    roundtrip.run(data, cmd, entries=entries, workers=2, accepted_sources=sources)
    run = data["run_history"][-1]
    forms = {}
    for key in run["selected_forms"]:
        cohort = data["records"][key]["cohorts"][-1]
        forms[key] = {
            "status": roundtrip.status(data, *key.split(":", 1)),
            "restored": cohort["restored"], "completed": cohort["completed"],
            "trials": [{field: target[field] for field in (
                "seed", "converted", "source", "accepted_sources", "status", "response",
                "restored", "first_source_match") if field in target} for target in cohort["targets"]],
        }
    report = {"checkout": checkout,
              "model": receipt, "runtime": args.runtime, "sampling_temperature": 0.2,
              "run": run, "forms": forms}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if run["complete"] and run["verifiable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
