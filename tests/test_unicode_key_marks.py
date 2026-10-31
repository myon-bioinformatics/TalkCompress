import unicodedata

from MorphoZip.morpho_zip import compress
from Zipilogue.zipilogue import derive_key


def test_derive_key_nfc_nfd_equal():
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert derive_key(nfc) == derive_key(nfd)


def test_derive_key_bytes_unchanged():
    nfd = unicodedata.normalize("NFD", "café").encode()
    assert derive_key(nfd) != derive_key("café".encode())


def test_article_with_non_basic_combining_mark_kept():
    # U+1DC4 is a combining mark outside U+0300-036F
    out = compress("I saw a\u1DC4 b")
    assert "a\u1DC4" in out
    assert not unicodedata.combining(out.lstrip()[0])


# 3bot レビュー Should 2: U+0300–036F 版に戻すと落ちるテスト（U+1DC4 は範囲外の結合文字）
def test_article_surface_re_rejects_extended_mark():
    from MorphoZip.morpho_zip import _ARTICLE_SURFACE_RE

    assert _ARTICLE_SURFACE_RE.search("a\u1dc4") is None
    assert _ARTICLE_SURFACE_RE.search("a cat") is not None


def test_pack_tokens_keeps_extended_mark_in_word():
    from MorphoZip.morpho_zip import _PACK_SPLIT, pack_tokens

    assert pack_tokens("ka\u1dc4la x").startswith("ka\u1dc4la")
    assert "ka\u1dc4la" in _PACK_SPLIT.split("ka\u1dc4la x")


def test_is_wordish_extended_mark():
    from MorphoZip.morpho_zip import pack_tokens

    # _is_wordish が拡張結合文字を語扱いしないと、語の前後で区切りが変わる
    # 語の直後の ( の前に空白が入るのは、直前のトークンが語扱いのときだけ
    assert pack_tokens("ka\u1dc4la (x)") == "ka\u1dc4la (x)"


def test_suggest_hereafter_extended_mark_not_split():
    from ShorthandEdge.shorthand_edge import suggest_hereafter

    text = " ".join(["xa\u1dc4yword appears"] * 4)
    longs = [str(d["long"]) for d in suggest_hereafter(text)]
    assert longs, longs
    assert not any("xa yword" in s for s in longs), longs


def test_derive_key_nfc_not_nfkc():
    # 互換文字（ﬁ リガチャ）は fi と別の鍵（NFKC ではなく NFC）
    assert derive_key("\ufb01") != derive_key("fi")
