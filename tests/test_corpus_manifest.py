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
    "license_url": "https://creativecommons.org/licenses/by/2.0/fr/", "lang": "ja", "category": "tatoeba",
    "path": "tatoeba/ja.jsonl", "count": 1, "bytes": 3, "o200k_tokens": 1, "sha256": "a" * 64,
    "retrieved_at": "2026-11-01", "ai_roundtrip": "未測定",
}


def R(i="r1", **kw):
    """manifest GOOD（ja / CC BY 2.0 FR）と整合する完全なレコード。"""
    return {"id": i, "text": "あ", "lang": "ja", "tier": "short", "source": "tatoeba",
            "license": "CC BY 2.0 FR", "author": "a", "url": "https://tatoeba.org/s/1", **kw}


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
    ({"path": "../tatoeba/ja.jsonl"}, "path"),
    ({"path": "tatoeba/en.jsonl"}, "path"),
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
    assert errs == ["entries[1]: (category, lang, source) ('tatoeba', 'ja', 'tatoeba') が重複",
                    "entries[1]: path 'tatoeba/ja.jsonl' が重複"]



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
    d = tmp_path / "tatoeba"
    d.mkdir()
    f = d / "ja.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs) + "\n", encoding="utf-8")
    e = {**GOOD, **cm.measure(f, _Enc()), **(entry_patch or {})}
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(_m(e)), encoding="utf-8")
    return f, mp


def test_measure_and_check(tmp_path):
    recs = [R("a", text="あい"), R("b", text="ab", tier="long")]
    f, mp = _write(tmp_path, recs)
    got = cm.measure(f, _Enc())
    assert got["count"] == 2 and got["bytes"] == 8 and got["o200k_tokens"] == 4
    assert got["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert cm.check(mp, _Enc()) == []
    f.write_text(f.read_text(encoding="utf-8") + json.dumps(R("c", text="c")) + "\n", encoding="utf-8")
    errs = cm.check(mp, _Enc())
    assert {e.split(":")[1].split()[0] for e in errs} == {"count", "bytes", "o200k_tokens", "sha256"}


def test_check_missing_file_and_bad_record(tmp_path):
    f, mp = _write(tmp_path, [R()])

    def put(*lines):
        f.write_text("".join(x + "\n" for x in lines), encoding="utf-8")
        return cm.check(mp, _Enc())

    assert any("許可リスト外" in e for e in put(json.dumps(R(license="CC BY-NC 4.0"))))
    assert any("text がない" in e for e in put(json.dumps({k: v for k, v in R().items() if k != "text"})))
    assert any("tier" in e for e in put(json.dumps(R(tier="huge"))))
    (tmp_path / "tatoeba/ja.jsonl").unlink()
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

    def opener(url, timeout=None):
        assert timeout == cf.TIMEOUT
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
    _, mp = _write(tmp_path, [R()])
    assert cm.check(mp, _Enc()) == []
    (tmp_path / "asr").mkdir()
    (tmp_path / "asr" / "ja.jsonl").write_text("", encoding="utf-8")
    assert cm.check(mp, _Enc()) == ["asr/ja.jsonl: manifest に無い jsonl（孤児）"]


# ---- #134 レビュー対応 ----

@pytest.mark.parametrize("key", ["id", "text", "lang", "tier", "source", "license", "author", "url"])
@pytest.mark.parametrize("bad", ["missing", 1, None, ""])
def test_record_required_keys(tmp_path, key, bad):
    rec = R()
    if bad == "missing":
        del rec[key]
    else:
        rec[key] = bad
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    errs, texts = cm.validate_records(f)
    assert errs == [f"x.jsonl:1: {key} がない（空でない文字列が必要）"] and texts == []


@pytest.mark.parametrize("line", ['"str"', "1", "[1]", "null", "{bad json"])
def test_record_non_object_is_error_not_crash(tmp_path, line):
    f = tmp_path / "x.jsonl"
    f.write_text(line + "\n" + json.dumps(R()) + "\n", encoding="utf-8")
    errs, texts = cm.validate_records(f)
    assert len(errs) == 1 and errs[0].startswith("x.jsonl:1: ") and texts == ["あ"]
    with pytest.raises(ValueError):
        cm.measure(f, _Enc())


def test_record_lang_license_must_match_entry(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(R(lang="en")) + "\n" + json.dumps(R("r2", text="い", license="CC0 1.0")) + "\n", encoding="utf-8")
    assert cm.validate_records(f)[0] == []
    errs, _ = cm.validate_records(f, GOOD)
    assert errs == [
        "x.jsonl:1: lang 'en' が manifest（'ja'）と不一致",
        "x.jsonl:2: license 'CC0 1.0' が manifest（'CC BY 2.0 FR'）と不一致",
    ]
    _, mp = _write(tmp_path, [R()])
    (tmp_path / "tatoeba/ja.jsonl").write_text(json.dumps(R(lang="en")) + "\n", encoding="utf-8")
    assert any("manifest（'ja'）と不一致" in e for e in cm.check(mp, _Enc()))


def test_record_duplicate_id(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(R("a")) + "\n" + json.dumps(R("b", text="い")) + "\n" + json.dumps(R("a", text="う")) + "\n", encoding="utf-8")
    assert cm.validate_records(f)[0] == ["x.jsonl:3: id 'a' がファイル内で重複"]
    _, mp = _write(tmp_path, [R("a"), R("b", text="い")])
    (tmp_path / "tatoeba/ja.jsonl").write_text(json.dumps(R("a")) + "\n" + json.dumps(R("a", text="い")) + "\n", encoding="utf-8")
    assert any("重複" in e for e in cm.check(mp, _Enc()))


def test_duplicate_path_rejected():
    errs = cm.validate_manifest(_m(GOOD, {**GOOD, "id": "y", "source": "Other"}))
    assert errs == ["entries[1]: path 'tatoeba/ja.jsonl' が重複"]


def test_size_limits(tmp_path):
    (tmp_path / "a").write_bytes(b"x" * 10)
    (tmp_path / "b").write_bytes(b"x" * 10)
    assert cm.check_sizes(tmp_path, 10, 20) == []
    assert cm.check_sizes(tmp_path, 9, 20) == ["a: 10 バイトで 1 ファイル上限 9 を超過", "b: 10 バイトで 1 ファイル上限 9 を超過"]
    assert cm.check_sizes(tmp_path, 10, 19) == ["corpus 合計 20 バイトで上限 19 を超過"]
    assert cm.MAX_FILE_BYTES == 256 * 1024 and cm.MAX_TOTAL_BYTES == 5 * 1024 * 1024


def test_size_limits_enforced_by_check(tmp_path, monkeypatch):
    _, mp = _write(tmp_path, [R()])
    assert cm.check(mp, _Enc()) == []
    size = (tmp_path / "tatoeba/ja.jsonl").stat().st_size
    monkeypatch.setattr(cm, "MAX_FILE_BYTES", size - 1)
    assert any("1 ファイル上限" in e for e in cm.check(mp, _Enc()))
    monkeypatch.setattr(cm, "MAX_FILE_BYTES", 10**9)
    monkeypatch.setattr(cm, "MAX_TOTAL_BYTES", size)
    assert any("corpus 合計" in e for e in cm.check(mp, _Enc()))


def test_repo_corpus_within_limits():
    assert cm.check_sizes(cm.CORPUS_DIR) == []


def test_manifest_main_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cm, "_encoder", lambda: _Enc())
    f, mp = _write(tmp_path, [R()])
    assert cm.main(["check", "--manifest", str(mp)]) == 0
    assert capsys.readouterr().out.strip() == "OK"
    f.write_text(json.dumps(R(text="ちがう")) + "\n", encoding="utf-8")
    assert cm.main(["check", "--manifest", str(mp)]) == 1
    assert "NG" in capsys.readouterr().out
    assert cm.main(["measure", str(f)]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1


def test_update_writes_back(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cm, "_encoder", lambda: _Enc())
    f, mp = _write(tmp_path, [R()])
    f.write_text(json.dumps(R(text="あいう")) + "\n" + json.dumps(R("r2", text="xy")) + "\n", encoding="utf-8")
    assert cm.main(["update", "--manifest", str(mp)]) == 0
    e = json.loads(mp.read_text(encoding="utf-8"))["entries"][0]
    assert (e["count"], e["bytes"], e["o200k_tokens"]) == (2, 11, 5)
    assert e["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert cm.check(mp, _Enc()) == []


@pytest.mark.parametrize("bad", ["../x", "a/b", "..", ".hidden", "", "a\\b", 3])
def test_fetch_rejects_bad_id(tmp_path, bad):
    with pytest.raises(ValueError, match="^id .*保存先"):
        cf.cache_path({**GOOD, "id": bad}, tmp_path)
    with pytest.raises(ValueError):
        cf.fetch_entry({**GOOD, "id": bad, "fetch_url": "https://x"}, tmp_path, lambda *a, **k: 1 / 0)


def test_fetch_cache_path_inside(tmp_path):
    assert cf.cache_path({**GOOD, "id": "tatoeba:1.v2"}, tmp_path) == (tmp_path / "ja" / "tatoeba:1.v2").resolve()
    with pytest.raises(ValueError, match="^lang "):
        cf.cache_path({**GOOD, "lang": "../x"}, tmp_path)
    # 正規表現をすり抜けても resolve 後の包含チェックで止まる
    import re
    orig = cf.ID_RE
    try:
        cf.ID_RE = re.compile(r".*")
        with pytest.raises(ValueError, match="cache の外"):
            cf.cache_path({**GOOD, "id": "../../x"}, tmp_path)
    finally:
        cf.ID_RE = orig


def test_fetch_main_exit_codes(tmp_path, monkeypatch, capsys):
    data = b"ok\n"
    base = {k: v for k, v in GOOD.items() if k != "path"}
    e1 = {**base, "id": "e1", "fetch_url": "https://x/1", "sha256": hashlib.sha256(data).hexdigest()}
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(_m(e1)), encoding="utf-8")
    monkeypatch.setattr(cf.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(data))
    monkeypatch.setattr(cf.fetch_entry, "__defaults__", (cf.CACHE, lambda url, timeout=None: io.BytesIO(data)))
    cache = tmp_path / "c"
    assert cf.main(["--manifest", str(mp), "--cache", str(cache)]) == 0
    assert (cache / "ja" / "e1").read_bytes() == data
    mp.write_text(json.dumps(_m({**e1, "sha256": "0" * 64})), encoding="utf-8")
    (cache / "ja" / "e1").unlink()
    assert cf.main(["--manifest", str(mp), "--cache", str(cache)]) == 1
    assert cf.main(["--manifest", str(mp), "--cache", str(cache), "--id", "other"]) == 0
    mp.write_text(json.dumps(_m({**e1, "license": "CC BY-NC 4.0"})), encoding="utf-8")
    assert cf.main(["--manifest", str(mp), "--cache", str(cache)]) == 1
    assert "許可リスト外" in capsys.readouterr().err


def test_record_duplicate_text_within_file(tmp_path):
    f = tmp_path / "x.jsonl"
    # JSON エスケープ違いでも読んだ後の text が同じなら重複
    f.write_text(json.dumps(R("a", text="あ")) + "\n" + json.dumps(R("b", text="い")) + "\n"
                 + json.dumps(R("c", text="あ"), ensure_ascii=False) + "\n" + json.dumps(R("d", text="あ")) + "\n", encoding="utf-8")
    assert cm.validate_records(f)[0] == ["x.jsonl:3: text が 1 行目と重複", "x.jsonl:4: text が 1 行目と重複"]


def _two_files(tmp_path, ja_recs, en_recs):
    base = {k: v for k, v in GOOD.items()}
    entries = []
    for lang, recs in (("ja", ja_recs), ("en", en_recs)):
        d = tmp_path / "tatoeba"
        d.mkdir(exist_ok=True)
        f = d / f"{lang}.jsonl"
        f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        e = {**base, "id": lang, "lang": lang, "path": f"tatoeba/{lang}.jsonl"}
        entries.append({**e, **cm.measure(f, _Enc(), e)})
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(_m(*entries)), encoding="utf-8")
    return mp


def test_record_id_duplicate_across_files(tmp_path):
    mp = _two_files(tmp_path, [R("a"), R("b", text="い")], [R("z", lang="en", text="x")])
    assert cm.check(mp, _Enc()) == []
    mp = _two_files(tmp_path, [R("a"), R("b", text="い")], [R("b", lang="en", text="x")])
    assert cm.check(mp, _Enc()) == ["entries[1]: tatoeba/en.jsonl: レコード id 'b' が tatoeba/ja.jsonl と重複（ファイル間）"]


def test_same_text_across_langs_allowed(tmp_path):
    mp = _two_files(tmp_path, [R("a", text="OK")], [R("b", lang="en", text="OK")])
    assert cm.check(mp, _Enc()) == []


def test_duplicate_manifest_id_only():
    other = {**GOOD, "category": "wiki", "lang": "en", "source": "Wikipedia", "path": "wiki/en.jsonl"}
    assert cm.validate_manifest(_m(GOOD, other)) == ["entries[1]: id 'x' が重複"]


def test_source_dup_key_casefold():
    errs = cm.validate_manifest(_m(GOOD, {**GOOD, "id": "y", "source": "TATOEBA", "fetch_url": "https://x"} | {}))
    assert "entries[1]: (category, lang, source) ('tatoeba', 'ja', 'tatoeba') が重複" in errs


def test_record_source_matches_entry_casefold(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(R(source="TaToEbA")) + "\n" + json.dumps(R("r2", text="い", source="Wikipedia")) + "\n", encoding="utf-8")
    assert cm.validate_records(f, GOOD)[0] == ["x.jsonl:2: source 'Wikipedia' が manifest（'Tatoeba'）と不一致"]
