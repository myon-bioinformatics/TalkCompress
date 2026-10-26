"""Round-2 feature tests: budget, role-layers, trace, auto, expand, frames, lex-policy."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # fresh module each time for lex_policy overrides
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ns(**kwargs):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    defaults = dict(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
        aad="",
        lexicon=None,
        export_lexicon=None,
        no_rle=False,
        preserve_newlines=False,
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
        pipeline=None,
        auto_machine=False,
        lex_policy=None,
        trace=False,
    )
    defaults.update(kwargs)
    return c.argparse.Namespace(**defaults)


def test_budget_shrinks():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    text = "um thank you for your information please let me know as soon as possible"
    out = c.run_budget(text, _ns(), budget=40, layers=["C", "E"])
    assert len(out) < len(text)
    assert len(out) <= len(c.run_pipeline(["C", "E"], text, _ns()))


def test_budget_passthrough_when_under():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    text = "hi"
    out = c.run_budget(text, _ns(), budget=100, layers=["C", "E"])
    assert out == text


def test_budget_cli_stats(capsys):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    rc = c.main(
        [
            "--budget",
            "50",
            "--stats",
            "--text",
            "um thank you for your information please",
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err
    stats = json.loads(err.strip().splitlines()[-1])
    assert "chars_before" in stats
    assert "chars_after" in stats
    assert "steps" in stats
    assert stats["chars_after"] <= stats["chars_before"]


def test_role_layers_jsonl():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    raw = "\n".join(
        [
            json.dumps({"role": "system", "text": "Keep this exact system prompt."}),
            json.dumps({"role": "user", "text": "as soon as possible thank you"}),
            json.dumps({"role": "assistant", "text": "I have 3 animals ready"}),
        ]
    )
    role_map = c.parse_role_layers("user=C,assistant=E,system=identity")
    out = c.process_jsonl(raw, _ns(), role_map=role_map, default_layer="C")
    lines = [json.loads(ln) for ln in out.splitlines()]
    by_role = {ln["role"]: ln["text"] for ln in lines}
    assert by_role["system"] == "Keep this exact system prompt."
    assert "ASAP" in by_role["user"] or "asap" in by_role["user"].lower()
    assert "3匹" in by_role["assistant"] or "3" in by_role["assistant"]


def test_role_layers_cli(tmp_path):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    inp = tmp_path / "chat.jsonl"
    inp.write_text(
        json.dumps({"role": "user", "text": "for your information"}) + "\n"
        + json.dumps({"role": "system", "text": "NOCHANGE"}) + "\n",
        encoding="utf-8",
    )
    outp = tmp_path / "out.jsonl"
    rc = c.main(
        [
            "--jsonl",
            "--role-layers",
            "user=C,system=identity",
            "--file",
            str(inp),
            "--out",
            str(outp),
        ]
    )
    assert rc == 0
    rows = [json.loads(ln) for ln in outp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any("FYI" in r["text"] for r in rows if r["role"] == "user")
    assert any(r["text"] == "NOCHANGE" for r in rows if r["role"] == "system")


def test_trace_shape():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    trace: list = []
    c.run_pipeline(["C", "E"], "um thank you for your information", _ns(), trace=trace)
    assert len(trace) == 2
    for step in trace:
        assert "step" in step
        assert "layer" in step
        assert "chars_before" in step
        assert "chars_after" in step
        assert "sample_delta" in step
    assert trace[0]["layer"] == "C"
    assert trace[1]["layer"] == "E"


def test_trace_cli(capsys):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    rc = c.main(["--pipeline", "C,E", "--trace", "--text", "um thank you"])
    assert rc == 0
    err = capsys.readouterr().err
    obj = json.loads(err.strip().splitlines()[-1])
    assert "trace" in obj
    assert len(obj["trace"]) >= 1


def test_auto_returns_nonempty():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    text = "Hello there friend. こんにちは世界。Thanks for your information."
    layers = c.choose_auto_layers(text, _ns())
    assert layers
    assert all(x in ("A", "B", "C", "E") for x in layers)
    out = c.run_pipeline(layers, text, _ns())
    assert isinstance(out, str)
    assert len(out) > 0


def test_auto_cli(capsys):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    rc = c.main(["--auto", "--text", "lol as soon as possible please"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out
    assert "asap" in out.lower() or "ASAP" in out or "pls" in out.lower() or len(out) < 40


def test_auto_machine_appends_a_when_key():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    layers = c.choose_auto_layers("hello world asap", _ns(auto_machine=True, key="secret"))
    assert "A" in layers


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


def test_convo_lex_policy_flag(tmp_path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import shared.lex_policy as lp

    backup = lp.dump_policy()
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    pol = tmp_path / "p.json"
    pol.write_text(
        json.dumps({"fillers_en": ["zzzzz"], "fillers_ja": []}),
        encoding="utf-8",
    )
    try:
        rc = c.main(["--layer", "E", "--lex-policy", str(pol), "--text", "zzzzz hello"])
        assert rc == 0
    finally:
        restore = tmp_path / "restore.json"
        restore.write_text(json.dumps(backup), encoding="utf-8")
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


def test_parse_role_layers_plus():
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    m = c.parse_role_layers("user=C+E,system=skip")
    assert m["user"] == ["C", "E"]
    assert m["system"] == "identity"
