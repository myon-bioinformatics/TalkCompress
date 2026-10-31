"""Role-differentiated bracket experiment (scripts/bracket_roles.py)."""

from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bracket_roles", ROOT / "scripts/bracket_roles.py")
br = importlib.util.module_from_spec(_spec)
sys.modules["bracket_roles"] = br
_spec.loader.exec_module(br)

S = "in possession of good fortune, for Paris, must"


@pytest.mark.parametrize(
    ("variant", "out"),
    [
        ("P1", "in(possession) of(good fortune), for(Paris), must"),
        ("P1m", "in possession of(good fortune), for Paris, must"),
        ("P2", "in(possession) of({good fortune}), for(Paris), must"),
        ("P3«»", "in«possession» of«good fortune», for«Paris», must"),
        ("P3‹›", "in‹possession› of‹good fortune›, for‹Paris›, must"),
        ("P3«»m", "in possession of«good fortune», for Paris, must"),
        ("P3‹›m", "in possession of‹good fortune›, for Paris, must"),
    ],
)
def test_variants(variant, out):
    assert br.apply(S, variant) == out


def test_quotes_and_unknown():
    assert br.apply('he said “go now” and "stay"', "Q「」") == "he said 「go now」 and 「stay」"
    assert br.apply("he said “go”", 'Q""') == 'he said "go"'
    for bad in ("P9", "Qxx", "P1x"):
        with pytest.raises(ValueError):
            br.apply("in good fortune", bad)


def test_nfc_safe():
    src = "in Zu\u0308rich for Paris, now"
    out = br.apply(src, "P1")
    assert out == "in Zürich for(Paris), now" and unicodedata.is_normalized("NFC", out)
    assert br.apply("in cafe\u0301 x", "P3«»") == "in café x"


def test_measure_and_main(capsys):
    rows = br.measure({"x.txt": "go to the store."}, lambda t: t.replace(" the", ""), len)
    assert rows["A"] == {"tokens": len("go to store."), "bytes": len("go to store.")}
    assert rows["P1"]["tokens"] == len("go to(store).")
    assert rows["P3«»"]["bytes"] == len("go to«store».".encode())
    assert rows["P1m"] == rows["A"]
    pytest.importorskip("tiktoken")
    assert br.main([]) == 0 and "P2:" in capsys.readouterr().out
    assert br.main(["--json"]) == 0 and '"A"' in capsys.readouterr().out
