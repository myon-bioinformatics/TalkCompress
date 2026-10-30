"""Round-4 layer-unit tests: A export/negotiate, B bank+mosaic, C ledger, E counters.

DensityZip wiring for --translate-min → tests/integration/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- A: RuleBook export / import / threshold / negotiate ---


def test_rulebook_export_import_merge(tmp_path):
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    alice = rb.RuleBook.load(tmp_path / "alice.json", threshold=3)
    alice.declare("status update complete", "r1")
    alice.declare("ready and waiting", "r2")
    dump = tmp_path / "alice_export.json"
    alice.export_rules(dump)

    bob = rb.RuleBook.load(tmp_path / "bob.json", threshold=2)
    bob.declare("ping pong match", "r1")  # different long, same short preferred
    info = bob.import_rules(dump, merge=True)
    assert info["added"] >= 2
    assert bob._find_by_long("status update complete") is not None
    assert bob._find_by_long("ready and waiting") is not None
    # bob keeps own rule
    assert bob._find_by_long("ping pong match") is not None
    encoded = bob.encode_with_rules("please status update complete and ready and waiting")
    assert "status update complete" not in encoded.lower()
    assert "ready and waiting" not in encoded.lower()


def test_rulebook_set_threshold_and_cli(tmp_path, capsys):
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    book = rb.RuleBook.load(tmp_path / "book.json", threshold=5)
    book.set_threshold(2)
    assert book.threshold == 2
    book.save()

    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    rc = z.main(
        ["rule-threshold", "--state", str(tmp_path / "book.json"), "--threshold", "4"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "4"
    reloaded = rb.RuleBook.load(tmp_path / "book.json")
    assert reloaded.threshold == 4


def test_rulebook_negotiate_multi_peer(tmp_path):
    rb = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    hub = rb.RuleBook.load(tmp_path / "hub.json")
    p1 = rb.RuleBook()
    p1.declare("continuous integration pipeline", "ci")
    p2 = rb.RuleBook()
    p2.declare("end to end test suite", "e2e")
    p2.proposals.append({"long": "definition of done", "short": "dod", "count": 2})
    e1 = tmp_path / "p1.json"
    e2 = tmp_path / "p2.json"
    p1.export_rules(e1)
    p2.export_rules(e2)
    info = hub.negotiate([e1, e2], adopt_proposals=True)
    assert info["peers"] == 2
    assert hub._find_by_long("continuous integration pipeline")
    assert hub._find_by_long("end to end test suite")
    assert hub._find_by_long("definition of done")
    # CLI path
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    state = tmp_path / "cli_hub.json"
    rb.RuleBook.load(state).save()
    rc = z.main(
        [
            "rule-negotiate",
            "--state",
            str(state),
            "--import",
            str(e1),
            "--peer",
            str(e2),
        ]
    )
    assert rc == 0
    merged = rb.RuleBook.load(state)
    assert len(merged.rules) >= 2


# --- B: translation bank growth + mosaic interaction ---


def test_b_bank_new_entries_shorten():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    # bust cache after bank edits
    t.load_translation_bank.cache_clear()
    chosen, lang, n = t.pick_shortest_translation("Good night.")
    assert lang != "src"
    assert n < t.estimate_tokens("Good night.")
    chosen2, _, n2 = t.pick_shortest_translation("What time is it?")
    assert n2 < t.estimate_tokens("What time is it?")
    assert "ASAP" in t.pick_shortest_translation("as soon as possible")[0]


def test_b_mosaic_with_translate_min_interaction():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    t.load_translation_bank.cache_clear()
    text = "Good morning. 今日はとても良い天気ですね. See you later."
    plain = t.compress(text, rle=True, translate_min=False)
    mini = t.compress(text, rle=True, translate_min=True)
    # mosaic still has tags / pipes
    assert ":" in mini or "|" in mini
    # translate-min should not grow overall mosaic vs plain (token/char lean)
    assert t.estimate_tokens(t.expand(mini)) <= t.estimate_tokens(t.expand(plain))
    # round-trip expand still yields text
    expanded = t.expand(mini)
    assert expanded
    # B must NOT apply C ledger under→下
    keep = t.minify_by_translation("The cat is under the table.")
    assert "under" in keep.lower() or "下" not in keep or "桌下" in keep or "机の下" in keep
    # natural short may drop "under" word via ZH/JA — but never via C ledger glyph alone on EN path
    # Explicit: compress without translate leaves under
    assert "under" in t.compress("The cat is under the table.", translate_min=False).lower()


# --- C: ledger round-4 + chat pack ---


def test_c_ledger_spatial_and_conjunctions():
    from shared.ledger import apply_ledger_lex, convention_ids

    ids = convention_ids()
    assert "spatial-left-right" in ids
    assert "conj-moreover" in ids
    assert apply_ledger_lex("left and right sides") == "左右 sides"
    assert apply_ledger_lex("front and back") == "前後"
    assert apply_ledger_lex("inside and outside") == "内外"
    assert apply_ledger_lex("big and small") == "大小"
    assert "also" in apply_ledger_lex("moreover we continue")
    assert "moreover" not in apply_ledger_lex("moreover we continue").lower()
    assert apply_ledger_lex("nevertheless it works").startswith("but")
    assert "so" in apply_ledger_lex("therefore we stop")
    assert "e.g." not in apply_ledger_lex("for example cats")  # pruned (o200k)
    # bare clause "that is the plan" keeps its meaning; appositive gloss maps
    assert "i.e." not in apply_ledger_lex("that is the plan")
    assert "i.e." not in apply_ledger_lex("a car, that is, a vehicle")  # i.e. token loser

    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("check left and right carefully")
    assert "左右" in out
    out2 = s.compress("moreover please advise")
    assert "also" in out2.lower()
    assert "PA" in out2 or "please advise" not in out2.lower()


def test_c_chat_pack_and_map_growth():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    assert "chat" in s.list_packs()
    sess = s.Session()
    sess.load_packs(["chat"])
    out = s.compress("send a heads up in the group chat", session=sess)
    assert "HU" in out or "GC" in out
    out2 = s.compress("for your reference please")
    assert "FYR" in out2


# --- E: counters / grammar / smart quotes ---


def test_e_new_counters_and_grammar():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert "3台" in m.compress("I have 3 cars ready")
    assert "2棟" in m.compress("build 2 buildings here")
    assert "5杯" in m.compress("drink 5 cups tonight")
    assert "4組" in m.compress("prepare 4 pairs now")
    assert "7通" in m.compress("send 7 emails today")
    out = m.compress("additionally for example, that is, fine", unique=False, etymon=False)
    assert "+" in out  # additionally→+ (gap-fill; was also)
    assert "additionally" not in out.lower()
    assert "e.g." not in out and "for example" in out  # e.g. token loser
    assert "i.e." not in out and "that is" in out  # i.e. token loser
    # expand counters subset
    assert "vehicles" in m.expand("3台")


def test_e_smart_quoted_articles_kept():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    # straight quotes keep inner word
    assert "the" in m.compress('say "the" clearly', unique=False, etymon=False).lower()
    # smart quotes
    smart = "say “the” clearly"
    out = m.compress(smart, unique=False, etymon=False)
    assert "the" in out.lower()
    # unquoted still stripped
    plain = m.compress("say the clearly", unique=False, etymon=False)
    assert " the " not in f" {plain} ".lower()


def test_e_does_not_apply_c_ledger_or_ill_by_default():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("I will go under the table", unique=False, etymon=False, counters=False)
    assert "under" in out.lower()
    assert "I'll" not in out
