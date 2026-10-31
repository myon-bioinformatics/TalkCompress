"""Curly→straight quote normalisation (MorphoZip) and scripts/quote_roundtrip.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("quote_roundtrip", ROOT / "scripts/quote_roundtrip.py")
qr = importlib.util.module_from_spec(_spec)
sys.modules["quote_roundtrip"] = qr
_spec.loader.exec_module(qr)
mz = qr.load_mz()


@pytest.mark.parametrize(
    ("src", "out"),
    [
        ("he said “go now”.", 'he said "go now".'),
        ("‘don’t go’ she said", "'don’t go' she said"),
        ("don’t", "don’t"),
        ("the dogs’ bones", "the dogs’ bones"),
        ("‘tis", "'tis"),
        ("‘a’\n‘b’", "'a'\n'b'"),
        ("‘it’s Zu\u0308rich’", "'it’s Zürich'"),
        ("“Café”, ‘naïve’", "\"Café\", 'naïve'"),
    ],
)
def test_normalize_quotes(src, out):
    import unicodedata

    assert mz.normalize_quotes(unicodedata.normalize("NFC", src)) == unicodedata.normalize("NFC", out)


def test_compress_uses_straight_quotes_and_keeps_protected():
    assert "“" not in mz.compress("He said “go home” now.")
    assert mz.compress("I don’t know, the dogs’ bones.") == "I don’t know, dogs’ bones."
    assert "“kept”" in mz.compress("[[keep:“kept”]] here")


@pytest.mark.parametrize(
    "src",
    ["“Hi,” he said. “Go.”", "‘one’ and “two”", "road—”\nWe", "(“x”)", "“a—b”"],
)
def test_restore_roundtrip(src):
    assert qr.restore_quotes(mz.normalize_quotes(src)) == src


def test_corner_roundtrip():
    s = "“a” ‘b’"
    assert qr.to_corner(s) == "「a」 ‘b’" and qr.from_corner(qr.to_corner(s)) == s


def test_check_and_main(capsys):
    texts = {"a.txt": "He said “go” now.", "b.txt": 'plain "x"', "c.txt": "x“a”"}
    res = qr.check(texts, mz, len)
    assert res["spans"] == 2 and res["roundtrip"]['Q""']["checked"] == 2
    assert res["roundtrip"]['Q""']["mismatches"] == ["c.txt"]
    assert res["rows"]['Q""']["bytes"] < res["rows"]["curly"]["bytes"]
    assert list(res["heavy"]) == ["a.txt"]
    empty = qr.check({}, mz, len)
    assert empty["heavy"] == {} and empty["per_span"] == {'Q""': 0.0, "Q「」": 0.0}
    pytest.importorskip("tiktoken")
    assert qr.main([]) == 0 and "roundtrip" in capsys.readouterr().out
    assert qr.main(["--json"]) == 0 and '"spans"' in capsys.readouterr().out
