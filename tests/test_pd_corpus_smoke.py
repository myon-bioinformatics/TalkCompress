"""Random smoke over copyright-free (PD / US-gov / free RF) corpus snippets.

Samples which passages **and** how much text / how many lines to feed,
using a seeded RNG so CI stays reproducible. Override via pytest options:

  pytest --pd-seed=42 --pd-n=5
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from tests._helpers import load, ns

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "pd_corpus"
MANIFEST = CORPUS / "manifest.json"


@pytest.fixture
def pd_seed(pytestconfig) -> int:
    return int(pytestconfig.getoption("--pd-seed"))


@pytest.fixture
def pd_n(pytestconfig) -> int:
    return max(1, int(pytestconfig.getoption("--pd-n")))


def _load_passages() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: list[dict] = []
    for entry in data["passages"]:
        path = CORPUS / entry["file"]
        text = path.read_text(encoding="utf-8")
        raw_lines = text.splitlines()
        assert raw_lines, f"empty fixture: {path}"
        out.append({**entry, "text": text, "raw_lines": raw_lines})
    assert len(out) >= 10, "pd_corpus too small"
    return out


def _slice_passage(rng: random.Random, passage: dict) -> tuple[str, dict]:
    """Pick a random contiguous line span and optional char trim within it.

    Always returns non-empty text. Metadata describes the random choice.
    """
    lines = passage["raw_lines"]
    n = len(lines)
    # How many lines to feed: 1 .. n (prefer a bit of range even on short snippets)
    k = rng.randint(1, n)
    start = rng.randint(0, n - k)
    chunk_lines = lines[start : start + k]
    chunk = "\n".join(chunk_lines).strip()
    if not chunk:
        # rare all-blank span — fall back to full passage
        chunk = passage["text"].strip()
        start, k = 0, n

    # Optionally trim to a random character budget (still ≥ ~40 chars when possible)
    if len(chunk) > 80 and rng.random() < 0.55:
        lo = min(40, len(chunk))
        hi = len(chunk)
        budget = rng.randint(lo, hi)
        # cut on a word boundary when easy
        cut = chunk[:budget]
        if " " in cut and budget < len(chunk):
            cut = cut.rsplit(" ", 1)[0]
        if cut.strip():
            chunk = cut.strip()

    meta = {
        "id": passage["id"],
        "line_start": start,
        "line_count": k,
        "chars": len(chunk),
    }
    return chunk, meta


def _estimate_tokens(text: str) -> int:
    t = load("tessera_talk", "TesseraTalk/tessera_talk.py")
    return int(t.estimate_tokens(text))


@pytest.fixture(scope="module")
def passages() -> list[dict]:
    return _load_passages()


def test_pd_corpus_manifest_sane(passages):
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["count"] == len(passages) == len(data["passages"])
    sources = CORPUS / "SOURCES.md"
    assert sources.is_file()
    for p in passages:
        assert p["license"], p["id"]
        assert p["source_url"].startswith("http"), p["id"]
        assert (CORPUS / p["file"]).is_file()


def test_pd_corpus_random_compress_ce(passages, pd_seed, pd_n):
    """Seeded random: pick N passages × random line/char spans; C→E must not crash."""
    seed = pd_seed
    n = min(pd_n, len(passages))
    rng = random.Random(seed)
    chosen = rng.sample(passages, n)

    dz = load("density_zip", "DensityZip/density_zip.py")
    args = ns()

    results = []
    for p in chosen:
        text, meta = _slice_passage(rng, p)
        assert isinstance(text, str) and text.strip()
        out = dz.run_pipeline(["C", "E"], text, args)
        assert isinstance(out, str)
        assert out  # non-empty
        # Soft: token count should not hard-explode; allow equal / mild growth
        # (classic prose often gains little from C/E; fail only on wild blow-up)
        before_t = _estimate_tokens(text)
        after_t = _estimate_tokens(out)
        assert after_t <= before_t * 3 + 8, (
            f"token blow-up on {meta}: {before_t} → {after_t}\n"
            f"in={text[:120]!r}\nout={out[:120]!r}"
        )
        results.append({**meta, "tokens_in": before_t, "tokens_out": after_t})

    # Reproducibility: same seed → same selection metadata
    rng2 = random.Random(seed)
    chosen2 = rng2.sample(passages, n)
    metas2 = [_slice_passage(rng2, p)[1] for p in chosen2]
    assert [r["id"] for r in results] == [m["id"] for m in metas2]
    assert [r["line_start"] for r in results] == [m["line_start"] for m in metas2]
    assert [r["line_count"] for r in results] == [m["line_count"] for m in metas2]


def test_pd_corpus_random_compress_c_e_final(passages, pd_seed, pd_n):
    """Second draw (offset seed): include B-final token pass; still no crash."""
    seed = pd_seed + 17
    n = min(pd_n, len(passages))
    rng = random.Random(seed)
    chosen = rng.sample(passages, n)

    dz = load("density_zip", "DensityZip/density_zip.py")
    args = ns()

    for p in chosen:
        text, meta = _slice_passage(rng, p)
        out = dz.run_pipeline(["C", "E", "B-final-zh-de"], text, args)
        assert isinstance(out, str)
        assert out.strip()
        # Soft non-increase on whitespace tokens preferred; allow equal
        # Use estimate_tokens; do not fail on mild growth from glyph swaps
        before_t = _estimate_tokens(text)
        after_t = _estimate_tokens(out)
        assert after_t <= before_t * 3 + 8, (meta, before_t, after_t)
