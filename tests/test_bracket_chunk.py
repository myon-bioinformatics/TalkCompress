"""Opt-in bracket-chunk experiment (scripts/bracket_chunk.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bracket_chunk", ROOT / "scripts/bracket_chunk.py")
bc = importlib.util.module_from_spec(_spec)
sys.modules["bracket_chunk"] = bc
_spec.loader.exec_module(bc)


def test_wrap_forms():
    s = "in possession of good fortune, must"
    assert bc.wrap(s, "()") == "in(possession) of(good fortune), must"
    assert bc.wrap(s, "[]", "space") == "in [possession] of [good fortune], must"
    assert bc.wrap("go to the store.", "「」", "keep", True) == "go to「store」."
    assert bc.wrap("go to the store.", "()", "none", True) == "go to store."
    assert bc.wrap("go to the store.", "()") == "go to(the store)."


def test_wrap_rejects_unknown_form():
    with pytest.raises(ValueError):
        bc.wrap("x", "()", "bogus")


def test_chunks_stop_and_skip():
    assert bc.chunks("said to him one day") == []
    assert bc.chunks("for Mrs. Long") == []
    assert bc.chunks("of ça truth") == []
    assert bc.chunks("of fooça") == []
    assert bc.chunks("of a b c d e") == []
    assert [c[3] for c in bc.chunks("of a b c, x")] == ["a b c"]
    assert [c[3] for c in bc.chunks("in want of wife")] == ["want", "wife"]
    assert bc.chunks("of") == [] and bc.chunks("") == []


def test_measure_and_corpus():
    texts = {"x.txt": "go to the store."}
    res = bc.measure(texts, lambda t: t.replace(" the", ""), len)
    rows = res["rows"]
    assert rows["comp:base"]["tokens"] == len("go to store.")
    assert rows["comp:keep()"]["tokens"] == len("go to(store).")
    assert rows["raw:keep「」"]["bytes"] == len("go to「store」.".encode())
    assert res["chunks_comp"] == 1 and res["chunks_raw"] == 1
    assert res["merge"]["()"] == {"extra_tokens": 3, "samples": 3}
    corpus = bc.load_corpus()
    assert len(corpus) >= 40


def test_main_runs(capsys):
    pytest.importorskip("tiktoken")
    assert bc.main([]) == 0
    assert "comp:base" in capsys.readouterr().out
    assert bc.main(["--json"]) == 0
    assert '"rows"' in capsys.readouterr().out


@pytest.mark.parametrize(
    "src",
    ["in Zu\u0308rich", "to the cafe\u0301", "of Malmo\u0308 now", "for nin\u0303o", "in Cre\u0300me", "of Sa\u0303o Paulo"],
)
def test_nfd_accents_not_split(src):
    import unicodedata

    nfc = unicodedata.normalize("NFC", src)
    out = bc.wrap(src, "()")
    assert out == bc.wrap(nfc, "()") and unicodedata.is_normalized("NFC", out)
    assert all(not unicodedata.combining(out[e]) for _p, _s, e, _i in bc.chunks(src) if e < len(out))
    assert bc.chunks("in Zu\u0308rich") == [] and bc.chunks("to cafe\u0301") == []
    assert bc.wrap("in Zu\u0308rich", "()") == "in Zürich"
    assert bc.wrap("in Gödel", "()") == "in Gödel" and bc.wrap("in café", "()") == "in café"


def test_chunk_boundaries():
    assert bc.chunks("of a b c d, x") == []
    assert [c[3] for c in bc.chunks("of a b c, x")] == ["a b c"]
    assert [c[3] for c in bc.chunks("for Paris.")] == ["Paris"]
    assert bc.chunks("for Mrs.") == [] and bc.chunks("for Dr.") == []
    assert [c[3] for c in bc.chunks("for paris.")] == ["paris"]
    assert bc.wrap("of a  b", "()") == "of(a)  b"
