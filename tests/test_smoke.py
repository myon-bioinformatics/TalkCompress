from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_zipilogue_roundtrip():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = b"secret"
    raw = b"hello bots"
    assert z.decode(z.encode(raw, key=key), key=key) == raw


def test_shorthand_compress():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    assert "ASAP" in s.compress("please reply as soon as possible")


def test_morpho_first_person():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert m.compress("私は行く") == "I行く"


def test_tessera_segments():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    tagged = t.tag_sentences("Hello. こんにちは。", ["en", "ja"])
    assert len(tagged) >= 2
