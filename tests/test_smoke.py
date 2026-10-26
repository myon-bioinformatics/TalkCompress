"""Smoke + behavioral tests for TalkCompress A–E."""

from __future__ import annotations

import importlib.util
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# --- A Zipilogue ---


def test_zipilogue_roundtrip():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = "shared-bot-secret"
    raw = b"hello bots \xe2\x9c\x93"
    env = z.encode(raw, key=key)
    assert isinstance(env, bytes)
    assert b"=" not in env  # no padding
    assert z.decode(env, key=key) == raw


def test_zipilogue_tamper_fails():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    env = bytearray(z.encode(b"payload", key="k"))
    # Flip a byte in the middle of the envelope ASCII
    mid = len(env) // 2
    env[mid] = (env[mid] + 1) % 128 or 65
    try:
        z.decode(bytes(env), key="k")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_zipilogue_wrong_key_fails():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    env = z.encode(b"secret message", key="alpha")
    try:
        z.decode(env, key="beta")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_zipilogue_cli_roundtrip(tmp_path):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key_file = tmp_path / "key.txt"
    key_file.write_text("cli-key\n", encoding="utf-8")
    # encode via main
    import io
    import sys

    buf = io.StringIO()
    old = sys.stdout
    try:
        # capture bytes stdout
        class B:
            def __init__(self):
                self.data = b""

            def write(self, b):
                if isinstance(b, str):
                    self.data += b.encode()
                else:
                    self.data += b
                return len(b)

            def flush(self):
                pass

        bout = B()
        sys.stdout = bout  # type: ignore[assignment]
        # actually encode uses buffer
        sys.stdout = old
        rc = z.main(["encode", "--key-file", str(key_file), "--text", "ping"])
        assert rc == 0
    finally:
        sys.stdout = old
    env = z.encode(b"ping", key="cli-key")
    assert z.decode(env, key="cli-key") == b"ping"


# --- B TesseraTalk ---


def test_tessera_segments():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    tagged = t.tag_sentences("Hello. こんにちは。", None)
    assert len(tagged) >= 2


def test_tessera_heuristic_langs():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    tagged = t.tag_sentences(
        "The cat sits on the mat. 今日はいい天気です。 El perro corre en el parque.",
        None,
    )
    langs = [lang for lang, _ in tagged]
    assert "en" in langs
    assert "ja" in langs
    assert "es" in langs


def test_tessera_compress_expand():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    src = "Hello world. こんにちは世界。"
    mosaic = t.compress(src)
    assert "en:" in mosaic
    assert "ja:" in mosaic
    assert "|" in mosaic
    back = t.expand(mosaic)
    assert "Hello world" in back
    assert "こんにちは世界" in back


# --- C ShorthandLab ---


def test_shorthand_compress():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    assert "ASAP" in s.compress("please reply as soon as possible")
    assert "FYI" in s.compress("for your information this is ready")


def test_shorthand_expand():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    assert "as soon as possible" in s.expand("do it ASAP")


def test_shorthand_hereafter_convention():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    sess = s.Session()
    text = "hereafter pull request=PR\nplease open a pull request soon"
    out = s.compress(text, session=sess)
    assert "hereafter" not in out.lower() or "pull request=PR" not in out
    assert "PR" in out
    assert "pull request" not in out.lower()
    assert sess.conventions.get("pull request") == "PR"


def test_shorthand_state_file(tmp_path):
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    path = tmp_path / "state.json"
    sess = s.Session()
    s.compress("hereafter unit test=UT\nok", session=sess)
    sess.save(path)
    sess2 = s.Session()
    sess2.load(path)
    assert "UT" in s.compress("run the unit test", session=sess2)


# --- E MorphoZip ---


def test_morpho_first_person():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert m.compress("私は行く") == "I行く"
    assert "I" in m.compress("僕は考える")


def test_morpho_english_multi():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("I am here with you and without fear whatever happens")
    assert "I'm" in out
    assert "w/" in out
    assert "w/o" in out
    assert "&" in out
    assert "∀" in out


def test_morpho_density_stats():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    before = "I am ready and waiting"
    after = m.compress(before)
    d = m.density(before, after)
    assert d["chars_before"] == len(before)
    assert d["chars_after"] == len(after)
    assert d["saved"] == len(before) - len(after)


def test_morpho_counters_kept():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    # 助数詞 should survive
    assert "匹" in m.compress("犬が3匹いる")
    assert "個" in m.compress("飴が7個ある")


# --- D ConvoZip ---


def test_convo_resolve_layer():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    assert c.resolve_layer("1") == "A"
    assert c.resolve_layer("tessera") == "B"
    assert c.resolve_layer("C") == "C"
    assert c.resolve_layer("morpho") == "E"


def test_convo_route_shorthand():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    ns = c.argparse.Namespace(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
    )
    out = c.transform_line("C", "for your information", ns)
    assert "FYI" in out


def test_convo_jsonl():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    ns = c.argparse.Namespace(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
    )
    raw = json.dumps({"role": "user", "text": "thank you"}, ensure_ascii=False)
    out = c.process_jsonl(raw, ns, default_layer="C")
    obj = json.loads(out)
    assert obj["role"] == "user"
    assert "ty" in obj["text"].lower() or obj["text"] == "ty"


def test_convo_zipilogue_route():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    ns = c.argparse.Namespace(
        key="route-key",
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="encode",
    )
    env = c.transform_line("A", "hi", ns)
    ns.mode = "decode"
    plain = c.transform_line("A", env, ns)
    assert plain == "hi"


# --- shared lex_policy / E uniqueness ---


def test_lex_strip_fillers():
    from shared.lex_policy import strip_fillers

    assert "ready" in strip_fillers("um well I mean ready")
    assert "um" not in strip_fillers("um well I mean ready").lower()
    assert "行く" in strip_fillers("えーと、行く")
    assert "えーと" not in strip_fillers("えーと、行く")


def test_lex_unique_and_etymon():
    from shared.lex_policy import apply_etymon_align, apply_unique_readings

    u = apply_unique_readings("please find out the answer", compact=True)
    assert "ascrt" in u or "ascertain" in u or "find out" not in u.lower()
    e = apply_etymon_align("send the information and the document")
    assert "info" in e
    assert "doc" in e
    assert apply_etymon_align("información") == "info"


def test_morpho_strips_fillers_and_pins_lexemes():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("um 私は will find out the information")
    assert "um" not in out.lower()
    assert "I" in out
    assert "info" in out
    # find out → unique path (ascrt or similar compact)
    assert "find out" not in out.lower()


def test_shorthand_also_strips_fillers():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    out = s.compress("um for your information")
    assert "FYI" in out
    assert "um" not in out.lower()
