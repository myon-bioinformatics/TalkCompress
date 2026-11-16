"""RulePeerCodec (A) RuleBook: 共有ルールの成長、語境界、リテラル置換。

- rulebook: RulePeerCodec RuleBook: shared-rule growth (layer A core).
- rulebook_boundaries: 監査: rulebook の語境界と Unicode 対応。
- rulebook_literal_ascii_case: RulePeerCodec RuleBook: 置換はリテラル、ASCII 文字の大小無視は ASCII のみ。
"""

from __future__ import annotations

from RulePeerCodec.rulebook import Rule
from RulePeerCodec.rulebook import RuleBook
from RulePeerCodec.rulebook import _bounded
from RulePeerCodec.rulebook import _extract_phrases
from pathlib import Path
from rulebook import RuleBook
from tests._helpers import load as _load
import json
import sys

import pytest


# ──── rulebook ────────────────────────────────────────────────────

"""RulePeerCodec RuleBook: shared-rule growth (layer A core)."""


def test_rulebook_grows_after_repeated_phrases(tmp_path):
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    book = rb.RuleBook.load(tmp_path / "book.json", threshold=3)
    phrase = "ready and waiting"
    for _ in range(2):
        info = book.observe(f"please stay {phrase} now")
        assert info["adopted"] == []
        assert phrase.lower() in book.counts or phrase in book.counts
    info = book.observe(f"please stay {phrase} now")
    assert info["adopted"], "third sighting should auto-adopt"
    assert any(phrase.lower() in r.long.lower() for r in book.rules)
    book.save()
    assert (tmp_path / "book.json").is_file()


def test_rulebook_encode_decode_roundtrip(tmp_path):
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    book = rb.RuleBook.load(tmp_path / "book.json")
    book.declare("status update complete", "r1")
    book.save()
    encoded = book.encode_with_rules("please status update complete thanks")
    assert "r1" in encoded
    assert "status update complete" not in encoded.lower() or "r1" in encoded
    decoded = book.decode_with_rules(encoded)
    assert "status update complete" in decoded.lower()


def test_rulebook_declare_formats():
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    book = rb.RuleBook()
    assert book.ingest_line("rule: hello world => hw") is not None
    assert book._find_by_short("hw") is not None
    book2 = rb.RuleBook()
    assert book2.ingest_line(":: foo bar = fb") is not None
    assert book2.encode_with_rules("xx foo bar yy") == "xx fb yy"


def test_rule_sim_shortens_after_threshold(tmp_path, capsys):
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    state = tmp_path / "sim.json"
    corpus = tmp_path / "corpus.txt"
    line = "agents stay ready and waiting forever"
    corpus.write_text("\n".join([line] * 5) + "\n", encoding="utf-8")
    rc = z.main(
        [
            "rule-sim",
            "--state",
            str(state),
            "--corpus",
            str(corpus),
            "--threshold",
            "3",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.strip().splitlines() if ln.startswith("[")]
    assert len(lines) == 5
    # early turns: full length; later: shorter once r* appears
    first_len = int(lines[0].split("]")[1].split("→")[0].strip())
    last = lines[-1]
    last_after = int(last.split("→")[1].split()[0])
    assert last_after < first_len
    assert "r1" in last or "r2" in last or any(
        tok.startswith("r") and tok[1:].isdigit() for tok in last.split()
    )
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["rules"], "sim should have adopted at least one rule"


def test_rule_encode_with_optional_key(tmp_path, capsys):
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    state = tmp_path / "book.json"
    book = rb.RuleBook.load(state)
    book.declare("ping pong", "r1")
    book.save()
    rc = z.main(
        ["rule-encode", "--state", str(state), "--key", "secret", "--text", "do ping pong now"]
    )
    assert rc == 0
    env = capsys.readouterr().out.strip()
    # Envelope is base64url. The nonce is random, so a short token such as
    # "r1" (or even "ping") can appear in the ciphertext by chance. base64url
    # has no spaces, so the long phrase is a stable plaintext-absence check.
    # Magic, length, and the inner rule text are checked by decode.
    assert env
    assert " " not in env
    assert "ping pong" not in env
    inner = z.decode(env, key="secret")
    assert inner == b"do r1 now"
    # decode path
    class _C:
        def __init__(self):
            self.out = ""

        def write(self, s):
            self.out += s if isinstance(s, str) else s.decode()
            return len(s)

        def flush(self):
            pass

    old = sys.stdout
    buf = _C()
    try:
        sys.stdout = buf  # type: ignore[assignment]
        rc2 = z.main(
            ["rule-decode", "--state", str(state), "--key", "secret", "--text", env]
        )
    finally:
        sys.stdout = old
    assert rc2 == 0
    assert "ping pong" in buf.out


def test_crypto_roundtrip_still_works():
    """Do not regress classic RulePeerCodec envelope."""
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    env = z.encode(b"hello bots", key="k")
    assert z.decode(env, key="k") == b"hello bots"


# ──── rulebook_boundaries ─────────────────────────────────────────

"""監査: rulebook の語境界と Unicode 対応。"""


def _book():
    return RuleBook(rules=[Rule("r1", "in the", "r1"), Rule("r2", "ありがとう", "r2")])


def test_encode_does_not_rewrite_inside_words():
    b = _book()
    assert b.encode_with_rules("within these walls") == "within these walls"
    assert b.encode_with_rules("sit in the car") == "sit r1 car"
    assert b.encode_with_rules("In the end") == "r1 end"


def test_cjk_rule_roundtrips_without_spaces():
    b = _book()
    enc = b.encode_with_rules("はいありがとう")
    assert enc == "はいr2"
    assert b.decode_with_rules(enc) == "はいありがとう"


def test_decode_keeps_latin_word_boundary():
    b = _book()
    assert b.decode_with_rules("xr1 r1y r1") == "xr1 r1y in the"
    assert b.decode_with_rules("r1, r1") == "in the, in the"


def test_bounded_edges():
    assert _bounded("ab") == r"(?<![^\W\u3040-\u30ff\u3400-\u9fff])ab(?![^\W\u3040-\u30ff\u3400-\u9fff])"
    assert _bounded("あa") == r"あa(?![^\W\u3040-\u30ff\u3400-\u9fff])"
    assert _bounded("aあ") == r"(?<![^\W\u3040-\u30ff\u3400-\u9fff])aあ"
    assert _bounded("!") == "!"
    assert _bounded("") == ""


def test_extract_phrases_keeps_accented_words():
    got = _extract_phrases("ça va très bien")
    assert "ça va" in got and "très bien" in got
    assert "a va" not in got and "tr s" not in got
    assert "Привет мир" in _extract_phrases("Привет мир")


def test_corpus_rules_do_not_overlap_and_roundtrip():
    """規則どうしの重なり検出: 実コーパスで学習した全規則の組で往復できること。"""
    import itertools
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent
    lines = []
    for f in sorted((root / "fixtures" / "pd_corpus").glob("*.txt")):
        lines += [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    book = RuleBook(threshold=3)
    for ln in lines:
        book.observe(ln)
    rules = book.rules
    assert len(rules) >= 20
    for a, c in itertools.permutations(rules, 2):
        assert not re.search(_bounded(c.long), a.short, re.I)
        assert not re.search(_bounded(c.short), a.long)
        t = f"{a.long} {c.long}"
        assert book.decode_with_rules(book.encode_with_rules(t)).lower() == t.lower()
    for ln in lines:
        assert book.decode_with_rules(book.encode_with_rules(ln)).lower() == ln.lower()


# ──── rulebook_literal_ascii_case ─────────────────────────────────

"""RulePeerCodec RuleBook: 置換はリテラル、ASCII 文字の大小無視は ASCII のみ。"""


ROOT = Path(__file__).resolve().parents[1]


sys.path.insert(0, str(ROOT / "RulePeerCodec"))


@pytest.mark.parametrize("short", [r"C:\new\1x", r"\g<0>!", r"a\tb", "\\"])
def test_encode_decode_literal(short: str) -> None:
    book = RuleBook()
    book.declare("my path here", short)
    enc = book.encode_with_rules("see my path here now")
    assert enc == f"see {short} now"
    assert book.decode_with_rules(enc) == "see my path here now"


@pytest.mark.parametrize(
    "text",
    ["the opınıon panel", "the OPİNİON panel", "the ſkip list", "the \u212aind word"],
)
def test_unicode_fold_not_matched(text: str) -> None:
    book = RuleBook()
    for long in ("opinion panel", "skip list", "kind word"):
        book.declare(long)
    assert book.encode_with_rules(text) == text


def test_ascii_and_nonascii_case_still_fold() -> None:
    book = RuleBook()
    r1 = book.declare("opinion panel")
    r2 = book.declare("café crème")
    assert book.encode_with_rules("The OPINION Panel") == f"The {r1.short}"
    assert book.encode_with_rules("CAFÉ CRÈME ok") == f"{r2.short} ok"


def test_ascii_case_match_helper() -> None:
    from rulebook import _ascii_case_match

    assert _ascii_case_match("Kind", "kind")
    assert not _ascii_case_match("\u212aind", "kind")
    assert not _ascii_case_match("kind", "\u212aind")
    assert not _ascii_case_match("kin", "kind")


def test_decode_long_form_is_literal() -> None:
    book = RuleBook()
    rule = book.declare(r"dir C:\new\1x", "DP")
    assert book.decode_with_rules(f"open {rule.short} ok") == r"open dir C:\new\1x ok"
