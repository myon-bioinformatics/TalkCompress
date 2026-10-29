"""Tokenizer agreement / compatibility reports (build-time / CI only).

Primary scoring of the matrix is o200k_base (scripts/tense_matrix.py). This
script adds two reporting layers; neither changes any winner:

* ``--agreement``: stdlib ``tessera_talk.estimate_tokens`` vs o200k_base on the
  fixed sample (fixtures/token_agreement_sample.json) and on every matrix string
  (EN source, EN cheapest baseline, adopted / best form). Prints exact-match rate
  and winner-flip count (cells whose adopt/EN verdict differs when the stdlib
  estimate replaces o200k). The yardstick for eventually dropping tiktoken; the
  stdlib path is a deliberately tokenizer-independent measure.
* ``--compat``: per adopted cell, which pinned tokenizers the winner strictly
  beats EN's cheapest spelling on (tokens, then utf8). Optional HF tokenizers are
  downloaded once into ~/.cache/talkcompress/tokenizers; offline → skipped.
  Losing on some tokenizer is recorded, not disqualifying.

    uv run python scripts/tokenizer_compat.py --agreement
    uv run python scripts/tokenizer_compat.py --compat     # rewrites docs/tokenizer_compat.{json,md}
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import tense_matrix as tm  # noqa: E402

SAMPLE_PATH = ROOT / "TesseraTalk/fixtures/token_agreement_sample.json"
COMPAT_JSON = ROOT / "docs/tokenizer_compat.json"
COMPAT_MD = ROOT / "docs/tokenizer_compat.md"
CACHE = Path.home() / ".cache/talkcompress/tokenizers"

# Pinned public tokenizer.json revisions (no auth needed).
HF_TOKENIZERS = {
    "qwen2.5": ("Qwen/Qwen2.5-0.5B", "060db6499f32faf8b98477b0a26969ef7d8b9987"),
    "qwen3": ("Qwen/Qwen3-0.6B", "c1899de289a04d12100db370d81485cdf75e47ca"),
    "llama3.2": ("unsloth/Llama-3.2-1B", "9535bd9b1d1dea6acafbdc4813b728796aeb28da"),
    "mistral-v0.3": ("unsloth/mistral-7b-v0.3", "9ea1b83f5ced5663c5fa89c300fe59f9bdcd2b10"),
    "deepseek-v3": ("deepseek-ai/DeepSeek-V3", "e815299b0bcbac849fa540c768ef21845365c9eb"),
}
TIKTOKEN = ("o200k_base", "cl100k_base")


def _u8(s: str) -> int:
    return len(s.encode("utf-8"))


def _stdlib():
    from tests._helpers import load

    return load("tessera_talk", "TesseraTalk/tessera_talk.py").estimate_tokens


def _report_cells() -> list[dict]:
    return json.loads(tm.REPORT_PATH.read_text(encoding="utf-8"))["cells"]


def _en_best(src: str, tok) -> str:
    return min(tm.en_baselines(src), key=lambda f: (tok(f), _u8(f)))


def _beats(form: str, src: str, tok) -> bool:
    en = _en_best(src, tok)
    return (tok(form), _u8(form)) < (tok(en), _u8(en))


def agreement() -> dict:
    est = _stdlib()
    o = tm.o200k_tokens
    est_sp = lambda s: est(" " + s)  # noqa: E731  same mid-sentence framing
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["sample"]
    cells = _report_cells()
    strings = sorted({s for c in cells if "best" in c
                      for s in (c["src"], c.get("en_best", c["src"]), c["best"])} | {c["src"] for c in cells})
    exact = lambda xs: sum(est_sp(s) == o(s) for s in xs)  # noqa: E731
    flips = []
    for c in cells:
        if "best" not in c or c["status"] not in ("adopt", "reject"):
            continue
        if c.get("parity_verb") is not None and c["status"] == "reject":
            continue
        a, b = _beats(c["best"], c["src"], o), _beats(c["best"], c["src"], est_sp)
        if a != b:
            flips.append(c["src"])
    return {
        "sample_n": len(sample), "sample_exact": exact(sample),
        "matrix_n": len(strings), "matrix_exact": exact(strings),
        "cells_judged": sum(1 for c in cells if "best" in c), "winner_flips": len(flips),
        "flip_examples": flips[:10],
    }


def _hf(name: str):
    repo, rev = HF_TOKENIZERS[name]
    from tokenizers import Tokenizer

    p = CACHE / name / rev / "tokenizer.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{repo}/resolve/{rev}/tokenizer.json"
        with urllib.request.urlopen(url, timeout=60) as r:
            p.write_bytes(r.read())
    tk = Tokenizer.from_file(str(p))
    return lambda s: len(tk.encode(" " + s, add_special_tokens=False).ids)


def _tik(name: str):
    import tiktoken

    enc = tiktoken.get_encoding(name)
    return lambda s: len(enc.encode(" " + s))


def load_tokenizers() -> tuple[dict, dict]:
    """name -> counter; name -> skip reason. HF loads in parallel; failures skip."""
    toks, skipped = {}, {}
    for n in TIKTOKEN:
        toks[n] = _tik(n)
    with ThreadPoolExecutor(max_workers=len(HF_TOKENIZERS)) as ex:
        futs = {n: ex.submit(_hf, n) for n in HF_TOKENIZERS}
        for n, f in futs.items():
            try:
                toks[n] = f.result()
            except Exception as e:  # offline / HTTP error → optional, skip cleanly
                skipped[n] = f"{type(e).__name__}: {e}"[:120]
    return toks, skipped


def compat() -> dict:
    import tiktoken

    toks, skipped = load_tokenizers()
    names = list(toks)
    bank = json.loads(tm.BANK_PATH.read_text(encoding="utf-8")) if hasattr(tm, "BANK_PATH") else None
    entries = bank["entries"] if bank else tm.build()[0]["entries"]
    rows, counts, cats = [], Counter(), Counter()
    for e in entries:
        src, to = e["from"][0], e["to"]
        won = [n for n in names if _beats(to, src, toks[n])]
        counts.update(won)
        cat = "all" if len(won) == len(names) else "none" if not won else (
            "o200k only" if won == ["o200k_base"] else f"{len(won)}/{len(names)}")
        cats[cat] += 1
        rows.append({"id": e["id"], "src": src, "to": to, "lang": e["lang"], "beats_en_on": won, "category": cat})
    pins = {n: {"kind": "tiktoken", "version": tiktoken.__version__} for n in TIKTOKEN}
    pins.update({n: {"kind": "hf", "repo": r, "revision": v} for n, (r, v) in HF_TOKENIZERS.items() if n in toks})
    return {"tokenizers": pins, "skipped": skipped, "adopted": len(rows),
            "beats_en_count": {n: counts[n] for n in names}, "categories": dict(cats.most_common()), "cells": rows}


def compat_md(d: dict) -> str:
    out = ["# トークナイザー互換レポート（report-only）", "",
           "採点は o200k_base。各採用セルの勝者が英語の最安形（短縮形含む）に (tokens, utf8) で厳密に勝つトークナイザーを記録。負けても不採用にはしない。", "",
           "生成: `uv run python scripts/tokenizer_compat.py --compat`", "", "| tokenizer | pin | 勝ち | / 採用 |", "|---|---|---|---|"]
    for n, p in d["tokenizers"].items():
        pin = p.get("revision", p.get("version"))
        out.append(f"| {n} | {p.get('repo', 'tiktoken')}@{pin[:12]} | {d['beats_en_count'][n]} | {d['adopted']} |")
    if d["skipped"]:
        out += ["", "スキップ: " + ", ".join(d["skipped"])]
    out += ["", "| 区分 | セル数 |", "|---|---|", *[f"| {k} | {v} |" for k, v in d["categories"].items()], ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agreement", action="store_true")
    ap.add_argument("--compat", action="store_true")
    a = ap.parse_args(argv)
    if a.agreement:
        r = agreement()
        print(f"stdlib vs o200k_base: sample exact {r['sample_exact']}/{r['sample_n']} "
              f"({r['sample_exact'] / r['sample_n']:.1%}), matrix exact {r['matrix_exact']}/{r['matrix_n']} "
              f"({r['matrix_exact'] / r['matrix_n']:.1%}), winner flips {r['winner_flips']}/{r['cells_judged']}")
        print("flip examples:", r["flip_examples"])
    if a.compat:
        d = compat()
        COMPAT_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        COMPAT_MD.write_text(compat_md(d), encoding="utf-8")
        print(compat_md(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
