"""コーパス取得スクリプト（fetch_corpus_lowres.py / fetch_corpus_major.py）と同梱サンプル。

- corpus_lowres: Script-specific checks for scripts/fetch_corpus_lowres.py.
- corpus_major: 主要10言語コーパス（#137）の取得スクリプトと同梱サンプルの検査。
"""

from __future__ import annotations

from pathlib import Path
import corpus_manifest as cm
import fetch_corpus_major as fm
import importlib.util
import json
import re
import sys

import pytest


# ──── corpus_lowres ───────────────────────────────────────────────

"""Script-specific checks for scripts/fetch_corpus_lowres.py.

File/manifest consistency (sha256, counts, bytes, o200k, licences, sizes) is
covered by tests/test_corpus_manifest.py; this file only checks what that
generic validator cannot see.
"""


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
    assert {r["tier"] for r in rows} == {"short"}
    assert rows[0]["id"] == "lowres-tatoeba-ko-0000" and rows[0]["license"] == "CC BY 2.0 FR"
    assert list(MOD.to_jsonl(rows).decode().splitlines()[0].split('"')[1::4]) == list(MOD.KEYS)


# FLORES-200 file codes (ISO 639-3 + ISO 15924), as shipped in flores200_dataset.tar.gz.
EXPECTED_FLORES = {
    "ko": "kor_Hang", "vi": "vie_Latn", "th": "tha_Thai", "id": "ind_Latn", "tr": "tur_Latn",
    "he": "heb_Hebr", "fa": "pes_Arab", "sw": "swh_Latn", "bn": "ben_Beng", "ta": "tam_Taml",
}


def test_flores_code_table_is_exact():
    assert MOD.FLORES == EXPECTED_FLORES
    text = LICENSES.read_text(encoding="utf-8")
    listed = dict(re.findall(r"([a-z]{2})=([a-z]{3}_[A-Z][a-z]{3})", text))
    assert listed == MOD.FLORES


# ──── corpus_major ────────────────────────────────────────────────

"""主要10言語コーパス（#137）の取得スクリプトと同梱サンプルの検査。"""


def _members(lang_code, sents, urls):
    meta = ("URL\tdomain\n" + "".join(u + "\tx\n" for u in urls)).encode()
    body = "\n".join(sents).encode()
    out = {}
    for split in ("dev", "devtest"):
        out[f"flores200_dataset/{split}/{lang_code}.{split}"] = body
        out[f"flores200_dataset/metadata_{split}.tsv"] = meta
    return out


def test_long_joiner_per_language():
    urls = ["u1", "u1", "u2"]
    _, ja = fm.build_flores("ja", _members("jpn_Jpan", ["あ。", "い。", "う。"], urls))
    _, zh = fm.build_flores("zh", _members("zho_Hans", ["甲。", "乙。", "丙。"], urls))
    _, en = fm.build_flores("en", _members("eng_Latn", ["A.", "B.", "C."], urls))
    assert [r["text"] for r in ja[:2]] == ["あ。い。", "う。"]
    assert [r["text"] for r in zh[:2]] == ["甲。乙。", "丙。"]
    assert [r["text"] for r in en[:2]] == ["A. B.", "C."]


def test_repo_long_equals_joined_medium_sentences():
    """同梱サンプルで、medium（1文）を元記事 url ごとに言語別区切りで連結したものが long と一致する。"""
    base = cm.MANIFEST.parent / "flores200"
    for lang in fm.LANGS:
        rows = [json.loads(x) for x in (base / f"{lang}.jsonl").read_text(encoding="utf-8").splitlines()]
        medium = [r for r in rows if r["tier"] == "medium"]
        long = [r for r in rows if r["tier"] == "long"]
        groups: list[tuple[str, list[str]]] = []
        for r in medium:
            if groups and groups[-1][0] == r["url"]:
                groups[-1][1].append(r["text"])
            else:
                groups.append((r["url"], [r["text"]]))
        complete = groups[:-1]  # 最後の記事はサンプル末尾で切れている可能性がある
        assert len(complete) >= 2, lang
        sep = "" if lang in ("ja", "zh") else " "
        for k, (url, sents) in enumerate(complete):
            assert long[k]["url"] == url, (lang, k)
            assert long[k]["text"] == sep.join(sents), (lang, k)


def _license_table_corpus_major():
    text = (cm.MANIFEST.parent / "LICENSES-major.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| [^|]+ \| (https://\S+) \| ([0-9a-f]{64}) \|$", text, re.M))


def test_license_table_matches_fetch_constants():
    want = {(fm.FLORES_URL, fm.FLORES_SHA256)}
    want |= {(fm.TATOEBA_URL.format(code=c), h) for c, h in fm.TATOEBA.values()}
    assert len(want) == 1 + len(fm.LANGS)
    assert _license_table_corpus_major() == want
