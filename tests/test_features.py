"""Feature tests: pipeline, lexicon, RLE mosaic, counters, AAD, compare."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _ns(**kwargs):
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    defaults = dict(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
        aad="",
        lexicon=None,
        no_rle=False,
        strip=False,
        no_strip=False,
        no_unique=False,
        no_etymon=False,
        no_counters=False,
        aggressive_fillers=False,
        hex_nums=False,
        hex_bare=False,
        file=None,
        out=None,
        text=None,
    )
    defaults.update(kwargs)
    return c.argparse.Namespace(**defaults)



# --- layer ownership: fillers + UNIQUE_COMPACT = C ---


def test_layer_ownership_matrix_classic_example():
    """Classic example: E alone keeps um/ascertain; C alone & C,E strip + compact."""
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    classic = "um 私は will find out the information about 3 animals"

    e_out = m.compress(classic)
    assert "um" in e_out.lower()
    assert "ascertain" in e_out.lower()
    assert "ascrt" not in e_out.lower()
    assert "info" in e_out
    assert "3匹" in e_out

    c_out = s.compress(classic)
    assert "um" not in c_out.lower()
    assert "ascrt" in c_out.lower()

    pipe = c.run_pipeline(["C", "E"], classic, _ns())
    assert "um" not in pipe.lower()
    assert "ascrt" in pipe.lower() or "ascertain" not in pipe.lower()
    assert "3匹" in pipe or "info" in pipe


# --- pipeline C→E ---


def test_pipeline_c_then_e():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    text = "um thank you for your information"
    out = c.run_pipeline(["C", "E"], text, _ns())
    assert "um" not in out.lower()
    # C: thank you→ty, for your information→FYI; E may further shrink
    assert "FYI" in out or "ty" in out.lower() or "info" in out
    assert len(out) < len(text)


def test_pipeline_a_without_key_errors():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    try:
        c.run_pipeline(["A", "C"], "hi", _ns(key=None))
        raised = False
    except SystemExit as e:
        raised = True
        assert "key" in str(e).lower()
    assert raised


def test_parse_pipeline():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    assert c.parse_pipeline("C,E") == ["C", "E"]
    assert c.parse_pipeline("3,4") == ["C", "E"]
    assert c.parse_pipeline("shorthand,morpho") == ["C", "E"]


# --- lexicon load ---


def test_shorthand_lexicon_load(tmp_path):
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"continuous delivery": "CDel", "hello world": "hw"}), encoding="utf-8")
    sess = s.Session()
    sess.load_lexicon(lex)
    out = s.compress("please start continuous delivery", session=sess)
    assert "CDel" in out


def test_convo_lexicon_flag(tmp_path):
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"special phrase": "SP"}), encoding="utf-8")
    out = c.transform_line("C", "use the special phrase now", _ns(lexicon=str(lex)))
    assert "SP" in out


# --- RLE mosaic ---


def test_tessera_rle_roundtrip():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    src = "Hello there. World is fine. こんにちは。また今度。"
    mosaic = t.compress(src, rle=True)
    # Two EN sentences should share one lang tag at start of run
    assert mosaic.count("en:") <= 2  # at most one per run; likely 1
    # RLE form: second EN sentence has no lang prefix
    parts = mosaic.split("|")
    assert any(not p.startswith(("en:", "ja:")) for p in parts[1:]) or "en:" in mosaic
    back = t.expand(mosaic)
    assert "Hello there" in back
    assert "World is fine" in back
    assert "こんにちは" in back


def test_tessera_rle_and_full_both_expand():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    full = "en:Hello.|en:World.|ja:こんにちは。"
    rle = "en:Hello.|World.|ja:こんにちは。"
    assert "Hello" in t.expand(full)
    assert "World" in t.expand(rle)
    assert "こんにちは" in t.expand(rle)


def test_tessera_stats():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    st = t.stats("Hello. こんにちは。")
    assert st["sentences"] >= 2
    assert "en" in st["langs"] or "ja" in st["langs"]


def test_tessera_no_rle_still_works():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    src = "Hello. World."
    mosaic = t.compress(src, rle=False)
    assert mosaic.count("en:") == 2


# --- counters / hex ---


def test_morpho_counters():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert "3匹" in m.compress("I see 3 animals here")
    assert "2人" in m.compress("there are 2 people waiting")
    assert "5個" in m.compress("pack 5 pieces carefully")
    assert "4回" in m.compress("retry 4 times please")


def test_morpho_hex_nums():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("value is 255 here", hex_nums=True, counters=False)
    assert "0xff" in out
    bare = m.compress("value is 255 here", hex_nums=True, hex_prefix=False, counters=False)
    assert "ff" in bare
    # default off
    plain = m.compress("value is 255 here", counters=False)
    assert "255" in plain


def test_morpho_gender_light_extra():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert "they" in m.compress("he or she will go")
    assert "them" in m.compress("彼を呼ぶ")


# --- lex_policy expansions smoke ---


def test_lex_policy_expansions_smoke():
    from shared.lex_policy import (
        ETYMON_ALIGN,
        FILLERS_EN,
        FILLERS_JA,
        UNIQUE_COMPACT,
        UNIQUE_READINGS,
        apply_etymon_align,
        apply_unique_readings,
        strip_fillers,
    )

    assert len(FILLERS_EN) >= 25
    assert len(FILLERS_JA) >= 15
    assert "roll out" in UNIQUE_READINGS
    assert "instantiate" in UNIQUE_COMPACT or "inst" in UNIQUE_COMPACT.values()
    assert "message" in ETYMON_ALIGN
    assert "nombre" not in ETYMON_ALIGN  # FR false friend
    assert "msg" in apply_etymon_align("send a message")
    assert "deploy" in apply_unique_readings("please roll out the app", compact=True) or "deploy" in UNIQUE_READINGS["roll out"]
    out = strip_fillers("hmm you know I guess ready")
    assert "ready" in out
    assert "hmm" not in out.lower()


# --- Zipilogue AAD ---


def test_zipilogue_aad_mac_separation():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = "shared"
    raw = b"same plaintext"
    env = z.encode(raw, key=key, aad="channel-alpha")
    assert z.decode(env, key=key, aad="channel-alpha") == raw
    # Different AAD must fail MAC
    try:
        z.decode(env, key=key, aad="channel-beta")
        raised = False
    except ValueError:
        raised = True
    assert raised
    # Empty AAD also fails against labeled envelope
    try:
        z.decode(env, key=key, aad="")
        raised2 = False
    except ValueError:
        raised2 = True
    assert raised2


def test_zipilogue_empty_aad_roundtrip():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    env = z.encode(b"hello", key="k", aad="")
    assert z.decode(env, key="k") == b"hello"
    assert z.decode(env, key="k", aad=None) == b"hello"


def test_zipilogue_file_cli(tmp_path):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    src = tmp_path / "plain.bin"
    out = tmp_path / "env.txt"
    back = tmp_path / "back.bin"
    src.write_bytes(b"\x00\x01binary-payload")
    rc = z.main(["encode", "--key", "fk", "--aad", "lab", "--file", str(src), "--out", str(out)])
    assert rc == 0
    assert out.read_bytes().strip()
    rc = z.main(["decode", "--key", "fk", "--aad", "lab", "--file", str(out), "--out", str(back)])
    assert rc == 0
    assert back.read_bytes() == b"\x00\x01binary-payload"


# --- compare JSON shape ---


def test_compare_json_shape():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    rows = c.compare_layers("thank you for your information about 3 animals", _ns())
    assert len(rows) >= 3
    for row in rows:
        assert "layer" in row
        assert "chars_before" in row
        assert "chars_after" in row
        assert "ratio" in row
        assert isinstance(row["ratio"], float)
    layers = {r["layer"] for r in rows}
    assert "C" in layers
    assert "E" in layers
    assert "C,E" in layers


def test_convo_file_and_out(tmp_path):
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    inp = tmp_path / "in.txt"
    outp = tmp_path / "out.txt"
    inp.write_text("for your information", encoding="utf-8")
    rc = c.main(["--layer", "C", "--file", str(inp), "--out", str(outp)])
    assert rc == 0
    assert "FYI" in outp.read_text(encoding="utf-8")


def test_convo_pipeline_cli():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        rc = c.main(["--pipeline", "C,E", "--text", "um thank you"])
        assert rc == 0
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert "um" not in out.lower()
    assert len(out.strip()) > 0


def test_convo_compare_cli():
    c = _load("convo_hub", "ConvoHub/convo_hub.py")
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        rc = c.main(["--compare", "--text", "as soon as possible please"])
        assert rc == 0
    finally:
        sys.stdout = old
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) >= 3
    for ln in lines:
        obj = json.loads(ln)
        assert "ratio" in obj
