"""Mid-split / truncated-text smoke — roast defects that clean fixtures miss.

Intentionally cuts passages mid-token / mid-phrase / mid-CJK-run / mid-sentence /
mid-markdown-ish span, and feeds abrupt translated fragments. Purpose is crash
and invariant hunting, **not** restoration quality or round-trip fidelity.

Seeded RNG (``--mid-seed`` / ``--mid-n``) keeps CI reproducible.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from tests._helpers import load, ns

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "pd_corpus"
MANIFEST = CORPUS / "manifest.json"
TRANS_JSON = ROOT / "TesseraTalk" / "fixtures" / "translations.json"
ZH_DE_JSON = ROOT / "TesseraTalk" / "fixtures" / "zh_de_phrases.json"

_CJK_RUN = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF]{2,}")
_ASCII_WORD = re.compile(r"[A-Za-z']{4,}")

# Fabricated abrupt originals / translations (end mid-word or mid-phrase).
# Not expected to densify cleanly — only to survive the pipeline.
_ABRUPT_FRAGMENTS: list[tuple[str, str]] = [
    ("asap-mid", "Please reply as soon as poss"),
    ("bahnhof-mid", "Meet me at the train stati"),
    ("will-go-mid", "I will go tomor"),
    ("zh-weather-mid", "今天天气很"),
    ("de-bahnhof-mid", "Der Bahnhof ist ge"),
    ("keep-unclosed", "[[keep:foo"),
    ("keep-bt-unclosed", "`keep:bar"),
    ("md-bold-mid", "Hello **world"),
    ("ledger-under-mid", "under the tabl"),
    ("counter-singular", "three animal"),
    ("counter-stem-mid", "3 anima"),
    ("densifier-trunc", "as soon as"),
    ("adj-noun-mid", "high speed rai"),
    ("prog-mid", "I'm goi"),
    ("ja-weather-mid", "今日はとて"),
    ("zh-meeting-mid", "我们今天下午三点开"),
    ("combining-nfd", "cafe\u0301"),  # NFD e+acute — must not crash
    ("combining-leading", "\u0301x"),  # leading combiner after a bad cut
    ("emptyish-article", "a"),  # E article strip may yield ""
]


@pytest.fixture
def mid_seed(pytestconfig) -> int:
    return int(pytestconfig.getoption("--mid-seed"))


@pytest.fixture
def mid_n(pytestconfig) -> int:
    return max(1, int(pytestconfig.getoption("--mid-n")))


def _estimate_tokens(text: str) -> int:
    t = load("tessera_talk", "TesseraTalk/tessera_talk.py")
    return int(t.estimate_tokens(text))


def _soft_ok(src: str, out: object, *, meta: dict) -> str:
    """Cheap invariants. No round-trip / restoration expectations."""
    assert isinstance(out, str), (meta, type(out), out)
    # Length must not explode without reason (allow small absolute slack).
    assert len(out) <= max(48, len(src) * 10 + 24), (
        f"length blow-up {meta}: {len(src)} → {len(out)}\n"
        f"in={src[:160]!r}\nout={out[:160]!r}"
    )
    # If input is valid UTF-8, output must remain valid UTF-8
    # (lone surrogates in *input* are out of scope — see dedicated test).
    try:
        src.encode("utf-8")
    except UnicodeEncodeError:
        pass
    else:
        out.encode("utf-8")
    # Soft token ceiling — same spirit as PD smoke (not a quality bar).
    if src.strip() and len(src) >= 8:
        before_t = _estimate_tokens(src)
        after_t = _estimate_tokens(out)
        assert after_t <= before_t * 3 + 8, (
            f"token blow-up {meta}: {before_t} → {after_t}\n"
            f"in={src[:120]!r}\nout={out[:120]!r}"
        )
    return out


# ---------------------------------------------------------------------------
# Cut generators (deterministic given rng)
# ---------------------------------------------------------------------------


def cut_mid_token(text: str, rng: random.Random) -> tuple[str, dict] | None:
    """Cut inside an ASCII word (≥4 letters)."""
    matches = list(_ASCII_WORD.finditer(text))
    if not matches:
        return None
    m = matches[rng.randrange(len(matches))]
    word = m.group(0)
    # leave at least 1 char of the word on the left; drop the rest
    keep = max(1, len(word) // 2)
    if keep >= len(word):
        keep = len(word) - 1
    cut_at = m.start() + keep
    chunk = text[:cut_at]
    if not chunk.strip():
        return None
    return chunk, {
        "pattern": "mid_token",
        "word": word,
        "cut_at": cut_at,
        "chars": len(chunk),
    }


def cut_mid_phrase(text: str, rng: random.Random) -> tuple[str, dict] | None:
    """Cut after a word boundary mid-way through a multi-word span (no rejoin)."""
    words = text.split()
    if len(words) < 4:
        return None
    # take a window of 3–6 words, then drop the last word mid-way via char cut
    win = min(len(words), rng.randint(3, 6))
    start = rng.randint(0, len(words) - win)
    span = " ".join(words[start : start + win])
    # cut inside the last word of the span
    parts = span.rsplit(" ", 1)
    if len(parts) != 2 or len(parts[1]) < 2:
        chunk = span[: max(1, len(span) * 2 // 3)]
    else:
        head, last = parts
        chunk = f"{head} {last[: max(1, len(last) // 2)]}"
    if not chunk.strip():
        return None
    return chunk, {
        "pattern": "mid_phrase",
        "chars": len(chunk),
        "win": win,
    }


def cut_mid_cjk(text: str, rng: random.Random) -> tuple[str, dict] | None:
    """Cut inside a 2+ CJK-codepoint run (between codepoints, not UTF-8 bytes)."""
    matches = list(_CJK_RUN.finditer(text))
    if not matches:
        return None
    m = matches[rng.randrange(len(matches))]
    run_len = m.end() - m.start()
    keep = max(1, run_len // 2)
    if keep >= run_len:
        keep = run_len - 1
    cut_at = m.start() + keep
    chunk = text[:cut_at]
    if not chunk.strip():
        return None
    return chunk, {
        "pattern": "mid_cjk",
        "run": text[m.start() : m.end()],
        "cut_at": cut_at,
        "chars": len(chunk),
    }


def cut_mid_sentence(text: str, rng: random.Random) -> tuple[str, dict] | None:
    """Cut before a sentence terminator, mid-clause."""
    # Prefer first sentence-ish unit
    m = re.search(r"[.!?。！？]", text)
    end = m.start() if m else len(text)
    unit = text[:end].strip()
    if len(unit) < 12:
        unit = text.strip()
    if len(unit) < 8:
        return None
    frac = rng.choice([0.35, 0.45, 0.55, 0.65])
    cut_at = max(4, int(len(unit) * frac))
    # Prefer not to land on space; if we do, nudge into the next word a bit
    chunk = unit[:cut_at]
    if chunk.endswith(" ") and cut_at < len(unit):
        nxt = unit[cut_at:].lstrip()
        take = min(3, max(1, len(nxt) // 2))
        chunk = unit[:cut_at] + nxt[:take]
    chunk = chunk.rstrip()
    if len(chunk) < 4:
        return None
    return chunk, {
        "pattern": "mid_sentence",
        "chars": len(chunk),
        "frac": frac,
    }


def cut_mid_markdown(text: str, rng: random.Random) -> tuple[str, dict] | None:
    """Wrap a slice in a markdown-ish / keep span, then truncate the closer."""
    body = text.strip().replace("\n", " ")
    if len(body) < 8:
        return None
    # pick a short interior slice
    start = rng.randint(0, max(0, len(body) - 8))
    slen = rng.randint(4, min(16, len(body) - start))
    inner = body[start : start + slen]
    kind = rng.choice(["keep_brack", "keep_bt", "bold", "code"])
    if kind == "keep_brack":
        wrapped = f"prefix [[keep:{inner}"  # no closing ]]
    elif kind == "keep_bt":
        wrapped = f"prefix `keep:{inner}"  # no closing `
    elif kind == "bold":
        wrapped = f"Hello **{inner}"  # no closing **
    else:
        wrapped = f"use `{inner}"  # no closing `
    return wrapped, {
        "pattern": "mid_markdown",
        "kind": kind,
        "chars": len(wrapped),
    }


_CUTTERS = (
    cut_mid_token,
    cut_mid_phrase,
    cut_mid_sentence,
    cut_mid_markdown,
)


def _load_pd_texts() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: list[dict] = []
    for entry in data["passages"]:
        path = CORPUS / entry["file"]
        text = path.read_text(encoding="utf-8")
        out.append({**entry, "text": text, "source": "pd"})
    return out


def _load_translated_sources() -> list[dict]:
    """EN `from` strings + ZH/DE/JA candidate strings from TesseraTalk fixtures."""
    out: list[dict] = []
    trans = json.loads(TRANS_JSON.read_text(encoding="utf-8"))
    for entry in trans["entries"]:
        eid = entry.get("id", "trans")
        for i, fr in enumerate(entry.get("from") or []):
            if isinstance(fr, str) and fr.strip():
                out.append(
                    {
                        "id": f"tr-from-{eid}-{i}",
                        "text": fr,
                        "source": "translations.from",
                    }
                )
        cands = entry.get("candidates") or {}
        for lang, val in cands.items():
            vals = val if isinstance(val, list) else [val]
            for j, s in enumerate(vals):
                if isinstance(s, str) and s.strip():
                    out.append(
                        {
                            "id": f"tr-{lang}-{eid}-{j}",
                            "text": s,
                            "source": f"translations.{lang}",
                        }
                    )
    zhde = json.loads(ZH_DE_JSON.read_text(encoding="utf-8"))
    for entry in zhde.get("entries") or []:
        eid = entry.get("id", "zhde")
        for i, fr in enumerate(entry.get("from") or []):
            if isinstance(fr, str) and fr.strip():
                out.append(
                    {
                        "id": f"zhde-from-{eid}-{i}",
                        "text": fr,
                        "source": "zh_de.from",
                    }
                )
        to = entry.get("to")
        if isinstance(to, str) and to.strip():
            out.append(
                {
                    "id": f"zhde-to-{eid}",
                    "text": to,
                    "source": "zh_de.to",
                }
            )
    return out


@pytest.fixture(scope="module")
def pd_texts() -> list[dict]:
    return _load_pd_texts()


@pytest.fixture(scope="module")
def translated_texts() -> list[dict]:
    return _load_translated_sources()


def _run_layers(text: str, layers: list[str]) -> str:
    dz = load("density_zip", "DensityZip/density_zip.py")
    return dz.run_pipeline(layers, text, ns())


def _run_c(text: str) -> str:
    se = load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    return se.compress(text)


def _run_e(text: str) -> str:
    mz = load("morpho_zip", "MorphoZip/morpho_zip.py")
    return mz.compress(text)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_abrupt_fragments_ce_no_crash():
    """Fixed abrupt fragments through C, E, C→E — soft invariants only."""
    # Notes on observed (non-failing) behaviors worth not forgetting:
    # - ``three animal`` (singular) → CE ``3匹`` because E counters use animals?
    # - ``a`` alone → E strips the article → ``""`` (documented empty OK)
    # - unclosed ``[[keep:…`` / `` `keep:… `` left intact (no hang)
    # - JA particles still rewrite on truncated runs (は→&, も→+)
    for name, src in _ABRUPT_FRAGMENTS:
        meta_base = {"id": name, "source": "fabricated"}
        for label, fn in (
            ("C", _run_c),
            ("E", _run_e),
            ("CE", lambda t: _run_layers(t, ["C", "E"])),
        ):
            out = fn(src)
            _soft_ok(src, out, meta={**meta_base, "layer": label})


def test_abrupt_fragments_ceb_final_no_crash():
    """Same fragments through C→E→B-final-zh-de (still no restoration bar)."""
    for name, src in _ABRUPT_FRAGMENTS:
        out = _run_layers(src, ["C", "E", "B-final-zh-de"])
        _soft_ok(src, out, meta={"id": name, "layer": "CEB", "source": "fabricated"})


def test_pd_mid_split_random_ce(pd_texts, mid_seed, mid_n):
    """Seeded PD cuts (mid-token / phrase / sentence / markdown) → C→E soft OK."""
    rng = random.Random(mid_seed)
    n = min(mid_n, len(pd_texts))
    chosen = rng.sample(pd_texts, n)
    results = []
    for p in chosen:
        cutter = rng.choice(_CUTTERS)
        got = cutter(p["text"], rng)
        if got is None:
            # fall back to mid-sentence on short / awkward passages
            got = cut_mid_sentence(p["text"], rng)
        if got is None:
            continue
        chunk, meta = got
        meta = {**meta, "id": p["id"], "source": "pd"}
        out = _run_layers(chunk, ["C", "E"])
        _soft_ok(chunk, out, meta=meta)
        # also hit C and E alone (cheap; modules cached)
        _soft_ok(chunk, _run_c(chunk), meta={**meta, "layer": "C"})
        _soft_ok(chunk, _run_e(chunk), meta={**meta, "layer": "E"})
        results.append(meta)

    assert results, "no mid-split samples produced — check fixtures / cutters"

    # Reproducibility: same seed → same pattern ids + cut sizes
    rng2 = random.Random(mid_seed)
    chosen2 = rng2.sample(pd_texts, n)
    metas2 = []
    for p in chosen2:
        cutter = rng2.choice(_CUTTERS)
        got = cutter(p["text"], rng2)
        if got is None:
            got = cut_mid_sentence(p["text"], rng2)
        if got is None:
            continue
        metas2.append({**got[1], "id": p["id"]})
    assert [r["id"] for r in results] == [m["id"] for m in metas2]
    assert [r["pattern"] for r in results] == [m["pattern"] for m in metas2]
    assert [r["chars"] for r in results] == [m["chars"] for m in metas2]


def test_pd_mid_split_ceb_final(pd_texts, mid_seed, mid_n):
    """Offset seed: PD mid-splits through C→E→B-final-zh-de."""
    rng = random.Random(mid_seed + 23)
    n = min(mid_n, len(pd_texts))
    for p in rng.sample(pd_texts, n):
        got = cut_mid_token(p["text"], rng) or cut_mid_sentence(p["text"], rng)
        if got is None:
            continue
        chunk, meta = got
        out = _run_layers(chunk, ["C", "E", "B-final-zh-de"])
        _soft_ok(
            chunk,
            out,
            meta={**meta, "id": p["id"], "layer": "CEB", "source": "pd"},
        )


def test_translated_mid_split_ce(translated_texts, mid_seed, mid_n):
    """Mid-cut EN sources + abrupt ZH/DE/JA candidates through C→E."""
    # Prefer items long enough to cut meaningfully
    pool = [t for t in translated_texts if len(t["text"].strip()) >= 8]
    assert len(pool) >= 10
    rng = random.Random(mid_seed + 7)
    n = min(mid_n * 2, len(pool))  # a bit more variety; still small
    for t in rng.sample(pool, n):
        text = t["text"]
        # CJK-heavy → prefer mid_cjk; else mid_token / mid_sentence
        if _CJK_RUN.search(text):
            got = cut_mid_cjk(text, rng) or cut_mid_sentence(text, rng)
        else:
            got = cut_mid_token(text, rng) or cut_mid_phrase(text, rng)
            if got is None:
                got = cut_mid_sentence(text, rng)
        if got is None:
            # last resort: hard char budget cut (still mid-ish)
            cut_at = max(3, len(text) * 2 // 3)
            chunk = text[:cut_at]
            meta = {"pattern": "hard_char", "chars": len(chunk)}
        else:
            chunk, meta = got
        out = _run_layers(chunk, ["C", "E"])
        _soft_ok(
            chunk,
            out,
            meta={**meta, "id": t["id"], "source": t["source"], "layer": "CE"},
        )


def test_translated_mid_cjk_ceb(translated_texts, mid_seed):
    """All available mid-CJK cuts from translation banks → CEB soft OK."""
    rng = random.Random(mid_seed + 11)
    hits = 0
    for t in translated_texts:
        got = cut_mid_cjk(t["text"], rng)
        if got is None:
            continue
        chunk, meta = got
        out = _run_layers(chunk, ["C", "E", "B-final-zh-de"])
        _soft_ok(
            chunk,
            out,
            meta={
                **meta,
                "id": t["id"],
                "source": t["source"],
                "layer": "CEB",
            },
        )
        hits += 1
        if hits >= 8:  # keep light
            break
    assert hits >= 3, "expected some CJK runs in TesseraTalk fixtures"


def test_lone_surrogate_does_not_crash_but_not_utf8():
    """Lone UTF-16 surrogates: must not raise; UTF-8 encode may fail.

    # BUG?/documented: layers pass the codepoint through unchanged. Valid
    # UTF-8 inputs are covered by ``_soft_ok``; this case is intentionally
    # invalid Unicode text and only checks non-crash + str return.
    """
    src = chr(0xD83D)  # high surrogate, unpaired
    for label, fn in (
        ("C", _run_c),
        ("E", _run_e),
        ("CE", lambda t: _run_layers(t, ["C", "E"])),
    ):
        out = fn(src)
        assert isinstance(out, str), label
        # Current behavior: passthrough. Do not require utf-8.
        assert out == src or len(out) <= 4, (label, repr(out))


def test_cutters_deterministic_unit():
    """Cutter helpers themselves are pure given an RNG seed."""
    sample = (
        "The Hare was once boasting of his speed before the other animals. "
        "I accept your challenge today."
    )
    a = cut_mid_token(sample, random.Random(1))
    b = cut_mid_token(sample, random.Random(1))
    assert a is not None and a == b
    c = cut_mid_phrase(sample, random.Random(2))
    d = cut_mid_phrase(sample, random.Random(2))
    assert c is not None and c == d
    e = cut_mid_sentence(sample, random.Random(3))
    f = cut_mid_sentence(sample, random.Random(3))
    assert e is not None and e == f
    g = cut_mid_markdown(sample, random.Random(4))
    h = cut_mid_markdown(sample, random.Random(4))
    assert g is not None and g == h

    cjk = "我们今天下午三点开会。今日はとても良い天気です。"
    i = cut_mid_cjk(cjk, random.Random(5))
    j = cut_mid_cjk(cjk, random.Random(5))
    assert i is not None and i == j
    assert i[1]["pattern"] == "mid_cjk"
