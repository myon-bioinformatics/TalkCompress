"""Round-2 layer-unit tests: expand, frames, lex-policy, packs helpers.

Budget/role/trace/auto via DensityZip → tests/integration/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]


def test_morpho_expand_smoke():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    compressed = m.compress("I see 3 animals and 2 people")
    assert "3匹" in compressed
    expanded = m.expand(compressed)
    assert "3 animals" in expanded
    assert "2 people" in expanded
    # pack tokens
    packed = m.pack_tokens("hello,  world   こんにちは  です")
    assert "hello" in packed
    assert "world" in packed
    assert "こんにちは" in packed
    # whitespace collapsed; CJK runs stay glued
    assert "  " not in packed.replace(", ", ",")  # allow single space after comma
    assert "   " not in packed


def test_morpho_expand_cli(capsys):
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    rc = m.main(["--mode", "expand", "--text", "3匹 and 2人"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "animals" in out
    assert "people" in out


def test_shorthand_export_lexicon(tmp_path):
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    sess = s.Session()
    sess.declare("special widget", "SW")
    data = sess.export_lexicon()
    assert "map" in data
    assert "conventions" in data
    assert data["conventions"]["special widget"] == "SW"
    path = tmp_path / "lex.json"
    sess.export_lexicon_to(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert "as soon as possible" in loaded["map"]


def test_shorthand_suggest_hereafter():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    text = (
        "the continuous integration pipeline failed. "
        "fix continuous integration again. "
        "continuous integration is red."
    )
    suggestions = s.suggest_hereafter(text)
    assert suggestions
    assert any("continuous integration" in str(x["long"]) for x in suggestions)
    assert all("hereafter" in str(x["line"]) for x in suggestions)


def test_zip_frames_roundtrip():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    payloads = [b"msg one", b"msg two", b"msg three"]
    blob = z.encode_frames(payloads, key="frame-key", aad="batch")
    assert blob.count(b"\n") == 2
    back = z.decode_frames(blob, key="frame-key", aad="batch")
    assert back == payloads


def test_zip_env_key(monkeypatch):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    monkeypatch.setenv("TALKCOMPRESS_ZIP_KEY", "from-env")
    ns = z.argparse.Namespace(key=None, key_file=None)
    key = z._read_key(ns)
    # Default key_normalization="none": env text is passed as raw UTF-8 bytes.
    assert key == b"from-env"
    env = z.encode(b"hi", key=key)
    assert z.decode(env, key="from-env") == b"hi"


def test_lex_policy_load_dump(tmp_path):
    # Import via package path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import shared.lex_policy as lp

    dumped = lp.dump_policy()
    assert "fillers_en" in dumped
    assert "etymon_align" in dumped
    path = tmp_path / "pol.json"
    # Override fillers to a tiny set
    path.write_text(
        json.dumps({"fillers_en": ["xyzzy_filler"], "fillers_ja": []}),
        encoding="utf-8",
    )
    applied = lp.load_policy(path)
    assert applied["fillers_en"] == ["xyzzy_filler"]
    out = lp.strip_fillers("hello xyzzy_filler world")
    assert "xyzzy_filler" not in out
    assert "hello" in out
    # restore a fuller policy so other tests in same process aren't wrecked if order varies
    restore = tmp_path / "restore.json"
    restore.write_text(json.dumps(dumped), encoding="utf-8")
    lp.load_policy(restore)



def test_tessera_new_lang_cues():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    assert "it" in t._CUES and "nl" in t._CUES and "id" in t._CUES and "sv" in t._CUES
    # Italian-ish
    assert t.detect_lang("Il gatto non è con la ragazza.") in ("it", "en", "es", "pt", "fr")
    # Indonesian cues
    lang = t.detect_lang("yang tidak ada dengan untuk ini itu dari pada")
    assert lang == "id"


def test_tessera_preserve_newlines():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    src = "Hello there.\n\nこんにちは。"
    mosaic = t.compress(src, preserve_newlines=True)
    assert "¶" in mosaic
    back = t.expand(mosaic, preserve_newlines=True)
    assert "\n\n" in back
    assert "Hello" in back
    assert "こんにちは" in back


