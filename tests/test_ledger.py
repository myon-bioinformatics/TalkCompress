"""ShorthandEdge (C) agreed-convention ledger: load + C-applied lex."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ledger_file_exists_and_loads():
    from shared.ledger import convention_ids, default_ledger_path, list_conventions, load_ledger

    path = default_ledger_path()
    assert path.is_file()
    assert path == ROOT / "ShorthandEdge" / "ledger" / "conventions.json"
    assert "ShorthandEdge" in str(path)
    assert "ConvoHub" not in str(path)
    assert "DensityZip" not in str(path)
    assert not (ROOT / "DensityZip" / "ledger").exists()
    assert not (ROOT / "ConvoHub").exists()
    data = load_ledger()
    assert data["version"] >= 2
    assert "meta" in data
    assert data["meta"]["base_mix"] == ["en", "zh", "ja"]
    ids = convention_ids()
    assert "spatial-under" in ids
    assert "uneven-凹凸" in ids
    assert "policy-base-mix" in ids
    lex = list_conventions(kind="lex", apply_layer="C")
    assert any(c["id"] == "spatial-under" for c in lex)
    # E MorphoZip closed-POS registrations live as apply_layer=E (metrics/inventory;
    # rewrite ownership stays on E; C apply_ledger_lex does not consume them).
    e_lex = list_conventions(kind="lex", apply_layer="E")
    assert any(c["id"] == "pronoun-I" for c in e_lex)
    assert any(c["id"] == "prep-from" for c in e_lex)
    assert any(c["id"] == "particle-kara" for c in e_lex)
    assert all(c.get("to") != "fr" for c in e_lex)
    all_lex = list_conventions(kind="lex")
    # zero-bit-delta rows pruned; ~100 base + EN contraction abbrev family (c-ill…)
    assert 14 <= len(all_lex) <= 200
    policy = list_conventions(kind="policy")
    assert len(policy) >= 1
    assert policy[0]["payload"]["prefer_short_alphabet_cognates"] is True


def test_ledger_lex_under_below_and_凹凸():
    from shared.ledger import apply_ledger_lex

    assert "下" in apply_ledger_lex("under the table")
    assert "under" not in apply_ledger_lex("under the table").lower()
    assert "下" in apply_ledger_lex("below average")
    assert "below" not in apply_ledger_lex("below average").lower()
    assert "上" in apply_ledger_lex("above zero")
    assert "上下" == apply_ledger_lex("up and down")
    assert "上下" == apply_ledger_lex("above and below")
    assert "凹凸" in apply_ledger_lex("デコボコな道")
    assert "凹凸" in apply_ledger_lex("bumpy road")
    assert "凹凸" in apply_ledger_lex("uneven surface")
    # do not mangle understand
    assert "understand" in apply_ledger_lex("I understand now").lower()


def test_shorthand_applies_ledger_under_and_凹凸():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("put it under the table")
    assert "下" in out
    assert "under" not in out.lower()

    out2 = s.compress("below average results")
    assert "下" in out2
    assert "below" not in out2.lower()

    out3 = s.compress("この道はデコボコだ")
    assert "凹凸" in out3
    assert "デコボコ" not in out3

    out4 = s.compress("bumpy path")
    assert "凹凸" in out4

    # opt-out
    kept = s.compress("under the table", ledger=False)
    assert "under" in kept.lower()


def test_morpho_does_not_apply_ledger_under():
    """E alone should leave under/凹凸 alone (C owns ledger lex)."""
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("put it under the table", unique=False, etymon=False, counters=False)
    assert "under" in out.lower()
    assert "下" not in out

    out3 = m.compress("この道はデコボコだ", unique=False, etymon=False, counters=False)
    assert "デコボコ" in out3
    assert "凹凸" not in out3



def test_furniture_table_to_desk_lexeme_not_sql():
    """Furniture table → 机 (or allowed 桌/桌子); SQL/tech keeps table."""
    from shared.ledger import apply_ledger_lex, list_conventions

    furniture = list_conventions(kind="lex", apply_layer="C")
    row = next(c for c in furniture if c["id"] == "furniture-table")
    assert row["to"] == "机"
    assert set(row.get("allowed_to") or []) >= {"机", "桌"}
    assert row.get("skip_sql_tech") is True

    out = apply_ledger_lex("put it on the table")
    assert "机" in out or "桌" in out
    assert "table" not in out.lower()

    out2 = apply_ledger_lex("The lamp is under the table")
    assert "下" in out2
    assert ("机" in out2 or "桌" in out2)
    assert "table" not in out2.lower()

    # SQL / tech keep English table
    for sql in (
        "CREATE TABLE users",
        "create table users",
        "SELECT * FROM users_table JOIN orders",
        "sql table schema",
        "drop table accounts",
        "alter table t add column x",
        "INSERT INTO my_table VALUES (1)",
        "the database table users",
        "query the db table",
    ):
        kept = apply_ledger_lex(sql)
        assert "table" in kept.lower(), f"expected table kept in {sql!r} → {kept!r}"
        assert "机" not in kept and "桌" not in kept, f"furniture lex leaked into {sql!r} → {kept!r}"


def test_shorthand_furniture_table_and_sql():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("put it on the table")
    assert "机" in out or "桌" in out
    assert "table" not in out.lower()

    sql = s.compress("CREATE TABLE users")
    assert "table" in sql.lower()
    assert "机" not in sql and "桌" not in sql


def test_ambiguity_gate_moreover_also():
    """Clear moreover→also; collision / prefer_precision keep moreover."""
    from shared.ledger import apply_ledger_lex

    clear = apply_ledger_lex("moreover we continue")
    assert "also" in clear.lower()
    assert "moreover" not in clear.lower()

    # short form already present → keep moreover
    collide = apply_ledger_lex("moreover we also need time")
    assert "moreover" in collide.lower()
    assert collide.lower().count("also") == 1

    # prefer_precision → keep original even without collision
    precise = apply_ledger_lex("moreover we continue", prefer_precision=True)
    assert "moreover" in precise.lower()
    assert "also" not in precise.lower()

    # therefore→so clear vs precision
    assert "so" in apply_ledger_lex("therefore we stop").lower()
    assert "therefore" in apply_ledger_lex("therefore we stop", prefer_precision=True).lower()


def test_shorthand_prefer_precision_flag():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    short = s.compress("moreover we continue")
    assert "also" in short.lower()
    long = s.compress("moreover we continue", prefer_precision=True)
    assert "moreover" in long.lower()


def test_lex_dual_metrics_schema_and_samples():
    """kind=lex must carry token + bit; sample under/moreover/table."""
    from shared.ledger import (
        compute_lex_metrics,
        list_conventions,
        load_ledger,
        validate_ledger_metrics,
        validate_lex_metrics,
    )

    assert validate_ledger_metrics(strict=True) == []

    by_id = {c["id"]: c for c in list_conventions(kind="lex")}
    for cid in ("spatial-under", "conj-moreover", "furniture-table"):
        c = by_id[cid]
        assert "metrics" in c
        m = c["metrics"]
        assert isinstance(m["token"]["before"], int)
        assert isinstance(m["token"]["after"], int)
        assert isinstance(m["bit"]["before"], int)
        assert isinstance(m["bit"]["after"], int)
        assert m["bit"]["model"] in ("utf8", "inventory")
        assert "utf8" in m["bit"]
        assert "TesseraTalk" in m["token"]["via"]
        assert "MorphoZip" in m["bit"]["via"]
        # Short form should not increase both views for these samples
        assert m["token"]["after"] <= m["token"]["before"]
        assert m["bit"]["utf8"]["after"] <= m["bit"]["utf8"]["before"]

    under = by_id["spatial-under"]["metrics"]
    assert under["token"]["sample_from"] == "under"
    assert under["token"]["before"] == 2 and under["token"]["after"] == 1
    assert under["bit"]["model"] == "utf8"
    assert under["bit"]["before"] == 40 and under["bit"]["after"] == 24

    moreover = by_id["conj-moreover"]["metrics"]
    assert moreover["token"]["sample_from"] == "moreover"
    assert moreover["token"]["before"] == 2 and moreover["token"]["after"] == 1

    table = by_id["furniture-table"]["metrics"]
    assert table["token"]["after"] == 1
    assert table["bit"]["utf8"]["after"] == 24

    # policy may omit / null metrics
    policy = list_conventions(kind="policy")[0]
    assert policy.get("metrics") in (None, {}) or "token" not in (policy.get("metrics") or {})

    # compute helper matches ledger for under→下
    computed = compute_lex_metrics("under", "下")
    assert computed["token"] == under["token"]
    assert computed["bit"]["before"] == under["bit"]["before"]
    assert computed["bit"]["after"] == under["bit"]["after"]

    # reject incomplete lex metrics
    bad = {"id": "x", "kind": "lex", "from": ["foo"], "to": "bar"}
    issues = validate_lex_metrics(bad, strict=True)
    assert any("missing metrics" in i for i in issues)

    data = load_ledger()
    assert data["version"] >= 2
    note_blob = " ".join(data["meta"].get("notes") or [])
    assert "estimate_tokens" in note_blob
    assert "utf8_bits" in note_blob or "closed_inventory" in note_blob


def test_compute_lex_metrics_inventory_model():
    """Optional inventory_name switches bit.model to inventory (E closed bits)."""
    from shared.ledger import compute_lex_metrics

    m = compute_lex_metrics("and", "&", inventory_name="conjunction")
    assert m["bit"]["model"] == "inventory"
    assert m["bit"]["inventory"]["name"] == "conjunction"
    assert m["bit"]["inventory"]["bits_per"] == m["bit"]["before"] == m["bit"]["after"]
    assert "utf8" in m["bit"]
    assert m["token"]["via"].startswith("B ")


def test_ledger_pos_registrations_dual_metrics():
    """Pronoun/particle/prep/aux E rows + C etc. carry dual metrics; fr not canonical."""
    from shared.ledger import list_conventions, validate_ledger_metrics

    assert validate_ledger_metrics(strict=True) == []
    by_id = {c["id"]: c for c in list_conventions(kind="lex")}
    for cid in (
        "pronoun-I",
        "pronoun-yo",
        "pronoun-私たち",
        "particle-to",
        "particle-kara",
        "prep-with",
        "prep-from",
        "prep2-without",
        "aux-can",
        "aux-neg-can",
        "e-conj-because",
        "compare-ge",
        "conj-etc",
    ):
        assert cid in by_id, cid
        m = by_id[cid]["metrics"]
        assert isinstance(m["token"]["before"], int)
        assert isinstance(m["bit"]["before"], int)
        assert m["bit"]["model"] in ("utf8", "inventory")
        assert "utf8" in m["bit"]

    assert by_id["prep-from"]["to"] == "←"
    assert by_id["prep-from"]["apply_layer"] == "E"
    assert by_id["prep-from"]["inventory"] == "preposition"
    assert "fr" in by_id["prep-from"]["from"]
    assert by_id["particle-kara"]["to"] == "←"
    assert by_id["particle-kara"].get("extended") is True
    assert by_id["particle-kara"]["metrics"]["bit"]["inventory"]["extended"] is True
    # C still owns spatial / furniture apply
    assert by_id["spatial-under"]["apply_layer"] == "C"
    assert by_id["conj-etc"]["apply_layer"] == "C"
    # deferred-at-100 batch (restored after zero-bit prune)
    assert "c-brb" in by_id and by_id["c-brb"]["to"] == "brb"
    assert "c-afaik" in by_id and by_id["c-afaik"]["to"] == "AFAIK"
    assert by_id["e-conj-whereas"]["to"] == "∵"
    assert by_id["e-conj-whereas"].get("extended") is True
    # no lex emits fr
    assert all(c.get("to") != "fr" for c in by_id.values())


def test_abbrev_family_contractions_synced():
    """c-ill-style EN contractions are C family=abbrev; code is rewrite source."""
    from shared.ledger import apply_ledger_lex, list_conventions, validate_ledger_metrics
    from shared.lex_policy import EN_CONTRACTION_SPEC, apply_en_contractions, en_contraction_ledger_rows

    assert validate_ledger_metrics(strict=True) == []
    by_id = {c["id"]: c for c in list_conventions(kind="lex")}

    # Every live SPEC row with utf8 shrink is registered
    for row in en_contraction_ledger_rows():
        cid = row["id"]
        assert cid in by_id, cid
        c = by_id[cid]
        assert c["apply_layer"] == "C"
        assert c["family"] == "abbrev"
        assert c["abbrev_kind"] == "contraction"
        assert c.get("ledger_apply") is False
        assert c.get("rewrite_via") == "apply_en_contractions"
        assert c["to"] == row["to"]
        m = c["metrics"]
        assert m["bit"]["utf8"]["delta"] < 0, cid

    # Spec ↔ apply path
    assert ("ill", "I will", "I'll") in EN_CONTRACTION_SPEC
    assert apply_en_contractions("I will go") == "I'll go"
    assert apply_en_contractions("do not go") == "don't go"
    assert apply_en_contractions("cannot go") == "can't go"

    # Registration-only: ledger apply must NOT emit I'll from I will
    assert "I'll" not in apply_ledger_lex("I will go")
    # latin abbrevs still apply via ledger
    assert "e.g." in apply_ledger_lex("for example we try")
    assert by_id["conj-etc"]["family"] == "abbrev"
    assert by_id["conj-for-example"]["abbrev_kind"] == "latin"
    assert by_id["c-asap"]["family"] == "abbrev"
    assert by_id["c-asap"]["abbrev_kind"] == "acronym"

    # E rows for polarity remain E; no duplicate I'll ownership
    assert by_id["aux-neg-can"]["apply_layer"] == "E"
    assert by_id["aux-neg-can"]["to"] == "!can"



def test_emoji_family_synced():
    """word→emoji is C family=emoji; pivot path; utf8 shrinks; includes ℹ️."""
    from shared.ledger import (
        apply_ledger_lex,
        convention_ids,
        list_conventions,
        validate_ledger_metrics,
    )
    from shared.lex_policy import EMOJI_SPEC, INFO_GLYPH, emoji_ledger_rows

    assert validate_ledger_metrics(strict=True) == []
    ids = convention_ids()
    assert "policy-emoji-pivot" in ids
    assert "policy-short-form-priority" in ids
    pols = {c["id"]: c for c in list_conventions(kind="policy")}
    assert pols["policy-emoji-pivot"]["payload"]["path"] == [
        "ml_aliases",
        "pivot",
        "emoji",
    ]
    assert pols["policy-short-form-priority"]["payload"]["order"][0] == "ml_math_symbol_inventory"
    assert pols["policy-short-form-priority"]["payload"]["prefer_math_symbol_when_both"]
    assert not pols["policy-short-form-priority"]["payload"]["prefer_emoji_over_new_math"]
    assert "policy-cross-lang-cheapest" in ids
    assert pols["policy-cross-lang-cheapest"]["payload"]["helper"].endswith(
        "select_cheapest_form"
    )

    by_id = {c["id"]: c for c in list_conventions(kind="lex")}

    assert len(EMOJI_SPEC) >= 15
    for row in emoji_ledger_rows():
        cid = row["id"]
        assert cid in by_id, cid
        c = by_id[cid]
        assert c["apply_layer"] == "C"
        assert c["family"] == "emoji"
        assert c.get("ledger_apply") is not False
        assert c["to"] == row["to"]
        assert c.get("pivot") == row["pivot"], cid
        assert c.get("pivot_lang") in ("en", "ja"), cid
        assert c["pivot"] in c["from"], cid
        assert c["metrics"]["bit"]["utf8"]["delta"] < 0, cid

    assert by_id["emoji-fire"]["to"] == "🔥"
    assert by_id["emoji-fire"]["pivot"] == "fire"
    assert by_id["emoji-fire"]["pivot_lang"] == "en"
    assert by_id["emoji-fire"]["from"][0] == "ファイア"
    assert by_id["emoji-heart"]["to"] == "♡"
    assert by_id["emoji-heart"]["pivot"] == "heart"
    assert "heart" in by_id["emoji-heart"]["from"]

    assert apply_ledger_lex("ファイア") == "🔥"
    assert apply_ledger_lex("Feuer") == "🔥"  # ML → pivot fire → 🔥
    assert "♡" in apply_ledger_lex("heart")
    assert "♡" in apply_ledger_lex("ハート")
    assert "🔥" in apply_ledger_lex("on fire")
    assert "👍" in apply_ledger_lex("thumbs up")
    assert "⚠" in apply_ledger_lex("warning")
    assert "✓" in apply_ledger_lex("check mark")
    assert "✅" not in apply_ledger_lex("check mark")
    assert "✕" in apply_ledger_lex("cross mark")

    # information→ℹ️ is C family=emoji (sole apply; not ETYMON)
    assert "emoji-information" in by_id
    assert by_id["emoji-information"]["to"] == INFO_GLYPH
    assert by_id["emoji-information"]["pivot"] == "information"
    assert by_id["emoji-information"]["from"][0] == "information"
    assert INFO_GLYPH in apply_ledger_lex("information")
    assert INFO_GLYPH in apply_ledger_lex("インフォメーション")
    assert INFO_GLYPH in apply_ledger_lex("información")

    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    assert "♡" in s.compress("heart")
    assert "🔥" in s.compress("ファイア")
    assert "🔥" in s.compress("fire")
    assert INFO_GLYPH in s.compress("send the information please")
    # FYI phrase must win over bare information→ℹ️
    assert "FYI" in s.compress("for your information please")
    assert INFO_GLYPH not in s.compress("for your information please")


def test_select_cheapest_form_and_symbol_family():
    """Cross-lang cheapest helper + family=symbol math rows; check uses ✓."""
    from shared.ledger import (
        apply_ledger_lex,
        convention_ids,
        list_conventions,
        select_cheapest_form,
        validate_ledger_metrics,
    )
    from shared.lex_policy import SYMBOL_SPEC

    assert validate_ledger_metrics(strict=True) == []
    ids = convention_ids()
    assert "policy-cross-lang-cheapest" in ids
    assert "symbol-neq" in ids
    assert "symbol-infinity" in ids

    by_id = {c["id"]: c for c in list_conventions(kind="lex")}
    assert by_id["emoji-check"]["to"] == "✓"
    assert by_id["emoji-cross"]["to"] == "✕"
    assert by_id["emoji-star"]["to"] == "★"

    for sid, _forms, dst, _r in SYMBOL_SPEC:
        cid = f"symbol-{sid}"
        assert cid in by_id, cid
        c = by_id[cid]
        assert c["family"] == "symbol"
        assert c["apply_layer"] == "C"
        assert c["to"] == dst
        assert c["metrics"]["bit"]["utf8"]["delta"] < 0, cid

    assert "≠" in apply_ledger_lex("not equal")
    assert "∞" in apply_ledger_lex("infinity")
    assert "±" in apply_ledger_lex("plus or minus")
    assert "%" in apply_ledger_lex("パーセント")
    assert "⇒" in apply_ledger_lex("implies that")

    # cheapest among meaning-preserving candidates (机 beats tables on token+utf8)
    pick = select_cheapest_form(["tables", "机", "桌"], reference="tables")
    assert pick["chosen"] == "机"
    assert pick["ranked"][0]["utf8_shrinks"] is True

    # ✓ beats longer emoji peer on clarity policy; same or better cost
    pick2 = select_cheapest_form(["✅", "✓"], reference="check mark")
    assert pick2["chosen"] in ("✓", "✅")  # same token/utf8; ✓ first-seen or tie-break
    # force order: put ✓ first → chosen ✓; put ✅ first may still pick either equal
    pick3 = select_cheapest_form(["✓", "✅"], reference="check mark")
    assert pick3["chosen"] == "✓"


def test_ever_family_no_matter_to_ever():
    """5W1H concessive multiword → -ever; however gate; dual metrics shrink."""
    from shared.ledger import (
        apply_ledger_lex,
        convention_ids,
        list_conventions,
        validate_ledger_metrics,
    )

    assert validate_ledger_metrics(strict=True) == []
    ids = convention_ids()
    for cid in (
        "ever-however",
        "ever-whatever",
        "ever-whichever",
        "ever-wherever",
        "ever-whenever",
        "ever-whoever",
        "policy-ever-concessive",
    ):
        assert cid in ids, cid
    assert "ever-whyever" not in ids

    by_id = {c["id"]: c for c in list_conventions(kind="lex", apply_layer="C")}
    for cid, dst, sample in (
        ("ever-however", "however", "no matter how"),
        ("ever-whatever", "whatever", "no matter what"),
        ("ever-whichever", "whichever", "no matter which"),
        ("ever-wherever", "wherever", "no matter where"),
        ("ever-whenever", "whenever", "no matter when"),
        ("ever-whoever", "whoever", "no matter who"),
    ):
        c = by_id[cid]
        assert c["family"] == "ever"
        assert c["to"] == dst
        assert sample in [str(x).lower() for x in c["from"]]
        m = c["metrics"]
        assert m["token"]["delta"] < 0, cid
        assert m["bit"]["utf8"]["delta"] < 0, cid
        assert m["token"]["sample_from"] == sample

    how = by_id["ever-however"]
    assert how.get("ambiguity_sensitive") is True
    assert "regardless of how" in [str(x).lower() for x in how["from"]]
    note = (how.get("note") or "") + (how.get("rationale") or "")
    assert "contrast" in note.lower() or "逆接" in note or "しかし" in note

    # phrase compress drops tokens (estimate via shorter surface)
    assert apply_ledger_lex("no matter how hard") == "however hard"
    assert apply_ledger_lex("No matter what you say") == "whatever you say"
    assert apply_ledger_lex("regardless of how difficult") == "however difficult"
    assert apply_ledger_lex("no matter which option") == "whichever option"
    assert apply_ledger_lex("no matter where you are") == "wherever you are"
    assert apply_ledger_lex("no matter when you arrive") == "whenever you arrive"
    assert apply_ledger_lex("no matter who comes") == "whoever comes"

    # meaning gate: prefer_precision / collision keep multiword; bare However untouched
    assert "no matter how" in apply_ledger_lex(
        "no matter how hard", prefer_precision=True
    ).lower()
    collide = apply_ledger_lex("no matter how, however we try")
    assert "no matter how" in collide.lower()
    bare = apply_ledger_lex("However, we disagree.")
    assert bare.startswith("However")

    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("No matter how hard it is, I will go.")
    assert "however" in out.lower()
    assert "no matter how" not in out.lower()
    assert "I'll" in out or "i'll" in out.lower()


def test_ever_family_staged_before_final_zh_de_keeps_asap():
    """C then B-final-zh-de: -ever applies; ASAP stays preferred over 尽快."""
    from tests._helpers import ns

    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    d = _load("density_zip", "DensityZip/density_zip.py")

    src = (
        "No matter how hard it is, I will go to the train station "
        "as soon as possible."
    )
    before = t.estimate_tokens(src)
    c_out = s.compress(src)
    assert "however" in c_out.lower()
    assert "no matter how" not in c_out.lower()
    assert "ASAP" in c_out
    assert "尽快" not in c_out
    mid = t.estimate_tokens(c_out)
    assert mid < before

    final = t.final_zh_de_token_pass(c_out)
    after = t.estimate_tokens(final)
    assert after <= mid
    assert "however" in final.lower()
    assert "ASAP" in final  # not rewritten to 尽快 after C
    assert "尽快" not in final
    assert "Bahnhof" in final or "iré" in final

    trace: list = []
    args = ns(final_zh_de=True, no_final_zh_de=False, translate_engine="fixture")
    pipe = d.run_pipeline(["C", "B-final-zh-de"], src, args, trace=trace)
    assert "however" in pipe.lower()
    assert "ASAP" in pipe
    assert "尽快" not in pipe
    assert trace[-1]["layer"] == "B-final-zh-de"


def test_however_hard_not_tho_after_ce():
    """Concessive/degree however (from no matter how or bare) must not become tho via E."""
    c = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    e = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    # C: no matter how → however
    after_c = c.compress("No matter how hard it is, I will go.")
    assert "however hard" in after_c.lower()
    assert "tho hard" not in after_c.lower()
    after_e = e.compress(after_c)
    assert "however hard" in after_e.lower()
    assert "tho hard" not in after_e.lower()
    # Bare degree
    bare = e.compress("however hard it looks")
    assert "however hard" in bare.lower()
    assert "tho hard" not in bare.lower()
    # Contrastive however still → tho
    contrast = e.compress("I tried; however, I failed.")
    assert "tho" in contrast.lower()


def test_lex_breakdown_flat_pos_or_tag():
    """lex rows carry compact breakdown: short POS (代/示/…) or short tag (連/頭/…)."""
    from shared.ledger import (
        BREAKDOWN_ALLOWED,
        BREAKDOWN_POS,
        infer_breakdown,
        list_conventions,
        validate_ledger_metrics,
    )

    assert validate_ledger_metrics(strict=True) == []
    lex = list_conventions(kind="lex")
    assert lex
    for c in lex:
        bd = c.get("breakdown")
        assert isinstance(bd, str) and bd in BREAKDOWN_ALLOWED, c.get("id")
    by_id = {c["id"]: c for c in lex}
    assert by_id["pronoun-mine"]["breakdown"] == "代"
    assert by_id["deixis-this"]["breakdown"] == "示"
    assert by_id["c-asap"]["breakdown"] in ("頭", "連", "略")
    assert by_id["ever-however"]["breakdown"] == "連"
    # infer prefers inventory POS
    assert infer_breakdown({"kind": "lex", "inventory": "pronoun", "from": ["I"], "to": "I"}) == "代"
    assert infer_breakdown({"kind": "lex", "family": "ever", "from": ["no matter how"], "to": "however"}) == "連"
    assert "代" in BREAKDOWN_POS
    from shared.ledger import compact_breakdown
    assert compact_breakdown("collocation") == "連"
    assert compact_breakdown("acronym") == "頭"
    assert compact_breakdown("pronoun") == "代"

