"""Replay the frozen 270-form pt cohort with official any-source acceptance.

    uv run python scripts/pt_roundtrip.py --run

The source snapshot precedes the gate; do not enumerate the reduced bank. Blind
answers must never be corrected to match sources. run() owns all trial counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import roundtrip as rt

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge"
JUDGE_SHA256 = "d161afaef0b6f8dea08c5ff5babb69f349a7baea60f697ddaf5e85b36dd369df"
CONVERTED_SHA256 = "73fb04a10d7d26fa7c45453c03e271ed64697f6565e4795369d3588abb4d6551"


def measure(data: dict) -> dict:
    """Append one 2430-target cohort; retain failures and historical evidence."""
    if hashlib.sha256((FIX / "pt_blind.json").read_bytes()).hexdigest() != JUDGE_SHA256:
        raise ValueError("immutable Portuguese judge hash mismatch")
    snapshot = json.loads((FIX / "pt_sources.json").read_text(encoding="utf-8"))
    forms = snapshot["forms"]
    if (len(forms) != 270 or len({f["key"] for f in forms}) != 270
            or data["templates"] != ["{s}.", "Maybe {s} today.", "She told me that {s}."]
            or data["seeds"] != [1, 2, 3] or data["min_trials"] != 9):
        raise ValueError("unexpected Portuguese cohort configuration")
    rt.run(data, "uv run python scripts/roundtrip_replay.py pt", only_lang="pt",
           entries=[f["entry"] for f in forms],
           accepted_sources={f["key"]: f["accepted_sources"] for f in forms})
    provenance = {
        "kind": "independent_blind_judge",
        "judge_file": "SentenceCalibratedMosaic/fixtures/roundtrip_judge/pt_blind.json",
        "judge_sha256": JUDGE_SHA256, "converted_only_sha256": CONVERTED_SHA256,
        "origin_main_sha": snapshot["origin_main_sha"],
        "source_acceptance": "any-official-source-v1",
        "disclosure": "Same assistant works on TalkCompress; source filenames/counts known, no example form-English pairs in assignment. Judge saw only 810 converted sentences before answering. Deterministic replay: three answers reused over three seeds, not nine independent live inferences.",
    }
    for f in forms:
        data["records"][f["key"]]["cohorts"][-1]["judge_provenance"] = provenance.copy()
    data["run_history"][-1]["judge_provenance"] = provenance.copy()
    if (not data["run_history"][-1]["complete"] or not data["run_history"][-1]["verifiable"]
            or data["run_history"][-1]["completed"] != 2430):
        raise RuntimeError("incomplete Portuguese cohort; do not apply a gate")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    data = measure(rt.load())
    rt.DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
