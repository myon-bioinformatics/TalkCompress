"""Script-specific checks for scripts/fetch_corpus_lowres.py.

File/manifest consistency (sha256, counts, bytes, o200k, licences, sizes) is
covered by tests/test_corpus_manifest.py; this file only checks what that
generic validator cannot see.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fetch_corpus_lowres.py"
LICENSES = ROOT / "tests" / "fixtures" / "corpus" / "LICENSES-lowres.md"

_spec = importlib.util.spec_from_file_location("fetch_corpus_lowres", SCRIPT)
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)


def _license_table() -> dict[str, str]:
    """Parse the 取得元 table of LICENSES-lowres.md into {url: sha256}."""
    rows = {}
    for line in LICENSES.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"\| [^|]+ \| (https://\S+) \| `([0-9a-f]{64})` \|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_license_table_matches_script_pins_exactly():
    expected = {MOD.FLORES_URL: MOD.FLORES_SHA256}
    expected.update({MOD.TATOEBA_URL.format(code=c): sha for c, sha in MOD.TATOEBA.values()})
    assert _license_table() == expected
    assert set(MOD.TATOEBA) == set(MOD.FLORES) == set(MOD.LANGS)


def test_fetch_rejects_sha256_mismatch(tmp_path):
    (tmp_path / ("0" * 64)).write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="sha256 mismatch"):
        MOD.fetch("https://example.invalid/x", "0" * 64, tmp_path)


def test_opus_codes_are_registered_as_iso639_1():
    assert MOD.tatoeba_source("fa").endswith(", pes)")
    assert MOD.tatoeba_source("sw").endswith(", swh)")


def _fake_flores(lang: str, sents: list[str], urls: list[str]) -> dict[str, bytes]:
    code = MOD.FLORES[lang]
    meta = "URL\tdomain\n" + "".join(f"{u}\tx\n" for u in urls)
    out = {}
    for split in ("dev", "devtest"):
        out[f"flores200_dataset/{split}/{code}.{split}"] = "\n".join(sents).encode()
        out[f"flores200_dataset/metadata_{split}.tsv"] = meta.encode()
    return out


def test_long_join_adds_exactly_one_space_per_boundary():
    sents = ["ประโยคแรก ", "ประโยคสอง", "อีกเรื่อง"]
    medium, long = MOD.build_flores("th", _fake_flores("th", sents, ["u1", "u1", "u2"]))
    assert [r["text"] for r in long[:2]] == ["ประโยคแรก ประโยคสอง", "อีกเรื่อง"]
    assert [r["url"] for r in long[:2]] == ["u1", "u2"]
    assert {r["tier"] for r in medium} == {"medium"} and {r["tier"] for r in long} == {"long"}
    assert len({r["id"] for r in medium + long}) == len(medium + long)


def test_metadata_length_mismatch_stops():
    with pytest.raises(SystemExit, match="metadata"):
        MOD.build_flores("ko", _fake_flores("ko", ["a", "b"], ["u1"]))


def test_short_filters_length_and_duplicates(tmp_path, monkeypatch):
    import gzip
    long_line = "x" * (MOD.SHORT_MAX_CHARS + 1)
    blob = gzip.compress(f"안녕\n\n안녕\n{long_line}\n고마워\n".encode())
    monkeypatch.setattr(MOD, "fetch", lambda url, sha, cache: blob)
    rows = MOD.build_short("ko", tmp_path)
    assert [r["text"] for r in rows] == ["안녕", "고마워"]
    assert rows[0]["id"] == "lowres-tatoeba-ko-0000" and rows[0]["license"] == "CC BY 2.0 FR"
    assert list(MOD.to_jsonl(rows).decode().splitlines()[0].split('"')[1::4]) == list(MOD.KEYS)
