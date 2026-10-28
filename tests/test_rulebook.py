"""Zipilogue RuleBook: shared-rule growth (layer A core)."""

from __future__ import annotations

import json
import sys

from tests._helpers import load as _load


def test_rulebook_grows_after_repeated_phrases(tmp_path):
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
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
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    book = rb.RuleBook.load(tmp_path / "book.json")
    book.declare("status update complete", "r1")
    book.save()
    encoded = book.encode_with_rules("please status update complete thanks")
    assert "r1" in encoded
    assert "status update complete" not in encoded.lower() or "r1" in encoded
    decoded = book.decode_with_rules(encoded)
    assert "status update complete" in decoded.lower()


def test_rulebook_declare_formats():
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    book = rb.RuleBook()
    assert book.ingest_line("rule: hello world => hw") is not None
    assert book._find_by_short("hw") is not None
    book2 = rb.RuleBook()
    assert book2.ingest_line(":: foo bar = fb") is not None
    assert book2.encode_with_rules("xx foo bar yy") == "xx fb yy"


def test_rule_sim_shortens_after_threshold(tmp_path, capsys):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
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
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
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
    """Do not regress classic Zipilogue envelope."""
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    env = z.encode(b"hello bots", key="k")
    assert z.decode(env, key="k") == b"hello bots"
