"""3bot reaudit (class a): #179-style in-context blind round-trip of 13 reversed forms.

    uv run python scripts/reaudit_a_3bot_roundtrip.py --write   # (re)write the results file
    uv run python scripts/reaudit_a_3bot_roundtrip.py --check   # replay and compare (exit 1 on drift)

Each form gets 3 author-designed contexts x the 3 official templates (9 sentences);
every converted sentence was judged by its own fresh context-free call with the
official ``roundtrip.PROMPT``. ``roundtrip.run()`` replays the stored replies
(``roundtrip_replay.py reaudit_a_3bot``) on a deep copy of roundtrip.json, so every
count comes from run(); roundtrip.json itself is never written. Exact match
(norm-nfc-v1) gates; meaning match is reference only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import roundtrip as rt

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge"
NAME = "reaudit_a_3bot"
RESULTS = FIX / f"{NAME}_results.json"
CMD = f"uv run python scripts/roundtrip_replay.py {NAME}"
SHA256 = {
    "blind": "8a3d73af80278047bb83d3494d8a7d7f8ef16b1530ddec26e52cac5769f4c091",
    "sources": "9a98771a298de9af622394f3e126707e81b8fa06267b8bf09658ff8cd98d0364",
    "meaning": "6cff40fb0c5ea81b246738254d7633a5406967d800479e61df02ae299a63b07e",
}
KEYS = ["fr:vis", "fr:vins", "fr:sus", "fr:voulus", "fr:prends", "fr:avais su", "fr:ira", "fr:arrivé",
        "pt:virá", "pt:essayé", "pt:farei", "es:pensamos", "zh:几点"]
# Bank (lang, form) each measured key re-enables when it passes. essayé is the French
# candidate (the data had it labelled pt); es:pensamos is reported only (its EN source is
# also in ROUNDTRIP_REVERSED_SOURCES, left to the 2bot audit), so it maps to nothing.
BANK_FORM = {k: tuple(k.split(":", 1)) for k in KEYS if k not in ("es:pensamos", "pt:essayé")}
BANK_FORM["pt:essayé"] = ("fr", "essayé")


def inputs() -> tuple[dict, dict, dict]:
    """Frozen judge replies, designed sentences and reference meaning labels (hash-checked)."""
    out = []
    for part, sha in SHA256.items():
        raw = (FIX / f"{NAME}_{part}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f"immutable {NAME}_{part}.json hash mismatch")
        out.append(json.loads(raw))
    judge, src, meaning = out
    converted = {s["converted"] for s in src["sentences"]}
    if list(src["forms"]) != KEYS or set(judge) != converted or set(meaning["by_converted"]) != converted:
        raise ValueError("judge / sources / meaning do not cover the same designed sentences")
    return judge, src, meaning


def measure(data: dict, cmd: str = CMD) -> dict:
    """Per form: run() with its 9 context templates on a copy; summary of the new cohort."""
    _, src, meaning = inputs()
    if src["official_templates"] != data["templates"] or data["seeds"] != [1, 2, 3] or data["min_trials"] != 9:
        raise ValueError("unexpected round-trip configuration")
    results = {}
    for key in KEYS:
        spec = src["forms"][key]
        lang, form = key.split(":", 1)
        probe = copy.deepcopy(data)
        probe["templates"] = spec["templates"]
        rt.run(probe, cmd, entries=[{"lang": lang, "from": spec["accepted_sources"], "to": form}],
               accepted_sources={key: spec["accepted_sources"]})
        cohort = probe["records"][key]["cohorts"][-1]
        targets = {}
        for t in cohort["targets"]:
            targets.setdefault(t["converted"], {
                "source": t["source"], "response": t["response"], "restored": t["restored"],
                "matched_source": t["matched_source"],
                "meaning_match_ref": meaning["by_converted"][t["converted"]]["meaning_match_ref"]})
        results[key] = {
            "lang": lang, "form": form, "status": rt.status(probe, lang, form),
            "exact": sum(v["restored"] for v in targets.values()),
            "meaning_same": sum(v["meaning_match_ref"] == "same" for v in targets.values()),
            "sentences": len(targets), "completed": cohort["completed"], "restored": cohort["restored"],
            "complete": cohort["complete"], "gate_visible": False, "targets": targets}
    return {"kind": "context_roundtrip_study", "gating": "exact norm-nfc-v1; reference only in roundtrip.json (not written)",
            "origin_main_sha": src["origin_main_sha"], "command": CMD,
            "thresholds": data["thresholds"], "min_trials": data["min_trials"], "results": results}


def restored(results: dict | None = None) -> set[tuple[str, str]]:
    """Bank (lang, form) re-enabled by a passing context cohort (default: committed results)."""
    if results is None:
        results = json.loads(RESULTS.read_text(encoding="utf-8"))["results"]
    return {BANK_FORM[k] for k, v in results.items() if k in BANK_FORM and v["status"] == "pass"}


def dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None, cmd: str = CMD) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = dump(measure(rt.load(), cmd))
    if a.write:
        RESULTS.write_text(text, encoding="utf-8")
        return 0
    ok = RESULTS.read_text(encoding="utf-8") == text
    print("up to date" if ok else f"{RESULTS.name} drifted; rerun --write", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
