"""AI round-trip (可逆性) check for adopted tense-matrix forms.

Each adopted bank entry (``from`` → ``to``) is embedded in several template
sentences; the converted sentence is handed to an AI restore command several
times in parallel with different seeds. Version 4 scores only the latest
cohort's ``restored / completed``. Complete legacy records without known
execution uncertainty retain their historical aggregate rate. Timed-out
attempts remain recorded, never silently omitted from a historical result.

Record accounting version 4 keeps cumulative counters as historical evidence,
not the scoring denominator. Each form has ``cohorts`` appended by each run; only the
latest cohort's distinct targets, completed count and restored count determine
its rate and minimum-trial gate. A complete later cohort may pass without
claiming that earlier timeouts were resolved. Legacy records are snapshotted
before their first v4 cohort; existing fixtures are not rewritten by reading.

Each invocation records target identities (language, form, source, converted
prompt and seed), configuration, a command digest (not potentially secret
command text), selected forms and duplicate target count. Zero-work cohorts
are unverified. Unselected forms retain their previous cohort. ``--run`` saves
results before returning nonzero for an incomplete or empty invocation.
Record-only callers may omit evaluation policy, but such cohorts cannot receive
a verified rate or gate result. Status applies the current requested policy;
the creation-time policy snapshot remains available for historical replay.

Usage::

    uv run python scripts/roundtrip.py --status               # per-form status counts
    uv run python scripts/roundtrip.py --impact               # winner changes if enforced
    uv run python scripts/roundtrip.py --run --cmd 'my-llm'   # record trials

``--cmd`` gets the prompt on stdin and ``ROUNDTRIP_SEED`` in the environment and
must print the restored English sentence. Enforcement is report-only: the
committed bank is never gated by this script.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import uuid
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA_PATH = ROOT / "TesseraTalk/fixtures/roundtrip.json"

PROMPT = (
    "The following sentence mixes English with short verb forms from other languages "
    "(subject pronouns may be dropped). Rewrite it as the original plain English sentence. "
    "Reply with the sentence only.\n\n{c}"
)


def load(path: Path = DATA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def key(lang: str, form: str) -> str:
    return f"{lang}:{form}"


def norm(s: str) -> str:
    # NFC first: an NFD reply (e + U+0301) would otherwise lose its accent below
    s = unicodedata.normalize("NFC", s).strip().strip('"').lower()
    s = re.sub(r"[^\w\s']", "", s)
    return " ".join(s.split())


def sentences(data: dict, src: str, to: str) -> list[tuple[str, str]]:
    """(original EN, converted) pairs, one per template."""
    out = []
    for t in data["templates"]:
        en = t.format(s=src)
        cv = t.format(s=to)
        out.append((en[0].upper() + en[1:], cv[0].upper() + cv[1:]))
    return out


def _valid_cohort(current) -> bool:
    if not isinstance(current, dict) or current.get("accounting_version") != 4 or current.get("evaluation_scope") != "latest_cohort":
        return False
    if not isinstance(current.get("run_id"), str) or not current["run_id"] or not isinstance(current.get("config"), dict):
        return False
    config = current["config"]
    if any(not isinstance(config.get(k), str) or not re.fullmatch(r"[0-9a-f]{64}", config[k])
           for k in ("command_sha256", "prompt_sha256")):
        return False
    policy = config.get("evaluation_policy")
    if (not isinstance(policy, dict) or not {"min_trials", "thresholds", "ge100m_langs"} <= policy.keys()
            or not _valid_policy(policy, required=True)):
        return False
    if config.get("normalization") != "norm-nfc-v1":
        return False
    targets = current.get("targets")
    if not isinstance(targets, list):
        return False
    expected = current.get("expected_target_ids")
    if (not isinstance(expected, list) or any(not isinstance(t, str) or not re.fullmatch(r"[0-9a-f]{64}", t) for t in expected)
            or len(set(expected)) != len(expected)):
        return False
    ids = set()
    counts = {"attempted": len(targets), "completed": 0, "timeouts": 0, "execution_errors": 0, "restored": 0}
    identity_fields = ("lang", "form", "source", "converted", "seed", "prompt_sha256")
    for target in targets:
        if not isinstance(target, dict) or any(not isinstance(target.get(k), str) for k in identity_fields):
            return False
        if not re.fullmatch(r"[0-9a-f]{64}", target["prompt_sha256"]):
            return False
        target_id = _identity({k: target[k] for k in identity_fields})
        if target.get("target_id") != target_id or target_id in ids:
            return False
        ids.add(target_id)
        outcome = target.get("status")
        if outcome == "completed":
            if type(target.get("restored")) is not bool:
                return False
            counts["completed"] += 1
            counts["restored"] += int(target["restored"])
        elif outcome == "timeout":
            counts["timeouts"] += 1
        elif outcome == "execution_error":
            counts["execution_errors"] += 1
        else:
            return False
    if ids != set(expected):
        return False
    if any(type(current.get(k)) is not int or current[k] != v for k, v in counts.items()):
        return False
    complete = bool(targets) and counts["completed"] == len(targets)
    return type(current.get("complete")) is bool and current["complete"] == complete


def latest_cohort(rec: dict | None) -> dict | None:
    if rec and rec.get("accounting_version") == 4:
        history = rec.get("cohorts")
        if (isinstance(history, list) and history and _valid_cohort(history[-1])
                and all(t["lang"] == rec.get("lang") and t["form"] == rec.get("form") for t in history[-1]["targets"])):
            return history[-1]
    return None


def unresolved_timeouts(rec: dict | None) -> int:
    """Current cohort timeouts; historical counts are never cleared."""
    current = latest_cohort(rec)
    if current is not None:
        return current["timeouts"]
    if not rec:
        return 0
    if rec.get("accounting_version") == 4:
        return 1  # malformed or missing current cohort is never verified
    historical = [rec.get("timeouts", 0), rec.get("execution_errors", 0)]
    if any(type(n) is not int or n < 0 for n in historical):
        return 1
    if any(historical):
        return sum(historical)  # clearing a legacy flag is not cohort evidence
    if (rec.get("accounting_version") == 3
            and isinstance(rec.get("pending_trials"), list)
            and type(rec.get("legacy_pending")) is bool):
        return len(rec.get("pending_trials", [])) + int(bool(rec.get("legacy_pending")))
    if rec.get("accounting_version") == 3:
        return 1  # unknown v3 layout must not silently become a verified record
    pending = rec.get("pending_timeouts", 0)
    return pending if type(pending) is int and pending >= 0 else 1


def rate(rec: dict | None) -> float | None:
    current = latest_cohort(rec)
    if rec and rec.get("accounting_version") == 4:
        if not current or not current["complete"]:
            return None
        return current["restored"] / current["completed"]
    if not rec or not rec.get("trials") or unresolved_timeouts(rec):
        return None
    return rec["restored"] / rec["trials"]


def status(data: dict, lang: str, form: str) -> str:
    """pass / fail / never / unverified for this form's latest cohort."""
    if not _valid_policy(data, required=True):
        return "unverified"
    rec = data["records"].get(key(lang, form))
    if rec and rec.get("accounting_version") == 4 and (rec.get("lang") != lang or rec.get("form") != form):
        return "unverified"
    current = latest_cohort(rec)
    r = rate(rec)
    trials = current["completed"] if current else (rec or {}).get("trials", 0)
    if rec and rec.get("accounting_version") == 4 and (r is None or trials < data["min_trials"]):
        return "unverified"
    if r is None or trials < data["min_trials"]:
        return "never" if r == 0 else "unverified"
    if r == 0:
        return "never"
    th = data["thresholds"]["ge100m" if lang in data["ge100m_langs"] else "lt100m"]
    return "pass" if r >= th else "fail"


def gate_for(data: dict, scope: str):
    """Candidate gate for tense_matrix.build: scope 'lt100m' or 'all'."""

    def gate(form: str, lang: str) -> bool:
        if not _valid_policy(data, required=True):
            return False
        rec = data["records"].get(key(lang, form))
        if unresolved_timeouts(rec):
            return False
        if rec and rec.get("accounting_version") == 4 and status(data, lang, form) == "unverified":
            return False
        st = status(data, lang, form)
        if st == "never":
            return False
        if scope == "lt100m" and lang in data["ge100m_langs"]:
            return True
        return st == "pass"

    return gate


REQUIRED_RULES = (("nl", "perf"),)  # (lang, tense) whose bank winners need round-trip


def required_keys(bank: dict) -> list[str]:
    """Bank winners that must carry a round-trip record (nl preterite for EN perfect)."""
    return sorted({key(e["lang"], e["to"]) for e in bank["entries"]
                   if (e["lang"], e["tense"]) in REQUIRED_RULES})


def _winners(bank: dict) -> dict[str, tuple[str, str, str]]:
    return {e["id"]: (e["from"][0], e["to"], e["lang"]) for e in bank["entries"]}


def impact(data: dict, scope: str) -> list[tuple[str, str, tuple | None, tuple | None]]:
    import tense_matrix as tm

    base = _winners(tm.build()[0])
    gated = _winners(tm.build(gate=gate_for(data, scope))[0])
    out = []
    for k in sorted(set(base) | set(gated)):
        a, b = base.get(k), gated.get(k)
        if (a and a[1:]) != (b and b[1:]):
            out.append((k, (a or b)[0], a and a[1:], b and b[1:]))
    return out


def _identity(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _valid_policy(data: dict, *, required: bool = False) -> bool:
    minimum = data.get("min_trials")
    if required or "min_trials" in data:
        if type(minimum) is not int or minimum <= 0:
            return False
    thresholds = data.get("thresholds")
    if required or "thresholds" in data:
        if not isinstance(thresholds, dict) or not {"lt100m", "ge100m"} <= thresholds.keys():
            return False
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
               for x in thresholds.values()):
            return False
    languages = data.get("ge100m_langs")
    if required or "ge100m_langs" in data:
        if not isinstance(languages, list) or any(not isinstance(lang, str) for lang in languages):
            return False
    return True


def run(data: dict, cmd: str, *, workers: int = 8, only_lang: str | None = None,
        entries: list[dict] | None = None, timeout: float = 120) -> dict:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if not _valid_policy(data):
        raise ValueError("invalid evaluation policy")
    if not isinstance(data["templates"], list) or any(not isinstance(t, str) for t in data["templates"]):
        raise ValueError("templates must be strings")
    if not isinstance(data["seeds"], list) or any(type(s) not in (int, str) for s in data["seeds"]):
        raise ValueError("seeds must be integers or strings")
    if entries is None:
        import tense_matrix as tm
        entries = tm.build()[0]["entries"]
    prompt_template = PROMPT
    config = {"only_lang": only_lang, "timeout": timeout, "workers": workers,
              "templates": copy.deepcopy(data["templates"]), "seeds": copy.deepcopy(data["seeds"]),
              "command_sha256": hashlib.sha256(cmd.encode("utf-8")).hexdigest(),
              "prompt_sha256": hashlib.sha256(prompt_template.encode("utf-8")).hexdigest(),
              "evaluation_policy": copy.deepcopy({k: data.get(k) for k in ("min_trials", "thresholds", "ge100m_langs")}),
              "normalization": "norm-nfc-v1"}
    run_id = str(uuid.uuid4())
    selected = {}
    targets = {}
    duplicate_targets = 0
    for e in entries:
        if only_lang and e["lang"] != only_lang:
            continue
        k = key(e["lang"], e["to"])
        selected[k] = {"lang": e["lang"], "form": e["to"]}
        for en, cv in sentences(data, e["from"][0], e["to"]):
            for seed in data["seeds"]:
                target = {"lang": e["lang"], "form": e["to"], "source": en,
                          "converted": cv, "seed": str(seed),
                          "prompt_sha256": hashlib.sha256(prompt_template.format(c=cv).encode("utf-8")).hexdigest()}
                target_id = _identity(target)
                if target_id in targets:
                    duplicate_targets += 1
                else:
                    targets[target_id] = target

    def one(item):
        target_id, target = item
        env = dict(os.environ, ROUNDTRIP_SEED=str(target["seed"]))
        result = {"target_id": target_id, **target}
        try:
            p = subprocess.run(cmd, shell=True, input=prompt_template.format(c=target["converted"]),
                               capture_output=True, text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {**result, "status": "timeout"}
        except (OSError, UnicodeError) as exc:
            return {**result, "status": "execution_error", "error_type": type(exc).__name__}
        if p.returncode != 0:
            return {**result, "status": "execution_error", "returncode": p.returncode}
        return {**result, "status": "completed", "restored": norm(p.stdout) == norm(target["source"])}

    expected_targets = {k: [target_id for target_id, t in targets.items() if key(t["lang"], t["form"]) == k] for k in selected}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, targets.items()))
    invocation = {"accounting_version": 4, "evaluation_scope": "latest_cohort", "run_id": run_id, "config": config,
                  "selected_forms": list(selected), "duplicate_targets": duplicate_targets,
                  "requested": len(results) + duplicate_targets, "scheduled": len(results),
                  "attempted": len(results), "completed": 0, "timeouts": 0, "execution_errors": 0}
    for k, form in selected.items():
        rec = data["records"].setdefault(k, {**form, "trials": 0, "restored": 0, "failures": []})
        prior_attempted = rec.get("attempted", rec["trials"] + rec.get("timeouts", 0) + rec.get("execution_errors", 0))
        if rec.get("accounting_version") != 4:
            rec["legacy_snapshot"] = copy.deepcopy(rec)
            rec["cohorts"] = []
        rec["lang"] = form["lang"]
        rec["form"] = form["form"]
        attempts = [x for x in results if key(x["lang"], x["form"]) == k]
        completed = sum(x["status"] == "completed" for x in attempts)
        timeouts = sum(x["status"] == "timeout" for x in attempts)
        errors = sum(x["status"] == "execution_error" for x in attempts)
        restored = sum(x.get("restored", False) for x in attempts)
        cohort = {"accounting_version": 4, "evaluation_scope": "latest_cohort", "run_id": run_id, "config": copy.deepcopy(config),
                  "targets": attempts, "attempted": len(attempts), "completed": completed,
                  "expected_target_ids": expected_targets[k],
                  "timeouts": timeouts, "execution_errors": errors, "restored": restored,
                  "complete": bool(attempts) and completed == len(attempts)}
        rec["cohorts"].append(cohort)
        rec["accounting_version"] = 4
        rec["trials"] += completed
        rec["completed"] = rec["trials"]
        rec["restored"] += restored
        rec["timeouts"] = rec.get("timeouts", 0) + timeouts
        rec["execution_errors"] = rec.get("execution_errors", 0) + errors
        rec["attempted"] = prior_attempted + len(attempts)
        for attempt in attempts:
            if attempt["status"] == "completed" and not attempt["restored"] and len(rec["failures"]) < 5:
                rec["failures"].append(attempt["converted"])
        invocation["completed"] += completed
        invocation["timeouts"] += timeouts
        invocation["execution_errors"] += errors
    invocation["complete"] = bool(results) and invocation["completed"] == len(results)
    invocation["verifiable"] = bool(selected) and all(status(data, f["lang"], f["form"]) != "unverified" for f in selected.values())
    data.setdefault("run_history", []).append(invocation)
    return data


def impact_doc(data: dict) -> str:
    import tense_matrix as tm

    bank = tm.build()[0]
    rows = impact(data, "lt100m")
    lines = [f"{k}\t{src}\t{old}\t->\t{new}" for k, src, old, new in rows]
    flip = {k: f"{old} -> {new}" for k, _s, old, new in rows}
    req = [e for e in bank["entries"] if (e["lang"], e["tense"]) in REQUIRED_RULES]
    out = [
        "# 往復チェック強制時の影響（report-only、記録0件時点）", "",
        "生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。", "",
        "## 往復チェック必須の nl 過去形（現在完了セル）", "",
        f"nl（1億人未満）の現在完了セル採用 {len(req)} 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。", "",
        "| id | EN | 採用 | lt100m 強制時 |", "|---|---|---|---|",
    ]
    out += [f"| {e['id']} | {e['from'][0]} | {e['to']} | {flip.get(e['id'], '(変化なし)')} |" for e in req]
    out += ["", f"## 全件（`--impact lt100m`、{len(lines)}件）", "", "```", *lines, "```", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--impact", choices=("lt100m", "all"))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cmd")
    ap.add_argument("--lang")
    ap.add_argument("--write-doc", action="store_true")
    ap.add_argument("--sync-required", action="store_true",
                    help="rewrite data['required'] from the current bank")
    a = ap.parse_args(argv)
    data = load()
    incomplete = False
    if a.run:
        if not a.cmd:
            ap.error("--run needs --cmd")
        DATA_PATH.write_text(json.dumps(run(data, a.cmd, only_lang=a.lang), ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        latest = data.get("run_history", [{}])[-1]
        incomplete = not (latest.get("complete", False) and latest.get("verifiable", False))
        if incomplete:
            print("Round-trip results saved; the current invocation is incomplete or empty and remains unverified.", file=sys.stderr)
    if a.sync_required:
        import tense_matrix as tm

        data["required"] = required_keys(tm.build()[0])
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.write_doc:
        (ROOT / "docs/roundtrip_impact.md").write_text(impact_doc(data), encoding="utf-8")
    if a.status:
        import tense_matrix as tm
        from collections import Counter

        c = Counter((e["lang"], status(data, e["lang"], e["to"])) for e in tm.build()[0]["entries"])
        for (lang, st), n in sorted(c.items()):
            print(f"{lang}\t{st}\t{n}")
    if a.impact:
        for k, src, old, new in impact(data, a.impact):
            print(f"{k}\t{src}\t{old}\t->\t{new}")
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())

