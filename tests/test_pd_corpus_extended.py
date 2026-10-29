"""Extended copyright-free corpus: sha256 pins + zero crashes on every line.

C→E runs over every line of every file; C→E→B-final runs on a seeded quarter.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from tests._helpers import load, ns

EXT = Path(__file__).resolve().parent / "fixtures" / "pd_corpus" / "extended"
MANIFEST = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
FILES = [e["file"] for e in MANIFEST["files"]]


def _lines(fname: str) -> list[str]:
    raw = (EXT / fname).read_text(encoding="utf-8").splitlines()
    return [ln.split("\t", 1)[-1] for ln in raw if ln.strip()]


def test_extended_manifest_pins():
    assert len(FILES) == 8
    assert (EXT / "SOURCES.md").is_file()
    for e in MANIFEST["files"]:
        data = (EXT / e["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == e["sha256"], e["file"]
        assert e["license"] and e["source_url"].startswith("http")
        assert data.decode("utf-8").count("\n") == e["lines"]


@pytest.mark.parametrize("fname", FILES)
def test_extended_corpus_zero_crash(fname):
    dz = load("density_zip", "DensityZip/density_zip.py")
    args = ns()
    lines = _lines(fname)
    rng = random.Random(fname)
    sub = set(rng.sample(range(len(lines)), max(1, len(lines) // 4)))
    for i, s in enumerate(lines):
        out = dz.run_pipeline(["C", "E"], s, args)
        assert isinstance(out, str) and out.strip(), (fname, s)
        assert not out.lstrip().startswith(","), (fname, s, out)
        assert ",," not in out or ",," in s, (fname, s, out)
        if i in sub:
            out2 = dz.run_pipeline(["C", "E", "B-final-zh-de"], s, args)
            assert isinstance(out2, str) and out2.strip(), (fname, s)
