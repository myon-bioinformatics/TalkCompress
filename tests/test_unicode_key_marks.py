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
