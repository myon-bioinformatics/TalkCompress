"""Measure el contribution to B-final: final_token_pass with vs without el.

Usage: uv run python scripts/el_contribution.py [--json]
Excludes el by temporarily removing it from FINAL_*_LANGS (no code hook needed).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests._helpers import load  # noqa: E402

_NAMES = ("FINAL_TENSE_LANGS", "FINAL_PHRASE_LANGS", "FINAL_PT_EL_LATIN_PHRASE_LANGS")


def _texts() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for p in sorted((ROOT / "tests/fixtures/pd_corpus").glob("*.txt")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                out.append((f"{p.name}:{i + 1}", line))
    fx = json.loads((ROOT / "tests/fixtures/pd20_examples.json").read_text(encoding="utf-8"))
    out += [(f"pd20:{e['id']}", e["text"]) for e in fx["entries"]]
    return out


def _run(t, texts, *, drop_el: bool) -> list[str]:
    saved = {n: getattr(t, n) for n in _NAMES}
    try:
        if drop_el:
            for n in _NAMES:
                setattr(t, n, frozenset(saved[n] - {"el"}))
        return [t.final_token_pass(s) for _, s in texts]
    finally:
        for n, v in saved.items():
            setattr(t, n, v)


def _bank_flips(t) -> list[dict[str, str]]:
    bank = t.load_es_fr_tense_bank()["entries"]
    with_el = {e["id"]: t.apply_es_fr_tense(e["from"][0]) for e in bank}
    saved = {n: getattr(t, n) for n in _NAMES}
    try:
        for n in _NAMES:
            setattr(t, n, frozenset(saved[n] - {"el"}))
        no_el = {e["id"]: t.apply_es_fr_tense(e["from"][0]) for e in bank}
    finally:
        for n, v in saved.items():
            setattr(t, n, v)
    return [
        {"id": k, "with_el": with_el[k], "no_el": no_el[k]}
        for k in with_el
        if with_el[k] != no_el[k]
    ]


def measure() -> dict:
    t = load("tessera_talk", "TesseraTalk/tessera_talk.py")
    texts = _texts()
    a = _run(t, texts, drop_el=False)
    b = _run(t, texts, drop_el=True)
    tok = lambda xs: sum(t.estimate_tokens(x) for x in xs)  # noqa: E731
    u8 = lambda xs: sum(len(x.encode()) for x in xs)  # noqa: E731
    src = [s for _, s in texts]
    diffs = [
        {"where": w, "with_el": x, "no_el": y}
        for (w, _), x, y in zip(texts, a, b)
        if x != y
    ]
    return {
        "lines": len(texts),
        "src": {"tokens": tok(src), "utf8": u8(src)},
        "with_el": {"tokens": tok(a), "utf8": u8(a)},
        "no_el": {"tokens": tok(b), "utf8": u8(b)},
        "el_delta": {"tokens": tok(a) - tok(b), "utf8": u8(a) - u8(b)},
        "el_glyph_lines": sum(bool(re.search("[\u0370-\u03ff]", x)) for x in a),
        "corpus_diffs": diffs,
        "bank_flips": _bank_flips(t),
    }


if __name__ == "__main__":
    print(json.dumps(measure(), ensure_ascii=False, indent=2))
