"""主要10言語コーパス（#137）の取得スクリプトと同梱サンプルの検査。"""
from __future__ import annotations

import json
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


def test_repo_ja_zh_long_have_no_inserted_space():
    base = cm.MANIFEST.parent / "flores200"
    for lang in ("ja", "zh"):
        for line in (base / f"{lang}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["tier"] == "long":
                assert "。 " not in r["text"], r["id"]
