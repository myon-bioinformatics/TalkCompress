import pytest

from shared import asr_normalize as a

J = "日本語のテキストです。ありがとうございます。café — “hi” ok"


@pytest.mark.parametrize("phrase,out", [
    ("Talk Compress", "TalkCompress"), ("play wright", "playwright"),
    ("mini-match", "minimatch"), ("シブヤ", "シブヤ"), ("  ", ""),
])
def test_join_word(phrase, out):
    assert a.join_word(phrase) == out


def test_keep_unknown_brackets_only_when_uncertain():
    assert a.keep_unknown("iron mate") == "ironmate"
    assert a.keep_unknown("iron mate", uncertain=True) == "ironmate(?)"


@pytest.mark.parametrize("src,out", [
    ("to [Talk Compress?] now", "to TalkCompress(?) now"),
    ("to [Shibuya？] now", "to Shibuya(?) now"),
    ("to Shibuya{0.42} now", "to Shibuya(?) now"),
    ("to Shibuya{0.9} now", "to Shibuya now"),
])
def test_normalize_uncertain(src, out):
    assert a.normalize_uncertain(src) == out


@pytest.mark.parametrize("s", [
    "is it (really?) yes", "use {a|b} here", "(Shibuya？)", "x = {ok}", "[note] fine",
    "<?xml version='1.0'?><svg/>",
])
def test_ordinary_text_untouched_by_default(s):
    assert a.normalize_uncertain(s) == s


def test_opt_in_paren_and_alternatives():
    assert a.normalize_uncertain("to (Shibuya？) now", paren=True) == "to Shibuya(?) now"
    assert a.normalize_uncertain("to {Ironmate|Iron mate} now", alternatives=True) == "to Ironmate(?) now"


def test_marker_not_xml_pi():
    assert "<?" not in a.keep_unknown("x", True) and "?>" not in a.keep_unknown("x", True)


def test_marker_token_cost():
    tiktoken = pytest.importorskip("tiktoken")
    e = tiktoken.get_encoding("o200k_base")
    for w in ("TalkCompress", "minimatch", "Shibuya"):
        plain = len(e.encode(f"to {w} now"))
        assert len(e.encode(f"to {a.keep_unknown(w, True)} now")) - plain == 1
        assert len(e.encode(f"to <?{w}?> now")) - plain >= 2


@pytest.mark.parametrize("enc", ["cp1252", "latin-1"])
@pytest.mark.parametrize("s", [J, "Ação é ótimo", "Résumé naïve", "Привет мир", "ありがとう、ございます。"])
def test_repair_utf8_read_as_single_byte(enc, s):
    bad = s.encode().decode(enc, "replace")
    assert a.clean_mojibake(bad) == s


def test_double_mojibake():
    s = "café naïve ok"
    bad = s.encode().decode("cp1252").encode().decode("cp1252")
    assert a.clean_mojibake(bad) == s


def test_cp932_strict_roundtrip():
    s = "テキストです"
    bad = s.encode().decode("cp932", "replace")
    out = a.clean_mojibake(bad)
    assert a._badness(out) <= a._badness(bad)
    assert "キストで" in out


@pytest.mark.parametrize("s", [
    "Ã la carte", "naïve café", "Straße", "日本語のまま", "ÂŁ", "x ≥ 3 — ok",
    "ｶﾀｶﾅとｷｬﾗ", "半角ｶﾅのﾃｽﾄです", "café…", "naïve–ok", "é©", "à‰", "Ü™", "é„x",
])
def test_clean_text_unchanged(s):
    assert a.clean_mojibake(s) == s


def test_collapse_unrecoverable():
    assert a.collapse_unrecoverable("ok \ufffd\ufffd \ufffd end") == "ok \ufffd end"


@pytest.mark.parametrize("s", ["a\x00b", "x\ue000y", "\ufffd\x00\ufffd", "\U000f0000"])
def test_nul_and_private_use_preserved(s):
    assert a.clean_mojibake(s) == s
    assert a.collapse_unrecoverable("a\tb\nc") == "a\tb\nc"


def test_normalize_asr_pipeline():
    bad = "[Talk Compress?] " + "café".encode().decode("cp1252") + " \ufffd\ufffd"
    assert a.normalize_asr(bad) == "TalkCompress(?) café \ufffd"
