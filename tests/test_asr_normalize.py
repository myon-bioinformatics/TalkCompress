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
    assert a.keep_unknown("iron mate", uncertain=True) == "<?ironmate?>"


@pytest.mark.parametrize("src,out", [
    ("to [Talk Compress?] now", "to <?TalkCompress?> now"),
    ("to (Shibuya？) now", "to <?Shibuya?> now"),
    ("to {Ironmate|Iron mate} now", "to <?Ironmate?> now"),
    ("to Shibuya{0.42} now", "to <?Shibuya?> now"),
    ("to Shibuya{0.9} now", "to Shibuya now"),
    ("to <? mini match ?> now", "to <?minimatch?> now"),
    ("is it (really)? yes [note] {x}", "is it (really)? yes [note] {x}"),
])
def test_normalize_uncertain(src, out):
    assert a.normalize_uncertain(src) == out


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


@pytest.mark.parametrize("s", ["Ã la carte", "naïve café", "Straße", "日本語のまま", "ÂŁ", "x ≥ 3 — ok"])
def test_clean_text_unchanged(s):
    assert a.clean_mojibake(s) == s


def test_collapse_unrecoverable():
    assert a.collapse_unrecoverable("ok \ufffd\ufffd \ufffd\x01\ue000 end") == "ok \ufffd end"
    assert a.collapse_unrecoverable("a\tb\nc") == "a\tb\nc"


def test_normalize_asr_pipeline():
    bad = "[Talk Compress?] " + "café".encode().decode("cp1252") + " \ufffd\ufffd"
    assert a.normalize_asr(bad) == "<?TalkCompress?> café \ufffd"
