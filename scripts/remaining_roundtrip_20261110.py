"""Replay the 4 adopted-but-unmeasured forms (es tomaré, pt acharei / logo / por isso).

    uv run python scripts/remaining_roundtrip_20261110.py --run

#161 / #164 promoted these runner-ups after the es (#172) / pt (#171) round-trips,
so they had no record. Sources are frozen in ``remaining_20261110_sources.json``
before the gate; the judge answers are never corrected to match sources and
run() owns every trial count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import roundtrip as rt

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge"
JUDGE_SHA256 = "631387708c3c72c403b8c9582e1ce80fabfa7b8b2ab0cebae1d492734ecfa67f"
# verbatim numbered reply of the judge (12 lines), before mapping to converted sentences
RAW_REPLY_SHA256 = "1c6c4c121d20e9fc3873de6a2785ebbbcde86bb231ab250aad63ad306f77fca3"
CONVERTED_SHA256 = "0c6dca355c5fe95f007140de4894a115b9350b9807758776c9b4bf2af2b80b46"
CMD = "uv run python scripts/roundtrip_replay.py remaining_20261110"


def measure(data: dict) -> dict:
    """Append one 36-target cohort (4 forms x 3 templates x 3 seeds)."""
    if hashlib.sha256((FIX / "remaining_20261110_blind.json").read_bytes()).hexdigest() != JUDGE_SHA256:
        raise ValueError("immutable judge hash mismatch")
    snapshot = json.loads((FIX / "remaining_20261110_sources.json").read_text(encoding="utf-8"))
    forms = snapshot["forms"]
    if ([f["key"] for f in forms] != ["es:tomaré", "pt:acharei", "pt:logo", "pt:por isso"]
            or data["templates"] != ["{s}.", "Maybe {s} today.", "She told me that {s}."]
            or data["seeds"] != [1, 2, 3] or data["min_trials"] != 9):
        raise ValueError("unexpected cohort configuration")
    rt.run(data, CMD, entries=[f["entry"] for f in forms],
           accepted_sources={f["key"]: f["accepted_sources"] for f in forms})
    provenance = {
        "kind": "independent_blind_judge",
        "judge_file": "SentenceCalibratedMosaic/fixtures/roundtrip_judge/remaining_20261110_blind.json",
        "judge_sha256": JUDGE_SHA256, "raw_reply_sha256": RAW_REPLY_SHA256,
        "converted_only_sha256": CONVERTED_SHA256,
        "origin_main_sha": snapshot["origin_main_sha"],
        "source_acceptance": "any-official-source-v1",
        "judge": "Fresh context-free independent strong-model agent (#172-level), single call; not the assistant doing the work",
        "disclosure": "The judge received only the official scripts/roundtrip.py PROMPT plus the 12 converted sentences in one call; no repository, source English or glosses. Its numbered reply is stored verbatim (only the 'N. ' prefixes mapped to their sentences). An earlier local Qwen2.5-7B-Instruct run was superseded at the owner's request and is not scored. Deterministic replay: three answers reused over three seeds, not nine independent live inferences.",
    }
    for f in forms:
        data["records"][f["key"]]["cohorts"][-1]["judge_provenance"] = provenance.copy()
    data["run_history"][-1]["judge_provenance"] = provenance.copy()
    if (not data["run_history"][-1]["complete"] or not data["run_history"][-1]["verifiable"]
            or data["run_history"][-1]["completed"] != 36):
        raise RuntimeError("incomplete cohort; do not apply a gate")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", required=True)
    ap.parse_args()
    data = measure(rt.load())
    rt.DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
