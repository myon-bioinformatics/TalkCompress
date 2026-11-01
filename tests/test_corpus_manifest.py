"""scripts/corpus_manifest.py と corpus_fetch.py の検証器テスト。"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import corpus_fetch as cf  # noqa: E402
import corpus_manifest as cm  # noqa: E402

GOOD = {
    "id": "x", "source": "Tatoeba", "url": "https://tatoeba.org/", "license": "CC BY 2.0 FR",
    "license_url": "https://creativecommons.org/licenses/by/2.0/fr/", "lang": "ja", "category": "sentence",
    "path": "sentence/ja.jsonl", "count": 1, "bytes": 3, "o200k_tokens": 1, "sha256": "a" * 64,
    "retrieved_at": "2026-11-01", "ai_roundtrip": "未測定",
}


def _m(*entries):
    return {"schema_version": 1, "entries": list(entries)}


def test_repo_manifest_matches_files():
    assert cm.check() == []


def test_good_entry_ok():
    assert cm.validate_manifest(_m(GOOD)) == []


@pytest.mark.parametrize("lic", ["CC BY-NC 4.0", "CC BY-ND 4.0", "unknown", "CC BY-NC-SA 4.0"])
def test_disallowed_license(lic):
    assert any("許可リスト外" in e for e in cm.validate_manifest(_m({**GOOD, "license": lic})))


@pytest.mark.parametrize("key", cm.REQUIRED)
def test_missing_required(key):
    e = copy.deepcopy(GOOD)
    del e[key]
    assert cm.validate_manifest(_m(e)) == [f"entries[0]: {key} がない"]


@pytest.mark.parametrize("patch,needle", [
    ({"category": "Bad Cat"}, "category"),
    ({"lang": "Japanese"}, "lang"),
    ({"count": -1}, "count"),
    ({"bytes": 1.5}, "bytes"),
    ({"o200k_tokens": True}, "o200k_tokens"),
    ({"sha256": "A" * 64}, "sha256"),
    ({"retrieved_at": "2026/11/01"}, "retrieved_at"),
    ({"ai_roundtrip": ""}, "ai_roundtrip"),
    ({"path": "/abs/short.jsonl"}, "path"),
    ({"path": "../sentence/ja.jsonl"}, "path"),
    ({"path": "sentence/en.jsonl"}, "path"),
    ({"path": "asr/ja.jsonl"}, "path"),
])
def test_bad_fields(patch, needle):
    errs = cm.validate_manifest(_m({**GOOD, **patch}))
    assert errs and all(needle in e for e in errs), errs


def test_path_xor_fetch_url():
    e = {k: v for k, v in GOOD.items() if k != "path"}
    assert any("どちらか" in x for x in cm.validate_manifest(_m(e)))
    assert any("どちらか" in x for x in cm.validate_manifest(_m({**GOOD, "fetch_url": "https://x"})))
    assert cm.validate_manifest(_m({**e, "fetch_url": "https://x"})) == []


def test_top_level_and_duplicates():
    assert cm.validate_manifest([]) == ["manifest は object"]
    assert "schema_version は 1" in cm.validate_manifest({"schema_version": 2, "entries": []})
    assert cm.validate_manifest({"schema_version": 1}) == ["entries は配列"]
    assert cm.validate_manifest(_m("x")) == ["entries[0]: object ではない"]
    assert any("重複" in e for e in cm.validate_manifest(_m(GOOD, GOOD)))
    errs = cm.validate_manifest(_m(GOOD, {**GOOD, "id": "y"}))
    assert errs == ["entries[1]: (category, lang, source) ('sentence', 'ja', 'Tatoeba') が重複"]



def test_schema_json_in_sync():
    s = json.loads((ROOT / "tests/fixtures/corpus/manifest.schema.json").read_text(encoding="utf-8"))
    item = s["properties"]["entries"]["items"]
    assert set(item["required"]) == set(cm.REQUIRED)
    assert set(item["properties"]["license"]["enum"]) == cm.ALLOWED_LICENSES
    assert "tier" not in item["properties"]


class _Enc:
    def encode(self, t):
        return list(t)  # 1 文字 = 1 トークンの偽エンコーダ


def _write(tmp_path, recs, entry_patch=None):
    d = tmp_path / "sentence"
    d.mkdir()
    f = d / "ja.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs) + "\n", encoding="utf-8")
    e = {**GOOD, **cm.measure(f, _Enc()), **(entry_patch or {})}
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(_m(e)), encoding="utf-8")
    return f, mp


def test_measure_and_check(tmp_path):
    recs = [{"text": "あい", "license": "CC0 1.0", "tier": "short"}, {"text": "ab", "license": "CC BY 4.0", "tier": "long"}]
    f, mp = _write(tmp_path, recs)
    got = cm.measure(f, _Enc())
    assert got["count"] == 2 and got["bytes"] == 8 and got["o200k_tokens"] == 4
    assert got["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert cm.check(mp, _Enc()) == []
    f.write_text(f.read_text(encoding="utf-8") + json.dumps({"text": "c", "license": "CC0 1.0", "tier": "short"}) + "\n", encoding="utf-8")
    errs = cm.check(mp, _Enc())
    assert {e.split(":")[1].split()[0] for e in errs} == {"count", "bytes", "o200k_tokens", "sha256"}


def test_check_missing_file_and_bad_record(tmp_path):
    _, mp = _write(tmp_path, [{"text": "a", "license": "CC0 1.0", "tier": "short"}])
    (tmp_path / "sentence/ja.jsonl").write_text('{"text": "a", "license": "CC BY-NC 4.0", "tier": "short"}\n', encoding="utf-8")
    assert any("許可リスト外" in e for e in cm.check(mp, _Enc()))
    (tmp_path / "sentence/ja.jsonl").write_text('{"license": "CC0 1.0", "tier": "short"}\n', encoding="utf-8")
    assert any("text がない" in e for e in cm.check(mp, _Enc()))
    (tmp_path / "sentence/ja.jsonl").write_text('{"text": "a", "license": "CC0 1.0", "tier": "huge"}\n', encoding="utf-8")
    assert any("tier" in e for e in cm.check(mp, _Enc()))
    (tmp_path / "sentence/ja.jsonl").write_text('{"license": "CC0 1.0", "tier": "short"}\n', encoding="utf-8")
    assert any("text がない" in e for e in cm.check(mp, _Enc()))
    (tmp_path / "sentence/ja.jsonl").unlink()
    assert any("がない" in e for e in cm.check(mp, _Enc()))


def test_seed_records_are_attributed():
    for f in (ROOT / "tests/fixtures/corpus").glob("*/*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            assert r["license"] in cm.ALLOWED_LICENSES and r["tier"] in cm.TIERS
            assert r["author"] and r["url"].startswith("https://"), f


def test_fetch_verifies_sha(tmp_path):
    data = "テスト\n".encode()
    e = {**GOOD, "fetch_url": "https://example.invalid/x", "sha256": hashlib.sha256(data).hexdigest()}
    calls = []

    def opener(url):
        calls.append(url)
        return io.BytesIO(data)

    p = cf.fetch_entry(e, tmp_path, opener)
    assert p.read_bytes() == data and calls == [e["fetch_url"]]
    cf.fetch_entry(e, tmp_path, opener)  # キャッシュ済みなら再取得しない
    assert len(calls) == 1
    bad = {**e, "id": "y", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="sha256 不一致"):
        cf.fetch_entry(bad, tmp_path, opener)
    assert not (tmp_path / "ja" / "y").exists()
    p.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        cf.fetch_entry(e, tmp_path, opener)


def test_orphan_jsonl_detected(tmp_path):
    _, mp = _write(tmp_path, [{"text": "a", "license": "CC0 1.0", "tier": "short"}])
    assert cm.check(mp, _Enc()) == []
    (tmp_path / "asr").mkdir()
    (tmp_path / "asr" / "ja.jsonl").write_text("", encoding="utf-8")
    assert cm.check(mp, _Enc()) == ["asr/ja.jsonl: manifest に無い jsonl（孤児）"]
