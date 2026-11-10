"""Re-audit context round-trip (class b + bonus, 30 forms / 270 sentences) by GitHubヘルプ4bot.

    uv run python scripts/reaudit_b_4bot_roundtrip.py --write

Replays the frozen per-sentence blind answers (``roundtrip_judge/reaudit_b_4bot_blind.json``)
through the official ``roundtrip.run()`` with each form's context templates, exactly like
PR #179's ``--run-context``. The cohorts are computed on an in-memory copy of
``roundtrip.json`` and written to ``roundtrip_judge/reaudit_b_4bot_results.json`` only:
``roundtrip.json`` itself is never written. Exact match (norm-nfc-v1) is the gate; the
meaning match is reference only. Every count comes from run().
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

import roundtrip as rt

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge"
NAME = "reaudit_b_4bot"
CMD = f"uv run python scripts/roundtrip_replay.py {NAME}"
SHA256 = {
    "sources": "1be687ca5e7259210729e26e42df8bdc8b70a60408ef4660b117f2cf73b70cd2",
    "blind": "b332f270e750ce1937b226792d2a0ea63d7f051b9a7d9a16c2918ec5719f9f48",
    "raw": "0ce02d12ff6c70c0da8c8bbf9977a262b622d7bd18f7000bc94edfedb2a6eb3d",
    "meaning": "fecdfbc4e08be165d4e1bed110c3761b0f4b752430f58b490bb1ddcafb098fb3",
}
# Forms whose bank reversal this study undoes (exact gate passed); everything else stays reversed.
UNDONE = ["es:pude", "zh:明白", "zh:电话", "pt:tensão", "zh:餐厅", "zh:心脏病"]
# Its key already holds the passing "among other things" record; the "among others" study never touches it.
SEPARATE_STUDY = {"la:inter alia": "among others"}
METHOD = {
    "judging": "One converted sentence per call: each of the 270 sentences went to its own fresh, context-free, closed-book judge that received only the official scripts/roundtrip.py PROMPT with that sentence. Replies stored verbatim (reaudit_b_4bot_raw.json); the replay map strips surrounding whitespace only.",
    "contexts": "Self-written by GitHubヘルプ4bot from the re-audit contexts.json (3 per form); not from a corpus. de and la forms were included on myon's instruction although the re-audit rated them low.",
    "trials": "3 contexts x 3 official templates = 9 distinct sentences per form; deterministic replay reuses each answer over seeds [1, 2, 3] (27 targets), not 27 live inferences.",
    "gate": "exact match after norm-nfc-v1 against the adopted English from[0] in context; ge100m >= 0.6 (>= 6/9), lt100m (la, el) >= 0.9 (9/9). lt100m adoption requires AI round-trip success.",
    "meaning": "Reference only, never a gate: separate fresh context-free judges saw only {reference, candidate} pairs, 9 per call, shuffled.",
    "roundtrip_json": "Not modified. Passing cohorts are not appended to records here, so roundtrip.status() still reports the earlier bare-form cohort for the 6 undone forms.",
}


def _load(name: str):
    path = FIX / f"{NAME}_{name}.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256[name]:
        raise ValueError(f"immutable {path.name} hash mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def measure(data: dict) -> dict:
    src, blind, raw, meaning = (_load(n) for n in ("sources", "blind", "raw", "meaning"))
    if src["official_templates"] != data["templates"] or data["seeds"] != [1, 2, 3] or data["min_trials"] != 9:
        raise ValueError("unexpected cohort configuration")
    if set(blind) != {s["converted"] for s in src["sentences"]} or len(blind) != 270:
        raise ValueError("judge does not cover the designed sentences")
    by_conv = meaning["by_converted"]
    provenance = {"kind": "independent_blind_judge", "scope": "designed_context", "per_sentence_calls": True,
                  "judge_file": f"SentenceCalibratedMosaic/fixtures/roundtrip_judge/{NAME}_blind.json",
                  "judge_sha256": SHA256["blind"], "raw_file_sha256": SHA256["raw"],
                  "request_sha256": src["request_sha256"], "origin_main_sha": src["origin_main_sha"],
                  "source_acceptance": "any-official-source-v1 (in-context adopted English only)",
                  "meaning_match_sha256": SHA256["meaning"]}
    forms, studies, passed_cohorts = {}, {}, {}
    for key, spec in src["forms"].items():
        lang, form = key.split(":", 1)
        probe = copy.deepcopy(data)
        probe["templates"] = spec["templates"]
        rt.run(probe, CMD, entries=[{"lang": lang, "from": [spec["adopted_source"]], "to": form}],
               accepted_sources={key: [spec["adopted_source"]]})
        probe["templates"] = data["templates"]
        cohort = probe["records"][key]["cohorts"][-1]
        if not cohort["complete"] or cohort["completed"] != 27:
            raise RuntimeError(f"incomplete context cohort for {key}")
        if {t["converted"] for t in cohort["targets"]} != {s["converted"] for s in src["sentences"] if s["key"] == key}:
            raise ValueError(f"context sentences drifted for {key}")
        cohort["judge_provenance"] = provenance.copy()
        cohort["meaning_match_ref"] = {t["converted"]: by_conv[t["converted"]]["meaning_match_ref"] for t in cohort["targets"]}
        status = rt.status(probe, lang, form)
        exact9 = sum(rt.norm(blind[c]) == rt.norm(by_conv[c]["expected"]) for c in cohort["meaning_match_ref"])
        meaning9 = sum(v == "same" for v in cohort["meaning_match_ref"].values())
        forms[key] = {"lang": lang, "form": form, "band": spec["band"], "threshold": spec["threshold"],
                      "adopted_source": spec["adopted_source"], "exact": exact9, "meaning_ref": meaning9, "of": 9,
                      "exact_targets": f"{cohort['restored']}/{cohort['completed']}", "status": status,
                      "reversal_undone": key in UNDONE}
        if (status == "pass") != (key in UNDONE):
            raise RuntimeError(f"gate result for {key} disagrees with UNDONE")
        if status == "pass":
            passed_cohorts[key] = cohort
        else:
            studies[key] = {"lang": lang, "form": form, "gate_visible": False,
                            "reason": "exact-match context cohort below threshold; reversal kept",
                            "cohort": cohort}
            if key in SEPARATE_STUDY:
                studies[key]["separate_from_record"] = (
                    f"source '{SEPARATE_STUDY[key]}' only; the existing '{key}' record for the adopted "
                    "'among other things' entry is untouched")
    items = []
    for s in src["sentences"]:
        c = s["converted"]
        items.append({"id": s["id"], "key": s["key"], "context_id": s["context_id"], "template_id": s["template_id"],
                      "converted": c, "expected": s["source_sentence"], "raw": raw["by_id"][s["id"]]["raw"],
                      "raw_sha256": raw["by_id"][s["id"]]["raw_sha256"],
                      "exact": rt.norm(blind[c]) == rt.norm(s["source_sentence"]),
                      "meaning_match_ref": by_conv[c]["meaning_match_ref"]})
    return {"kind": "reaudit_context_roundtrip", "name": NAME, "origin_main_sha": src["origin_main_sha"],
            "method": METHOD, "normalization": "norm-nfc-v1", "command": CMD,
            "forms": forms, "items": items,
            "passed_cohorts": passed_cohorts,
            "context_studies": {"reaudit_b_4bot": studies}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", required=True)
    ap.parse_args()
    os.chdir(ROOT)
    out = measure(rt.load())
    (FIX / f"{NAME}_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, f in out["forms"].items():
        print(f"{k}\t{f['exact']}/9\tmeaning {f['meaning_ref']}/9\t{f['status']}")


if __name__ == "__main__":
    main()
