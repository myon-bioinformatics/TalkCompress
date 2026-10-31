"""AI round-trip (可逆性) check for adopted tense-matrix forms.

Each adopted bank entry (``from`` → ``to``) is embedded in several template
sentences; the converted sentence is handed to an AI restore command several
times in parallel with different seeds. For complete records the restore rate
is ``restored / trials``. ``trials`` counts completed attempts; timed-out
attempts remain explicitly unverified, never silently omitted from a pass.

Record accounting (``accounting_version`` 2):

* ``trials`` (= ``completed``) / ``restored`` / ``failures``: cumulative over
  completed attempts; ``timeouts``: cumulative timed-out attempts;
  ``attempted`` = ``completed`` + ``timeouts``.
* ``pending_timeouts``: timed-out attempts in the *latest* ``--run`` that
  included the form.  It is reset on each such run, so a later run whose
  attempts all complete makes the form verifiable again (timeouts are not
  sticky).  Legacy records without it fall back to ``timeouts``.

While unresolved timeouts remain (``unresolved_timeouts(rec) > 0``) the form
is unverified: ``rate()`` is ``None`` and ``gate_for`` rejects it.  ``--run``
always saves results first, then exits 1 when a record touched by that run
still has unresolved timeouts, otherwise 0.

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


def unresolved_timeouts(rec: dict | None) -> int:
    """Timed-out attempts of the latest run (legacy records: all timeouts)."""
    if not rec:
        return 0
    return rec.get("pending_timeouts", rec.get("timeouts", 0))


def rate(rec: dict | None) -> float | None:
    if not rec or not rec.get("trials") or unresolved_timeouts(rec):
        return None
    return rec["restored"] / rec["trials"]


def status(data: dict, lang: str, form: str) -> str:
    """pass / fail / never / unverified for one (lang, form)."""
    rec = data["records"].get(key(lang, form))
    r = rate(rec)
    if r is None or rec["trials"] < data["min_trials"]:
        return "never" if r == 0 else "unverified"
    if r == 0:
        return "never"
    th = data["thresholds"]["ge100m" if lang in data["ge100m_langs"] else "lt100m"]
    return "pass" if r >= th else "fail"


def gate_for(data: dict, scope: str):
    """Candidate gate for tense_matrix.build: scope 'lt100m' or 'all'."""

    def gate(form: str, lang: str) -> bool:
        if unresolved_timeouts(data["records"].get(key(lang, form))):
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


def run(data: dict, cmd: str, *, workers: int = 8, only_lang: str | None = None,
        entries: list[dict] | None = None, timeout: float = 120) -> dict:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if entries is None:
        import tense_matrix as tm

        entries = tm.build()[0]["entries"]
    jobs = []
    for e in entries:
        if only_lang and e["lang"] != only_lang:
            continue
        for en, cv in sentences(data, e["from"][0], e["to"]):
            for seed in data["seeds"]:
                jobs.append((e["lang"], e["to"], en, cv, seed))

    def one(j):
        lang, to, en, cv, seed = j
        env = dict(os.environ, ROUNDTRIP_SEED=str(seed))
        try:
            p = subprocess.run(cmd, shell=True, input=PROMPT.format(c=cv), capture_output=True,
                               text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            # one hung trial must not discard every other result; recorded, not scored
            return lang, to, en, cv, seed, None
        return lang, to, en, cv, seed, norm(p.stdout) == norm(en)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, jobs))
    seen: set[str] = set()
    for lang, to, en, cv, _seed, ok in results:
        k = key(lang, to)
        rec = data["records"].setdefault(k, {"lang": lang, "form": to, "trials": 0, "restored": 0, "failures": []})
        if k not in seen:  # pending_timeouts describes this run only
            seen.add(k)
            rec["pending_timeouts"] = 0
        rec["accounting_version"] = 2
        if ok is None:
            rec["pending_timeouts"] += 1
            rec["timeouts"] = rec.get("timeouts", 0) + 1
            rec["completed"] = rec["trials"]
            rec["attempted"] = rec["trials"] + rec["timeouts"]
            continue
        rec["trials"] += 1
        rec["completed"] = rec["trials"]
        rec["attempted"] = rec["trials"] + rec.get("timeouts", 0)
        rec["restored"] += int(ok)
        if not ok and len(rec["failures"]) < 5:
            rec["failures"].append(cv)
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
        before = json.loads(json.dumps(data["records"]))
        DATA_PATH.write_text(json.dumps(run(data, a.cmd, only_lang=a.lang), ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        # only records touched by this run decide the exit code
        incomplete = any(unresolved_timeouts(rec) for k, rec in data["records"].items() if before.get(k) != rec)
        if incomplete:
            print("Round-trip results saved; timed-out attempts remain unverified.", file=sys.stderr)
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
