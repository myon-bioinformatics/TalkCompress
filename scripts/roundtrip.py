"""AI round-trip (可逆性) check for adopted tense-matrix forms.

Each adopted bank entry (``from`` → ``to``) is embedded in several template
sentences; the converted sentence is handed to an AI restore command several
times in parallel with different seeds, and the restore rate is
``restored / trials`` over every (sentence × seed) trial.

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
import os
import re
import subprocess
import sys
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
    s = s.strip().strip('"').lower()
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


def rate(rec: dict | None) -> float | None:
    if not rec or not rec.get("trials"):
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
        st = status(data, lang, form)
        if st == "never":
            return False
        if scope == "lt100m" and lang in data["ge100m_langs"]:
            return True
        return st == "pass"

    return gate


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
        entries: list[dict] | None = None) -> dict:
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
        p = subprocess.run(cmd, shell=True, input=PROMPT.format(c=cv), capture_output=True,
                           text=True, env=env, timeout=120)
        return lang, to, en, cv, seed, norm(p.stdout) == norm(en)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, jobs))
    for lang, to, en, cv, _seed, ok in results:
        rec = data["records"].setdefault(key(lang, to), {"lang": lang, "form": to, "trials": 0, "restored": 0, "failures": []})
        rec["trials"] += 1
        rec["restored"] += int(ok)
        if not ok and len(rec["failures"]) < 5:
            rec["failures"].append(cv)
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--impact", choices=("lt100m", "all"))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cmd")
    ap.add_argument("--lang")
    a = ap.parse_args(argv)
    data = load()
    if a.run:
        if not a.cmd:
            ap.error("--run needs --cmd")
        DATA_PATH.write_text(json.dumps(run(data, a.cmd, only_lang=a.lang), ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    if a.status:
        import tense_matrix as tm
        from collections import Counter

        c = Counter((e["lang"], status(data, e["lang"], e["to"])) for e in tm.build()[0]["entries"])
        for (lang, st), n in sorted(c.items()):
            print(f"{lang}\t{st}\t{n}")
    if a.impact:
        for k, src, old, new in impact(data, a.impact):
            print(f"{k}\t{src}\t{old}\t->\t{new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
