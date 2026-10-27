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
    # zero-bit-delta rows pruned; ~100 base + abbrev/emoji/symbol + finite prep/legal
    assert 14 <= len(all_lex) <= 600
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
    # finite prep compounds + legal shorts (this tranche)
    assert by_id["prep-throughout"]["to"] == "通"
    assert by_id["prep-toward"]["to"] == "→"
    assert by_id["legal-hereinafter"]["to"] == "∴↓"
    assert by_id["legal-therewith"]["to"] == "∴w/"
    assert by_id["legal-whereby"]["to"] == "∴by"
    assert by_id["c-regarding"]["to"] == "re:"
    assert by_id["c-as-follows"]["to"] == "↓"
    assert by_id["c-inter-alia"]["to"] == "i.a."
    # prep / prep-like adv finite set
    assert by_id["prep-across"]["to"] == "↔"
    assert by_id["prep-among"]["to"] == "中"
    assert by_id["prep-between"]["to"] == "間"
    assert by_id["prep-through"]["to"] == "通"
    assert by_id["prep-until"]["to"] == "〜"
    assert by_id["adv-meanwhile"]["to"] == "∥"
    assert by_id["adv-together"]["to"] == "共"
    assert by_id["adv-nearby"]["to"] == "近"
    # prep / prep-like adv follow-up tranche
    assert by_id["prep-according-to"]["to"] == "依"
    assert by_id["prep-owing-due"]["to"] == "因"
    assert "due to" in by_id["prep-owing-due"]["from"]
    assert by_id["prep-in-spite-of"]["to"] == "雖"
    assert by_id["prep-far-from"]["to"] == "遠"
    assert by_id["prep-out-of"]["to"] == "外"
    assert by_id["prep-opposite"]["to"] == "対側"
    assert by_id["prep-circa"]["to"] == "c."
    assert by_id["prep-into"]["to"] == "入"
    assert by_id["adv-beforehand"]["to"] == "先"
    assert by_id["adv-forever"]["to"] == "∞"
    assert by_id["adv-overnight"]["to"] == "泊"
    assert by_id["adv-somewhere"]["to"] == "某处"
    assert by_id["adv-elsewhere"]["to"] == "别处"
    assert by_id["adv-anew"]["to"] == "再"
    # cycle2
    assert by_id["prep-in-favor-of"]["to"] == "pro"
    assert by_id["prep-on-behalf-of"]["to"] == "代表"
    assert by_id["prep-by-means-of"]["to"] == "手段"
    assert by_id["prep-in-accordance-with"]["to"] == "準"
    assert "pursuant to" in by_id["prep-in-accordance-with"]["from"]
    assert by_id["prep-up-to"]["to"] == "≦"
    assert by_id["prep-in-light-of"]["to"] == "鑑"
    assert by_id["prep-for-sake-of"]["to"] == "為"
    assert by_id["prep-regardless"]["to"] == "不問"
    assert by_id["prep-past"]["to"] == "過"
    assert by_id["prep-following"]["to"] == "次"
    assert by_id["adv-pending"]["to"] == "未決"
    # cycle3
    assert by_id["prep-by-virtue-of"]["to"] == "力"
    assert by_id["prep-by-way-of"]["to"] == "経"
    assert by_id["prep-on-account-of"]["to"] == "因"
    assert "by reason of" in by_id["prep-on-account-of"]["from"]
    assert by_id["prep-in-exchange-for"]["to"] == "⇔"
    assert by_id["prep-on-top-of"]["to"] == "且"
    assert by_id["prep-at-expense-of"]["to"] == "犠牲"
    assert by_id["prep-in-middle-of"]["to"] == "最中"
    assert by_id["prep-as-result-of"]["to"] == "∴"
    assert by_id["prep-courtesy-of"]["to"] == "経"
    # cycle4
    assert by_id["prep-for-purpose-of"]["to"] == "目的"
    assert by_id["prep-for-benefit-of"]["to"] == "益"
    assert by_id["prep-in-interest-of"]["to"] == "利"
    assert by_id["prep-to-detriment-of"]["to"] == "害"
    assert by_id["prep-in-support-of"]["to"] == "援"
    assert by_id["prep-in-charge-of"]["to"] == "責"
    assert by_id["prep-in-control-of"]["to"] == "制"
    assert by_id["prep-in-search-of"]["to"] == "求"
    assert by_id["prep-in-need-of"]["to"] == "要"
    assert by_id["prep-in-hope-of"]["to"] == "希"
    assert by_id["prep-in-wake-of"]["to"] == "跡"
    assert by_id["prep-in-name-of"]["to"] == "名"
    assert by_id["prep-at-hands-of"]["to"] == "手"
    assert by_id["prep-at-mercy-of"]["to"] == "弄"
    assert by_id["prep-ahead-of"]["to"] == "先"
    assert "in advance of" in by_id["prep-ahead-of"]["from"]
    assert by_id["prep-in-association-with"]["to"] == "連携"
    assert by_id["prep-in-comparison"]["to"] == "比"
    assert by_id["prep-in-common-with"]["to"] == "共通"
    assert by_id["prep-subject-to"]["to"] == "条件"
    assert by_id["prep-adjacent-to"]["to"] == "隣"
    assert by_id["prep-in-defiance-of"]["to"] == "反"
    assert by_id["prep-by-order-of"]["to"] == "命"
    assert by_id["prep-under-cover-of"]["to"] == "覆"
    assert by_id["prep-at-odds-with"]["to"] == "対立"
    assert by_id["prep-with-a-view-to"]["to"] == "狙"
    assert by_id["prep-on-basis-of"]["to"] == "基"
    assert by_id["prep-in-presence-of"]["to"] == "在"
    assert by_id["prep-at-price-of"]["to"] == "代価"
    assert by_id["prep-under-auspices"]["to"] == "傘"
    assert by_id["prep-in-parallel-with"]["to"] == "∥"
    # cycle5
    assert by_id["prep-in-response-to"]["to"] == "応"
    assert by_id["prep-in-answer-to"]["to"] == "答"
    assert by_id["prep-in-line-with"]["to"] == "沿"
    assert by_id["prep-in-agreement-with"]["to"] == "合"
    assert by_id["prep-depending-on"]["to"] == "依"
    assert by_id["conj-as-well-as"]["to"] == "+"
    assert by_id["conj-let-alone"]["to"] == "況"
    assert by_id["prep-faced-with"]["to"] == "直面"
    assert by_id["prep-pertaining-to"]["to"] == "関"
    assert by_id["prep-independent-of"]["to"] == "独立"
    assert by_id["prep-akin-to"]["to"] == "≒"
    assert by_id["prep-equivalent-to"]["to"] == "≡"
    assert by_id["prep-limited-to"]["to"] == "限"
    assert by_id["prep-attributable-to"]["to"] == "帰"
    assert by_id["adv-for-time-being"]["to"] == "暫"
    assert by_id["adv-at-once"]["to"] == "即"
    assert by_id["adv-all-of-a-sudden"]["to"] == "突"
    assert by_id["adv-from-time-to-time"]["to"] == "偶"
    assert by_id["adv-at-last"]["to"] == "遂"
    assert by_id["adv-at-first"]["to"] == "初"
    assert by_id["adv-in-short"]["to"] == "略"
    assert by_id["adv-in-fact"]["to"] == "実"
    assert by_id["adv-in-practice"]["to"] == "実際"
    assert by_id["adv-in-theory"]["to"] == "理"
    assert by_id["adv-in-general"]["to"] == "一般"
    assert by_id["adv-on-purpose"]["to"] == "故意"
    assert by_id["adv-in-vain"]["to"] == "徒"
    assert by_id["adv-at-present"]["to"] == "今"
    assert by_id["adv-ahead-of-time"]["to"] == "早"
    assert by_id["adv-under-way"]["to"] == "進行"
    # cycle6
    assert by_id["prep-contrary-to"]["to"] == "逆"
    assert by_id["prep-proportional-to"]["to"] == "比例"
    assert by_id["prep-in-pursuit-of"]["to"] == "追"
    assert by_id["adv-after-all"]["to"] == "結局"
    assert by_id["adv-above-all"]["to"] == "最"
    assert by_id["adv-all-in-all"]["to"] == "総"
    assert by_id["adv-all-the-same"]["to"] == "猶"
    assert by_id["adv-by-and-large"]["to"] == "概"
    assert by_id["adv-by-far"]["to"] == "遥"
    assert by_id["adv-for-sure"]["to"] == "確"
    assert by_id["adv-in-any-case"]["to"] == "何れ"
    assert by_id["adv-in-the-end"]["to"] == "最終"
    assert by_id["adv-in-long-run"]["to"] == "長期"
    assert by_id["adv-on-the-contrary"]["to"] == "反対"
    assert by_id["adv-on-other-hand"]["to"] == "他方"
    assert by_id["adv-to-some-extent"]["to"] == "或程"
    assert by_id["adv-as-usual"]["to"] == "常"
    assert by_id["adv-more-or-less"]["to"] == "殆"
    assert by_id["adv-little-by-little"]["to"] == "徐"
    assert by_id["adv-step-by-step"]["to"] == "逐"
    assert by_id["adv-one-by-one"]["to"] == "逐一"
    assert by_id["adv-side-by-side"]["to"] == "並列"
    assert by_id["adv-again-and-again"]["to"] == "繰"
    assert by_id["adv-as-a-result"]["to"] == "結果"
    assert by_id["adv-in-advance"]["to"] == "予"
    assert by_id["adv-by-all-means"]["to"] == "是非"
    assert by_id["adv-in-essence"]["to"] == "本質"
    assert by_id["adv-in-detail"]["to"] == "詳"
    assert by_id["adv-in-retrospect"]["to"] == "回顧"
    assert by_id["adv-without-fail"]["to"] == "必ず"
    # cycle7
    assert by_id["prep-north-of"]["to"] == "北"
    assert by_id["prep-south-of"]["to"] == "南"
    assert by_id["prep-east-of"]["to"] == "東"
    assert by_id["prep-west-of"]["to"] == "西"
    assert by_id["prep-to-the-left-of"]["to"] == "左"
    assert by_id["prep-to-the-right-of"]["to"] == "右"
    assert by_id["prep-on-the-part-of"]["to"] == "側"
    assert by_id["prep-in-disregard-of"]["to"] == "無視"
    assert by_id["prep-out-of-control"]["to"] == "暴走"
    assert by_id["prep-out-of-date"]["to"] == "廃"
    assert by_id["prep-out-of-order"]["to"] == "故障"
    assert by_id["prep-under-pressure"]["to"] == "圧"
    assert by_id["prep-under-control"]["to"] == "制御"
    assert by_id["prep-liable-to"]["to"] == "負"
    assert by_id["prep-resistant-to"]["to"] == "耐"
    assert by_id["prep-sensitive-to"]["to"] == "敏"
    assert by_id["prep-inferior-to"]["to"] == "劣"
    assert by_id["prep-superior-to"]["to"] == "優"
    assert by_id["adv-no-longer"]["to"] == "最早"
    assert by_id["adv-as-yet"]["to"] == "未"
    assert by_id["adv-on-one-hand"]["to"] == "一方"
    assert by_id["adv-in-short-run"]["to"] == "短期"
    assert by_id["adv-to-large-extent"]["to"] == "大程"
    assert by_id["adv-shortly-after"]["to"] == "直後"
    assert by_id["adv-shortly-before"]["to"] == "直前"
    assert by_id["adv-day-by-day"]["to"] == "日々"
    assert by_id["adv-year-by-year"]["to"] == "年々"
    assert by_id["adv-face-to-face"]["to"] == "対面"
    # cycle8
    assert by_id["prep-upstream-of"]["to"] == "上流"
    assert by_id["prep-downstream-of"]["to"] == "下流"
    assert by_id["prep-out-of-place"]["to"] == "不所"
    assert by_id["prep-out-of-reach"]["to"] == "届外"
    assert by_id["prep-under-fire"]["to"] == "被弾"
    assert by_id["prep-under-review"]["to"] == "審査中"
    assert by_id["prep-immune-to"]["to"] == "免疫"
    assert by_id["prep-prone-to"]["to"] == "傾向"
    assert by_id["prep-preparatory-to"]["to"] == "準備"
    assert by_id["prep-further-to"]["to"] == "追伸"
    assert by_id["prep-in-praise-of"]["to"] == "賛"
    assert by_id["prep-such-as"]["to"] == "如"
    assert by_id["adv-for-real"]["to"] == "真"
    assert by_id["adv-in-turn"]["to"] == "順"
    assert by_id["adv-in-full"]["to"] == "全"
    assert by_id["adv-in-succession"]["to"] == "連続"
    assert by_id["adv-hand-in-hand"]["to"] == "携"
    assert by_id["adv-head-to-head"]["to"] == "直接"
    assert by_id["adv-long-since"]["to"] == "久"
    assert by_id["adv-right-then"]["to"] == "其時"
    assert by_id["adv-en-route"]["to"] == "途中"
    assert by_id["adv-by-no-means"]["to"] == "決して"
    assert by_id["adv-no-doubt"]["to"] == "疑無"
    assert by_id["adv-in-some-way"]["to"] == "或様"
    assert by_id["adv-in-many-ways"]["to"] == "多様"
    assert by_id["adv-at-times"]["to"] == "時々"
    assert by_id["adv-at-all-times"]["to"] == "常時"
    assert by_id["adv-at-random"]["to"] == "乱"
    assert "out of nowhere" in by_id["adv-all-of-a-sudden"]["from"]
    assert "excluding" in by_id["prep-except"]["from"]
    assert by_id["prep-upstream-of"]["breakdown"] == "前"
    assert by_id["adv-at-random"]["breakdown"] == "副"
    assert "exclusive of" in by_id["prep-except"]["from"]
    # cycle9
    assert by_id["prep-abreast-of"]["to"] == "並"
    assert by_id["prep-cognizant-of"]["to"] == "知"
    assert by_id["prep-mindful-of"]["to"] == "念"
    assert by_id["prep-fond-of"]["to"] == "好"
    assert by_id["prep-proud-of"]["to"] == "誇"
    assert by_id["prep-capable-of"]["to"] == "能"
    assert by_id["prep-incapable-of"]["to"] == "不能"
    assert by_id["prep-worthy-of"]["to"] == "値"
    assert by_id["prep-typical-of"]["to"] == "典型"
    assert by_id["prep-indicative-of"]["to"] == "示"
    assert by_id["prep-suggestive-of"]["to"] == "示唆"
    assert by_id["prep-characteristic-of"]["to"] == "特質"
    assert by_id["prep-rid-of"]["to"] == "撤"
    assert by_id["prep-full-of"]["to"] == "満"
    assert by_id["prep-composed-of"]["to"] == "構成"
    assert "consisting of" in by_id["prep-composed-of"]["from"]
    assert by_id["prep-for-the-duration-of"]["to"] == "期間"
    assert by_id["adv-offshore"]["to"] == "沖"
    assert by_id["adv-simultaneously"]["to"] == "同時"
    assert by_id["adv-respectively"]["to"] == "各"
    assert by_id["adv-similarly"]["to"] == "同様"
    assert by_id["adv-in-particular"]["to"] == "特"
    assert by_id["adv-so-to-speak"]["to"] == "言わば"
    assert by_id["adv-as-such"]["to"] == "斯"
    assert by_id["adv-once-and-for-all"]["to"] == "断"
    assert by_id["adv-currently"]["to"] == "現"
    assert by_id["adv-formerly"]["to"] == "旧"
    assert by_id["adv-alternately"]["to"] == "交互"
    assert by_id["adv-ever-since"]["to"] == "以来"
    assert "bereft of" in by_id["prep-for-lack-of"]["from"]
    assert "afraid of" in by_id["prep-for-fear-of"]["from"]
    assert "conversely" in by_id["prep-contrary-to"]["from"]
    assert "thereupon" in by_id["adv-right-then"]["from"]
    assert by_id["prep-abreast-of"]["breakdown"] == "前"
    assert by_id["adv-currently"]["breakdown"] == "副"
    # cycle10
    assert by_id["prep-weary-of"]["to"] == "厭"
    assert by_id["prep-ashamed-of"]["to"] == "恥"
    assert by_id["prep-jealous-of"]["to"] == "嫉"
    assert by_id["prep-empty-of"]["to"] == "空"
    assert by_id["prep-made-of"]["to"] == "製"
    assert by_id["adv-ashore"]["to"] == "岸"
    assert by_id["adv-overboard"]["to"] == "船外"
    assert by_id["adv-underwater"]["to"] == "水中"
    assert by_id["adv-nationwide"]["to"] == "全国"
    assert by_id["adv-worldwide"]["to"] == "世界"
    assert by_id["adv-clockwise"]["to"] == "時計"
    assert by_id["adv-counterclockwise"]["to"] == "反時計"
    assert by_id["adv-inside-out"]["to"] == "裏返"
    assert by_id["adv-upside-down"]["to"] == "逆さ"
    assert by_id["adv-backwards"]["to"] == "後方"
    assert by_id["adv-sideways"]["to"] == "横"
    assert by_id["adv-en-masse"]["to"] == "一斉"
    assert by_id["adv-all-along"]["to"] == "当初"
    assert by_id["adv-ever-after"]["to"] == "以後"
    assert by_id["adv-for-keeps"]["to"] == "永久"
    assert by_id["adv-off-and-on"]["to"] == "断続"
    assert by_id["adv-through-and-through"]["to"] == "徹底"
    assert by_id["adv-more-often-than-not"]["to"] == "大抵"
    assert by_id["adv-at-a-glance"]["to"] == "一見"
    assert by_id["adv-at-stake"]["to"] == "賭"
    assert by_id["adv-in-earnest"]["to"] == "本気"
    assert by_id["adv-in-effect"]["to"] == "実質"
    assert by_id["adv-out-of-stock"]["to"] == "品切"
    # cycle11 spaced deferred
    assert by_id["prep-as-of"]["to"] == "起"
    assert by_id["adv-for-once"]["to"] == "一度"
    assert by_id["adv-of-late"]["to"] == "近頃"
    assert by_id["adv-hitherto"]["to"] == "従来"
    assert by_id["adv-thus-far"]["to"] == "今迄"
    assert "to date" in by_id["adv-thus-far"]["from"]
    assert by_id["adv-under-age"]["to"] == "年少"
    assert by_id["adv-one-on-one"]["to"] == "1:1"
    assert by_id["adv-by-and-by"]["to"] == "稍後"
    assert by_id["adv-anywhere"]["to"] == "∃loc"
    assert by_id["adv-nowhere"]["to"] == "∅loc"
    assert by_id["adv-anytime"]["to"] == "∀時"
    assert by_id["adv-somewhat"]["to"] == "稍"
    assert by_id["adv-mutatis-mutandis"]["to"] == "準変"
    assert by_id["adv-ceteris-paribus"]["to"] == "他同"
    assert by_id["adv-sui-generis"]["to"] == "独自"
    assert by_id["adv-pari-passu"]["to"] == "同率"
    assert by_id["adv-ex-officio"]["to"] == "職権"
    assert by_id["adv-prima-facie"]["to"] == "一応"
    assert by_id["adv-ipso-facto"]["to"] == "当然"
    assert by_id["adv-a-priori"]["to"] == "先験"
    assert by_id["adv-de-facto"]["to"] == "d.f."
    assert by_id["adv-in-situ"]["to"] == "現場"
    assert by_id["adv-ad-hoc"]["to"] == "adhoc"
    assert "for good" in by_id["adv-forever"]["from"]
    assert "somehow" in by_id["adv-in-some-way"]["from"]
    # relative / 関代
    assert by_id["rel-which"]["to"] == "that"
    assert by_id["rel-whom"]["to"] == "who"
    assert by_id["rel-que"]["to"] == "que"
    assert "which" in by_id["rel-which"]["from"]
    assert "whom" in by_id["rel-whom"]["from"]
    assert "lequel" in by_id["rel-que"]["from"]
    assert by_id["rel-which"]["breakdown"] == "関代"
    assert by_id["rel-whom"]["breakdown"] == "関代"
    assert by_id["rel-que"]["breakdown"] == "関代"

    # objective gap-fill closed thin
    assert by_id["det-every"]["to"] == "∀"
    assert by_id["det-each"]["to"] == "各"
    assert by_id["det-some"]["to"] == "∃"
    assert by_id["det-none"]["to"] == "∅"
    assert by_id["det-both"]["to"] == "両"
    assert by_id["quant-several"]["to"] == "数"
    assert by_id["quant-various"]["to"] == "諸"
    assert by_id["quant-numerous"]["to"] == "多"
    assert "a lot of" in by_id["quant-numerous"]["from"]
    assert by_id["quant-a-few"]["to"] == "few"
    assert by_id["quant-a-little"]["to"] == "少"
    assert by_id["det-every"]["breakdown"] == "限"
    assert by_id["quant-numerous"]["breakdown"] == "限"
    assert by_id["conj-unless"]["to"] == "!if"
    assert by_id["conj-whether"]["to"] == "if"
    assert by_id["conj-while"]["to"] == "∥"
    assert by_id["conj-so-that"]["to"] == "so"
    assert by_id["conj-in-order-to"]["to"] == "to"
    assert by_id["pronoun-each-other"]["to"] == "互"
    assert "one another" in by_id["pronoun-each-other"]["from"]
    assert by_id["adv-maybe"]["to"] == "或"
    assert by_id["adv-probably"]["to"] == "恐"
    assert by_id["adv-already"]["to"] == "既"
    assert by_id["adv-also"]["to"] == "+"
    assert by_id["adv-only"]["to"] == "僅"
    assert by_id["adv-still"]["to"] == "尚"
    assert "roughly" in by_id["adv-approx"]["from"]
    assert "usually" in by_id["adv-as-usual"]["from"]
    assert by_id["adv-a-while"]["to"] == "awhile"
    assert by_id["aux-wanna"]["to"] == "wanna"
    assert by_id["aux-kinda"]["to"] == "kinda"
    assert by_id["aux-sorta"]["to"] == "sorta"
    assert by_id["aux-kinda"]["breakdown"] == "俗"
    assert by_id["prep-as-of"]["breakdown"] == "前"
    assert by_id["adv-mutatis-mutandis"]["breakdown"] == "連"
    assert "vis-a-vis" in by_id["prep-as-opposed-to"]["from"]
    assert "afterward" in by_id["adv-afterwards"]["from"]
    assert "as of yet" in by_id["adv-as-yet"]["from"]
    assert "first and foremost" in by_id["adv-above-all"]["from"]
    assert "in a nutshell" in by_id["adv-in-short"]["from"]
    assert "ad infinitum" in by_id["adv-forever"]["from"]
    assert by_id["prep-weary-of"]["breakdown"] == "前"
    assert by_id["adv-at-stake"]["breakdown"] == "副"
    assert "every now and then" in by_id["adv-from-time-to-time"]["from"]
    assert by_id["prep-north-of"]["breakdown"] == "前"
    assert by_id["adv-no-longer"]["breakdown"] == "副"
    assert "with regard to" in by_id["prep-in-regard-to"]["from"]
    assert "once again" in by_id["adv-anew"]["from"]
    assert "right now" in by_id["adv-at-present"]["from"]
    assert by_id["adv-after-all"]["breakdown"] == "副"
    assert by_id["prep-contrary-to"]["breakdown"] == "前"
    assert "in the meantime" in by_id["adv-meanwhile"]["from"]
    assert "based on" in by_id["prep-on-basis-of"]["from"]
    assert "from now on" in by_id["legal-henceforth"]["from"]
    assert "in compliance with" in by_id["prep-in-accordance-with"]["from"]
    assert by_id["prep-in-response-to"]["breakdown"] == "前"
    assert by_id["adv-for-time-being"]["breakdown"] == "副"
    assert "by dint of" in by_id["prep-by-virtue-of"]["from"]
    assert "on the brink of" in by_id["prep-on-verge-of"]["from"]
    assert "as per" in by_id["prep-in-accordance-with"]["from"]
    assert "free of" in by_id["prep2-without"]["from"]
    assert by_id["prep-for-purpose-of"]["breakdown"] == "前"
    assert by_id["prep-by-virtue-of"]["breakdown"] == "前"
    assert by_id["prep-in-favor-of"]["breakdown"] == "前"
    assert by_id["prep-according-to"]["breakdown"] == "前"
    assert by_id["adv-forever"]["breakdown"] == "副"
    assert "underneath" in by_id["spatial-under"]["from"]
    assert by_id["e-conj-whereas"].get("extended") is True
    # no lex emits fr
    assert all(c.get("to") != "fr" for c in by_id.values())


def test_formal_legal_connectives_dual_metrics():
    """Finite formal/legal + connective gaps. Meaning gate before cheapest.

    Skips ids already registered (hereinafter/thereof/therewith/whereby/…)
    and forms that lose the dual-metric or sense gate (hereof, thereby, hereto).
    """
    from shared.ledger import (
        BREAKDOWN_ALLOWED,
        apply_ledger_lex,
        list_conventions,
        select_cheapest_form,
        validate_ledger_metrics,
    )

    assert validate_ledger_metrics(strict=True) == []
    by_id = {c["id"]: c for c in list_conventions(kind="lex")}
    skipped = {
        "legal-hereinafter",
        "legal-hereinafter-aka",
        "legal-hereafter",
        "legal-herein",
        "legal-thereof",
        "legal-therewith",
        "legal-whereby",
        "prep-throughout",
        "prep-toward",
        "c-regarding",
        "c-as-follows",
        "c-inter-alia",
    }
    for cid in skipped:
        assert cid in by_id

    # hereof / thereby are not revived
    assert all(
        "hereof" not in [str(x).lower() for x in (c.get("from") or [])]
        and c.get("to") != "hereof"
        for c in by_id.values()
    )
    assert "legal-thereby" not in by_id
    assert apply_ledger_lex("agreed thereby") == "agreed thereby"

    expected = {
        "legal-therein": "∈it",
        "legal-thereto": "∴to",
        "legal-henceforth": "∴→",
        "legal-notwithstanding": "雖",
        "conj-insofar": "insofar",
        "c-pursuant": "per",
        "conj-provided": "if",
        "conj-in-lieu": "vs",
        "c-namely": "viz",
        "conj-hence": "∴",
        "conj-albeit": "tho",
        "c-foregoing": "supra",
        "c-aforementioned": "said",
        "symbol-vice-versa": "⇄",
        "c-tnc": "T&C",
        "c-et-al": "etal",
        "conj-given-that": "bc",
        "legal-null-void": "void",
    }
    for cid, dst in expected.items():
        c = by_id[cid]
        assert c["to"] == dst, cid
        assert c["breakdown"] in BREAKDOWN_ALLOWED
        m = c["metrics"]
        assert m["token"]["delta"] < 0, cid
        assert m["bit"]["utf8"]["delta"] < 0, cid
        assert m["token"]["sample_from"] == c["from"][0]

    # meaning gate: prepositional notwithstanding ≠ tho; despite's terminal is 雖
    assert select_cheapest_form(
        ["雖", "despite"], reference="notwithstanding"
    )["chosen"] == "雖"
    assert select_cheapest_form(
        ["supra", "above"], reference="the foregoing"
    )["chosen"] == "supra"
    assert select_cheapest_form(
        ["∈it", "∈there", "in it"], reference="therein"
    )["chosen"] == "∈it"
    assert select_cheapest_form(
        ["∴", "so"], reference="hence"
    )["chosen"] == "∴"
    assert select_cheapest_form(
        ["⇄", "vv"], reference="vice versa"
    )["chosen"] == "⇄"
    assert select_cheapest_form(
        ["viz", "viz.", "i.e."], reference="namely"
    )["chosen"] == "viz"

    assert apply_ledger_lex("notwithstanding section 5") == "雖 section 5"
    assert apply_ledger_lex("insofar as possible") == "insofar possible"
    assert "to the extent of" in apply_ledger_lex("to the extent of 5")
    assert apply_ledger_lex("pursuant to section 2") == "per section 2"
    assert "pursuant to" in apply_ledger_lex(
        "pursuant to section 2", prefer_precision=True
    )
    # per already in text → keep the long form
    kept = apply_ledger_lex("pursuant to the rule per annex")
    assert "pursuant to" in kept
    assert apply_ledger_lex("provided that we pay") == "if we pay"
    assert "provided that" in apply_ledger_lex(
        "provided that we pay", prefer_precision=True
    )
    assert apply_ledger_lex("now therefore the parties") == "∴ the parties"
    assert apply_ledger_lex("hence we stop") == "∴ we stop"
    assert apply_ledger_lex("null and void") == "void"
    assert apply_ledger_lex("terms and conditions") == "T&C"
    assert apply_ledger_lex("smith and others") == "smith etal"
    assert apply_ledger_lex("the foregoing terms") == "supra terms"
    assert apply_ledger_lex("the aforementioned company") == "the said company"
    # verb said blocks the legal determiner
    blocked = apply_ledger_lex("she said the aforementioned company")
    assert "aforementioned" in blocked
    assert apply_ledger_lex("vice versa") == "⇄"
    assert apply_ledger_lex("even though late") == "tho late"
    assert apply_ledger_lex("given that we signed") == "bc we signed"
    assert apply_ledger_lex("instead of cash") == "vs cash"
    # E-owned legal anaphora is not applied by C
    assert "therein" in apply_ledger_lex("parties therein")
    assert "hereof" in apply_ledger_lex("terms hereof")


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
    assert "関代" in BREAKDOWN_POS
    assert infer_breakdown({"kind": "lex", "family": "relative", "from": ["which"], "to": "that"}) == "関代"
    from shared.ledger import compact_breakdown
    assert compact_breakdown("relative") == "関代"
    assert compact_breakdown("関係代名詞") == "関代"
    assert compact_breakdown("collocation") == "連"
    assert compact_breakdown("acronym") == "頭"
    assert compact_breakdown("pronoun") == "代"

