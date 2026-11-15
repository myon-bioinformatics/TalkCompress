"""ShorthandSessionEdge (C): compress / expand のリテラル置換・語境界・NFC・ASCII 畳み込み。

- shorthand_compress_literal: ShorthandSessionEdge.compress: 短縮形はリテラル置換、改行は入力どおり保持する。
- shorthand_expand_boundary: 監査: ShorthandSessionEdge.expand が単語の途中を展開しないこと。
- shorthand_expand_nonascii_boundary: expand: non-ASCII short forms respect Latin word edges; ASCII shorts stay bounded.
- shorthand_expand_nfc: ShorthandSessionEdge.expand must treat NFD input like NFC.
- shorthand_ascii_casefold: ASCII shorthand phrases must not case-fold onto Turkish ı/İ, ſ or the Kelvin sign.
"""

from __future__ import annotations

from ShorthandSessionEdge import shorthand_session_edge as S
from ShorthandSessionEdge import shorthand_session_edge as s
from ShorthandSessionEdge.shorthand_session_edge import Session
from ShorthandSessionEdge.shorthand_session_edge import _apply_map
from ShorthandSessionEdge.shorthand_session_edge import expand
from pathlib import Path
from shorthand_session_edge import Session
from shorthand_session_edge import compress
import subprocess
import sys
import unicodedata

import pytest


# ──── shorthand_compress_literal ──────────────────────────────────

"""ShorthandSessionEdge.compress: 短縮形はリテラル置換、改行は入力どおり保持する。"""


ROOT = Path(__file__).resolve().parents[1]


sys.path.insert(0, str(ROOT / "ShorthandSessionEdge"))


@pytest.mark.parametrize(
    "short",
    [r"C:\new\1x", r"\g<0>!", r"a\tb", "\\"],
)
def test_short_form_is_literal(short: str) -> None:
    sess = Session()
    sess.declare("my path", short)
    assert compress("see my path now", session=sess, ledger=False) == f"see {short} now"


@pytest.mark.parametrize(
    "text",
    ["hello\n", "a\r\nb", "a\u2028b", "x\n\ny\n", "a\rb\r\n", "ok\x0bthen\x85"],
)
def test_line_endings_preserved(text: str) -> None:
    assert compress(text, ledger=False) == text


def test_declaration_line_consumed_with_its_newline() -> None:
    out = compress("hereafter big thing = BT\r\nthe big thing\n", ledger=False)
    assert out == "the BT\n"


def test_single_declaration_and_empty() -> None:
    assert compress("hereafter a b = X", ledger=False) == ""
    assert compress("", ledger=False) == ""


def test_cli_does_not_double_trailing_newline() -> None:
    script = ROOT / "ShorthandSessionEdge" / "shorthand_session_edge.py"
    r = subprocess.run(
        [sys.executable, str(script), "compress", "--no-ledger"],
        input="hello\n", capture_output=True, text=True, check=True,
    )
    assert r.stdout == "hello\n"
    r = subprocess.run(
        [sys.executable, str(script), "compress", "--no-ledger", "--text", "hello"],
        capture_output=True, text=True, check=True,
    )
    assert r.stdout == "hello\n"


def test_main_in_process_keeps_single_newline(monkeypatch, capsys) -> None:
    import io

    from shorthand_session_edge import main

    monkeypatch.setattr(sys, "stdin", io.StringIO("hello\n"))
    assert main(["compress", "--no-ledger"]) == 0
    assert capsys.readouterr().out == "hello\n"
    assert main(["compress", "--no-ledger", "--text", "hello"]) == 0
    assert capsys.readouterr().out == "hello\n"


def test_nonascii_key_is_word_bounded() -> None:
    sess = Session({"señor": "Sr", "確認します": "確"})
    out = compress("señor y señora, señores; 確認しますね", session=sess, ledger=False)
    assert out == "Sr y señora, señores; 確ね"
    # NFD mark after the key must not expose a bare match
    assert compress("señore\u0301", session=sess, ledger=False) == "señore\u0301"


def test_nonascii_short_is_literal() -> None:
    sess = Session({"café": r"\1é"})
    assert compress("un café", session=sess, ledger=False) == r"un \1é"


def test_main_expand_keeps_single_newline(monkeypatch, capsys) -> None:
    import io

    from shorthand_session_edge import main

    monkeypatch.setattr(sys, "stdin", io.StringIO("brb\n"))
    assert main(["expand"]) == 0
    out = capsys.readouterr().out
    assert out.endswith("\n") and not out.endswith("\n\n")
    assert main(["expand", "--text", "brb"]) == 0
    out = capsys.readouterr().out
    assert out.endswith("\n") and not out.endswith("\n\n")


# ──── shorthand_expand_boundary ───────────────────────────────────

"""監査: ShorthandSessionEdge.expand が単語の途中を展開しないこと。"""


def test_expand_skips_inside_words():
    assert s.expand("pretty cute city") == "pretty cute city"
    assert s.expand("it's tyx") == "it's tyx"
    assert s.expand("don'ty") == "don'ty"


def test_expand_whole_tokens():
    assert s.expand("ty, cu") == "thank you, see you"
    assert s.expand("TY") == "TY"
    assert s.expand("wdyt?") == "what do you think?"


def test_expand_long_with_backslash():
    assert s.expand("zz", mapping={"a\\1b": "zz"}) == "a\\1b"


def test_word_bounded_edges():
    assert s._word_bounded("ab") == r"(?<![\w'’])(?a:ab)(?![\w'’])"
    assert s._word_bounded("w/") == r"(?<![\w'’])(?a:w/)"
    assert s._word_bounded("/w") == r"(?a:/w)(?![\w'’])"


# ──── shorthand_expand_nonascii_boundary ──────────────────────────

"""expand: non-ASCII short forms respect Latin word edges; ASCII shorts stay bounded."""


def test_ascii_short_not_inside_word():
    assert expand("Problem with PR") == "Problem with pull request"


def test_nonascii_latin_short_not_inside_word():
    m = {"sécurité": "séc"}
    assert expand("La sécheresse, séc.", mapping=m) == "La sécheresse, sécurité."


def test_nonascii_latin_short_not_after_letter():
    m = {"señal": "ñal"}
    assert expand("Señal y ñal", mapping=m) == "Señal y señal"


def test_nonascii_short_not_before_nfd_mark():
    m = {"señal": "señ"}
    out = expand("sen\u0303\u0301 señ", mapping=m)
    assert out == unicodedata.normalize("NFC", "sen\u0303\u0301 señal")


def test_kana_short_stays_substring():
    assert "りょ" not in expand("おkりょ")


# ──── shorthand_expand_nfc ────────────────────────────────────────

"""ShorthandSessionEdge.expand must treat NFD input like NFC."""


def test_expand_nfd_accent_does_not_expose_short():
    s = "Příliš žluťoučký kůň úpěl."
    assert S.expand(s) == s
    assert S.expand(unicodedata.normalize("NFD", s)) == s
    assert S.expand("PR ok") == "pull request ok"


# ──── shorthand_ascii_casefold ────────────────────────────────────

"""ASCII shorthand phrases must not case-fold onto Turkish ı/İ, ſ or the Kelvin sign."""


def test_apply_map_ignores_dotless_i():
    m = Session().effective
    assert _apply_map("in my opınıon", m) == "in my opınıon"
    assert _apply_map("İN MY OPİNİON", m) == "İN MY OPİNİON"


def test_apply_map_keeps_ascii_case_insensitivity():
    m = Session().effective
    assert _apply_map("In My Opinion", m) == "IMO"


def test_expand_ignores_turkish_i_variants():
    assert expand("ımo, İMO") == "ımo, İMO"
    assert expand("IMO, imo") == "in my opinion, in my opinion"


def test_suggest_hereafter_keeps_dotted_capital_i_word_whole():
    from ShorthandSessionEdge.shorthand_session_edge import suggest_hereafter

    longs = [d["long"] for d in suggest_hereafter("İstanbul güzel. İstanbul güzel.")]
    assert "i\u0307stanbul güzel" in longs
    assert not any(p.startswith("i stanbul") or "stanbul i" in p for p in longs)
