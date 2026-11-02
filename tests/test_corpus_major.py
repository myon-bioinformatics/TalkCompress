"""主要10言語コーパス（#137）の取得スクリプトと同梱サンプルの検査。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import corpus_manifest as cm  # noqa: E402
import fetch_corpus_major as fm  # noqa: E402

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


def _license_table():
    text = (cm.MANIFEST.parent / "LICENSES-major.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| [^|]+ \| (https://\S+) \| ([0-9a-f]{64}) \|$", text, re.M))


def test_license_table_matches_fetch_constants():
    want = {(fm.FLORES_URL, fm.FLORES_SHA256)}
    want |= {(fm.TATOEBA_URL.format(code=c), h) for c, h in fm.TATOEBA.values()}
    assert len(want) == 1 + len(fm.LANGS)
    assert _license_table() == want
