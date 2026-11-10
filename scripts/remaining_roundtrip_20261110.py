"""Replay the 4 adopted-but-unmeasured forms (es tomaré, pt acharei / logo / por isso).

    uv run python scripts/remaining_roundtrip_20261110.py --run            # bare forms (0/9 x4)
    uv run python scripts/remaining_roundtrip_20261110.py --run-context    # in-context cohort

#161 / #164 promoted these runner-ups after the es (#172) / pt (#171) round-trips,
so they had no record. Sources are frozen in ``remaining_20261110_sources.json``
before the gate; the judge answers are never corrected to match sources and
run() owns every trial count.
"""
from __future__ import annotations

import argparse
import copy
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


CTX_JUDGE_SHA256 = "8bfefa6279cce2078a4e471a083e1aaf23669a06e354dc35b093adb62874d8f3"
CTX_RAW_REPLY_SHA256 = "cdd34ac2b296c9b3563af00caa0045c802853f6ef3d53e2cc41b453c0d01599a"
CTX_MEANING_SHA256 = "cffc9ff5df209268d89a9ba2d5136bfae764c32322b24e7e4f3608f535706c57"
CTX_CMD = "uv run python scripts/roundtrip_replay.py remaining_20261110_ctx"
CTX_KEYS = ["es:tomaré", "pt:acharei", "pt:logo", "pt:por isso"]


def context_templates(spec: dict) -> list[str]:
    """Each designed context with the adopted phrase as {s}, wrapped in the 3 official templates."""
    return spec["templates"]


def _run_context(data: dict, key: str, spec: dict) -> dict:
    """run() with this form's context templates; the official templates are restored afterwards."""
    official = data["templates"]
    data["templates"] = context_templates(spec)
    try:
        rt.run(data, CTX_CMD, entries=[{"lang": key.split(":", 1)[0], "from": [spec["adopted_source"]], "to": spec["form"]}],
               accepted_sources={key: [spec["adopted_source"]]})
    finally:
        data["templates"] = official
    return data


def measure_context(data: dict) -> dict:
    """In-context cohort (3 designed contexts x 3 official templates x 3 seeds per form).

    Exact match (norm-nfc-v1) stays the gate. A form whose context cohort passes gets it
    appended to its gate-visible record (after the bare 0/9 cohort, history kept). A form
    that fails keeps its reversal; its cohort is stored under ``context_studies`` only, so
    ``status()`` stays consistent with the reversal. Meaning match is reference only.
    """
    for name, sha in (("remaining_20261110_ctx_blind.json", CTX_JUDGE_SHA256),
                      ("remaining_20261110_ctx_meaning.json", CTX_MEANING_SHA256)):
        if hashlib.sha256((FIX / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f"immutable {name} hash mismatch")
    src = json.loads((FIX / "remaining_20261110_ctx_sources.json").read_text(encoding="utf-8"))
    judge = json.loads((FIX / "remaining_20261110_ctx_blind.json").read_text(encoding="utf-8"))
    meaning = json.loads((FIX / "remaining_20261110_ctx_meaning.json").read_text(encoding="utf-8"))["by_converted"]
    if list(src["forms"]) != CTX_KEYS or src["official_templates"] != data["templates"] or data["seeds"] != [1, 2, 3]:
        raise ValueError("unexpected context configuration")
    if set(judge) != {s["converted"] for s in src["sentences"]} or len(judge) != 36:
        raise ValueError("context judge does not cover the designed sentences")
    provenance = {
        "kind": "independent_blind_judge", "scope": "designed_context",
        "judge_file": "SentenceCalibratedMosaic/fixtures/roundtrip_judge/remaining_20261110_ctx_blind.json",
        "judge_sha256": CTX_JUDGE_SHA256, "raw_reply_sha256": CTX_RAW_REPLY_SHA256,
        "request_sha256": src["request_sha256"], "origin_main_sha": src["origin_main_sha"],
        "source_acceptance": "any-official-source-v1 (in-context adopted English only)",
        "judge": "Fresh context-free independent strong-model agent, single call with the official PROMPT + 36 numbered shuffled converted sentences",
        "disclosure": "Contexts were designed by the PR author. One 36-sentence call lets the judge cross-infer between sentences. Deterministic replay: one answer per sentence reused over three seeds.",
        "meaning_match_file": "SentenceCalibratedMosaic/fixtures/roundtrip_judge/remaining_20261110_ctx_meaning.json",
        "meaning_match_sha256": CTX_MEANING_SHA256,
    }
    studies = data.setdefault("context_studies", {}).setdefault("remaining_20261110", {})
    for key in CTX_KEYS:
        spec = src["forms"][key]
        lang, form = key.split(":", 1)
        probe = _run_context(copy.deepcopy(data), key, spec)
        cohort = probe["records"][key]["cohorts"][-1]
        if {t["converted"] for t in cohort["targets"]} != {s["converted"] for s in src["sentences"] if s["key"] == key}:
            raise ValueError(f"context sentences drifted for {key}")
        passed = rt.status(probe, lang, form) == "pass"
        target = _run_context(data, key, spec) if passed else probe
        cohort = target["records"][key]["cohorts"][-1]
        cohort["judge_provenance"] = provenance.copy()
        cohort["meaning_match_ref"] = {t["converted"]: meaning[t["converted"]]["meaning_match_ref"]
                                       for t in cohort["targets"]}
        if passed:
            data["run_history"][-1]["judge_provenance"] = provenance.copy()
        else:
            studies[key] = {"lang": lang, "form": form, "gate_visible": False,
                            "reason": "exact-match context cohort below threshold; reversal kept",
                            "cohort": cohort}
        if not cohort["complete"] or cohort["completed"] != 27:
            raise RuntimeError(f"incomplete context cohort for {key}")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--run-context", action="store_true")
    a = ap.parse_args()
    data = measure(rt.load()) if a.run else measure_context(rt.load())
    rt.DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
