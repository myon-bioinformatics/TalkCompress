"""B final token pass: compounds/ZH densifiers + ES/FR tense after A–E."""

from __future__ import annotations

from tests._helpers import load as _load, ns


def _tessera():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _density():
    return _load("density_zip", "DensityZip/density_zip.py")


def test_asap_acronym_beats_zh_densifier():
    t = _tessera()
    src = "Please reply as soon as possible."
    out = t.apply_zh_de_phrases(src)
    assert "ASAP" in out
    assert "尽快" not in out
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_asap_beats_ja_naru_haya_densifier():
    """ASAP ≺ なる早 (JA densifier spelling; not なるはや)."""
    t = _tessera()
    assert "ja" in t.FINAL_PHRASE_LANGS
    src = "Please reply as soon as possible."
    out = t.apply_zh_de_phrases(src)
    assert "ASAP" in out
    assert "なる早" not in out
    assert "なるはや" not in out


def test_short_de_compound_bahnhof_wins():
    t = _tessera()
    src = "Meet me at the train station tomorrow."
    out = t.apply_zh_de_phrases(src)
    assert "Bahnhof" in out
    assert "train station" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_adj_noun_zh_compound_wins():
    t = _tessera()
    src = "high speed rail and green tea"
    out = t.apply_zh_de_phrases(src)
    # longest-first: high speed rail → 高铁 (not bare high-speed → 高速)
    assert "高铁" in out
    assert "高速" not in out
    assert "绿茶" in out
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_long_de_compound_not_in_bank_when_losing():
    t = _tessera()
    # Geschwindigkeitsbegrenzung loses under estimate_tokens vs "speed limit"
    pairs = {(a.lower(), b) for a, b, _ in t.zh_de_phrase_pairs()}
    assert ("speed limit", "Geschwindigkeitsbegrenzung") not in pairs
    # bank only keeps winners
    for src, dst, lang in t.zh_de_phrase_pairs():
        assert lang in t.FINAL_PHRASE_LANGS
        assert t.estimate_tokens(dst) < t.estimate_tokens(src)


def test_es_fr_tense_future_go_wins():
    """before: I will go tomorrow. → after: cheapest live form (vou ≺ iré)."""
    t = _tessera()
    src = "I will go tomorrow."
    out = t.apply_es_fr_tense(src)
    assert any(s in out for s in ("vou", "iré", "irei", "πάω"))
    assert "will go" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_es_fr_tense_progressive_to_present():
    """before: I'm going now. → after: voy/vou (not 'voy to')."""
    t = _tessera()
    src = "I'm going now."
    out = t.apply_es_fr_tense(src)
    assert any(s in out for s in ("voy", "vou", "πάω"))
    assert "going" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_es_fr_tense_bank_all_drop_tokens():
    t = _tessera()
    for src, dst, lang in t.es_fr_tense_pairs():
        assert lang in t.FINAL_TENSE_LANGS
        assert t.estimate_tokens(dst) < t.estimate_tokens(src)


def test_final_pass_zh_sentence_from_bank():
    t = _tessera()
    src = "Good morning."
    out = t.final_zh_de_token_pass(src)
    assert out == "早。" or "早" in out
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_final_pass_combined_zh_and_de():
    t = _tessera()
    src = "Meet me at the train station as soon as possible."
    before = t.estimate_tokens(src)
    out = t.final_token_pass(src)
    after = t.estimate_tokens(out)
    assert "Bahnhof" in out
    assert "ASAP" in out
    assert "尽快" not in out
    assert after < before


def test_final_pass_includes_tense_and_compounds():
    """before: I will go … train station … ASAP → after: vou/iré + Bahnhof + ASAP."""
    t = _tessera()
    src = "I will go to the train station as soon as possible."
    before = t.estimate_tokens(src)
    out = t.final_token_pass(src)
    after = t.estimate_tokens(out)
    assert any(s in out for s in ("vou", "iré", "irei", "πάω"))
    assert "Bahnhof" in out
    assert "ASAP" in out
    assert "尽快" not in out
    assert after < before


def test_i_was_not_mapped_to_fui():
    t = _tessera()
    out = t.apply_es_fr_tense("I was tired.")
    assert "fui" not in out
    assert "I was" in out


def test_i_went_maps_to_fui():
    t = _tessera()
    out = t.apply_es_fr_tense("I went home.")
    assert "fui" in out
    assert t.estimate_tokens(out) < t.estimate_tokens("I went home.")


def test_pipeline_parse_final_token_alias():
    d = _density()
    assert d.parse_pipeline("C,E,final-token") == ["C", "E", "B-final-zh-de"]
    assert d.FINAL_TOKEN_STEP == d.FINAL_ZH_DE_STEP


def test_pipeline_ends_with_final_zh_de_on_auto():
    d = _density()
    from argparse import Namespace

    layers = d.choose_auto_layers(
        "um thank you for your information please",
        Namespace(auto_machine=False, no_final_zh_de=False),
    )
    assert layers[-1] == d.FINAL_ZH_DE_STEP


def test_pipeline_parse_final_step():
    d = _density()
    assert d.parse_pipeline("C,E,final-zh-de") == ["C", "E", "B-final-zh-de"]
    assert d.parse_pipeline("C,E,zhde") == ["C", "E", "B-final-zh-de"]


def test_with_final_zh_de_flag():
    d = _density()
    from argparse import Namespace

    base = ["C", "E"]
    on = d.with_final_zh_de(base, Namespace(final_zh_de=True, no_final_zh_de=False, auto=False))
    assert on == ["C", "E", "B-final-zh-de"]
    off = d.with_final_zh_de(
        ["C", "E", "B-final-zh-de"],
        Namespace(final_zh_de=True, no_final_zh_de=True, auto=False),
    )
    assert off == ["C", "E"]


def test_run_pipeline_order_ends_with_final(capsys):
    d = _density()

    text = "Meet me at the train station."
    args = ns(final_zh_de=True, no_final_zh_de=False, translate_engine="fixture")
    trace: list = []
    out = d.run_pipeline(["C", "E", "B-final-zh-de"], text, args, trace=trace)
    assert trace[-1]["layer"] == "B-final-zh-de"
    assert "Bahnhof" in out
    # token drop vs raw
    t = _tessera()
    assert t.estimate_tokens(out) < t.estimate_tokens(text)

def test_going_to_future_not_eaten_by_progressive_voy():
    """before→after:
    I'm going now. → voy/vou
    I'm going to leave now. → saldré (not 'voy to leave')
    """
    t = _tessera()
    prog = t.apply_es_fr_tense("I'm going now.")
    assert any(s in prog for s in ("voy", "vou", "πάω"))
    assert t.estimate_tokens(prog) < t.estimate_tokens("I'm going now.")
    raw = "I'm going to leave now."
    out = t.apply_es_fr_tense(raw)
    assert "voy to" not in out.lower()
    assert "vou to" not in out.lower()
    assert "saldré" in out or "vou sair" in out
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_going_to_go_maps_to_short_future():
    t = _tessera()
    raw = "I am going to go tomorrow."
    out = t.apply_es_fr_tense(raw)
    assert "voy to" not in out.lower()
    # cheapest among iré/vou/irei/πάω
    assert any(s in out for s in ("iré", "vou", "irei", "πάω"))
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_they_will_go_prefers_cheapest_pt_or_es():
    t = _tessera()
    raw = "they will go"
    out = t.apply_es_fr_tense(raw)
    # vão beats irán on utf8 under same token count
    assert out == "vão"
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_i_would_go_cheapest_pt_iria():
    t = _tessera()
    raw = "I would go"
    out = t.apply_es_fr_tense(raw)
    assert out == "iria"  # pt iria ≺ es iría on utf8
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_i_will_see_maps_to_vere():
    t = _tessera()
    raw = "I will see you."
    out = t.apply_es_fr_tense(raw)
    assert "veré" in out
    assert "will see" not in out.lower()


def test_final_tense_langs_include_pt_nl_el():
    t = _tessera()
    assert t.FINAL_TENSE_LANGS >= {"es", "fr", "pt", "nl", "el"}


def test_tense_before_after_examples():
    """Single-filter before→after expectations (tense densifier only)."""
    t = _tessera()
    cases = [
        ("I will go", ("vou", "iré", "irei", "πάω")),
        ("I went", ("fui", "vim")),
        ("they will go", ("vão",)),
        ("I would go", ("iria",)),
        ("I will see", ("veré",)),
        ("I saw", ("vi",)),
        ("I will say", ("diré",)),
        ("I said", ("dije",)),
        ("I could", ("pude",)),
        ("I would like", ("gostaria", "quisiera")),
        ("he is going", ("va", "vai")),
        ("I am going to go", ("vou", "iré", "irei", "πάω")),
        ("I'm going to leave", ("saldré", "vou sair")),
        ("I came", ("vim", "vine")),
        ("I did", ("fiz", "hice")),
        ("I had", ("tive", "tuve")),
        ("I know", ("sé",)),
        ("I left", ("salí",)),
        ("we are going", ("vamos",)),
        ("I will leave", ("saldré",)),
    ]
    for src, allowed in cases:
        out = t.apply_es_fr_tense(src)
        assert any(a in out for a in allowed), (src, out, allowed)
        assert t.estimate_tokens(out) < t.estimate_tokens(src), (src, out)
        # going-to must not leave a dangling "voy to"/"vou to"
        if "going to" in src.lower():
            assert "voy to" not in out.lower()
            assert "vou to" not in out.lower()


def test_de_nl_compound_one_word_wins():
    """DE/nl multiword → one-word compound when dual metrics win."""
    t = _tessera()
    cases = [
        # mobile phone → cel|κιν via sibling (beats Handy); covered in test_cell_phone / handy test
        ("Watch the traffic light carefully.", "Ampel"),
        ("Avoid the traffic jam ahead.", "Stau"),
        ("The swimming pool opens at nine.", "zwembad"),
        ("I need a washing machine today.", "wasmachine"),
        ("Need a vacuum cleaner soon.", "stofzuiger"),
    ]
    for src, want in cases:
        out = t.apply_zh_de_phrases(src)
        assert want in out, (src, out)
        assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_zh_compound_densifier_wins():
    t = _tessera()
    cases = [
        ("Ride the high speed rail tomorrow.", "高铁"),
        ("We prefer open source tooling.", "开源"),
        ("Meet at the police station.", "警局"),
        ("Check your blood pressure daily.", "血压"),
        ("Join the large language model talk.", "大模型"),
    ]
    for src, want in cases:
        out = t.apply_zh_de_phrases(src)
        assert want in out, (src, out)
        assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_hsr_longest_beats_bare_high_speed():
    """Longest-first: 'high speed rail' → 高铁, not '高速 rail'."""
    t = _tessera()
    out = t.apply_zh_de_phrases("Ride the high speed rail.")
    assert "高铁" in out
    assert "高速" not in out
    assert "rail" not in out.lower()


def test_handy_beats_zh_phone_densifier():
    """Among ZH/DE bank alone Handy beats 手机; with sibling, pt/el cel|κιν is cheapest."""
    t = _tessera()
    # zh/de bank isolation: Handy still beats 手机
    pairs = [(s, r, lang) for s, r, lang in t.zh_de_phrase_pairs() if s.lower() in {"mobile phone", "cell phone"}]
    forms = {r for _, r, _ in pairs}
    assert "Handy" in forms and "手机" in forms
    chosen = t._cheapest_repl("mobile phone", [(r, lang) for _, r, lang in pairs])
    assert chosen == "Handy"
    # full apply (zh/de + sibling): living pt/el short wins on token+bit
    out = t.apply_zh_de_phrases("Please bring your mobile phone.")
    assert any(s in out for s in ("cel", "κιν"))
    assert "手机" not in out
    assert "mobile phone" not in out.lower()


def test_nl_in_final_phrase_langs():
    t = _tessera()
    assert "nl" in t.FINAL_PHRASE_LANGS


def test_phrase_bank_pairs_dual_metric_wins():
    """Every active pair must shrink token AND utf8_bits."""
    t = _tessera()
    morpho = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    for src, dst, lang in t.zh_de_phrase_pairs():
        assert lang in t.FINAL_PHRASE_LANGS
        assert t.estimate_tokens(dst) < t.estimate_tokens(src)
        assert morpho.utf8_bits(dst) < morpho.utf8_bits(src)


def test_mid_compound_split_soft_no_false_fire():
    """Truncated compound phrases must not rewrite (word-boundary soft)."""
    t = _tessera()
    truncated = [
        "Meet me at the train stati",
        "Please bring your mobile pho",
        "Watch the traffic ligh",
        "Avoid the traffic ja",
        "The swimming poo is closed",
        "Need a vacuum clean",
        "Meet at the police stati",
        "We prefer open sourc tools",
    ]
    for src in truncated:
        out = t.apply_zh_de_phrases(src)
        # must not inject known compound surfaces from a partial phrase
        for needle in ("Bahnhof", "Handy", "Ampel", "Stau", "zwembad", "stofzuiger", "警局", "开源"):
            assert needle not in out, (src, out, needle)
        # soft: no crash, no blow-up
        assert isinstance(out, str)
        assert len(out) <= len(src) + 8
def test_pt_el_latin_phrase_langs_include_living():
    t = _tessera()
    assert t.FINAL_PT_EL_LATIN_PHRASE_LANGS >= {"pt", "el", "it", "la"}
    assert t.FINAL_PHRASE_LANGS >= {"pt", "el", "it", "la"}


def test_pt_el_latin_phrase_bank_all_drop_tokens():
    t = _tessera()
    pairs = t.pt_el_latin_phrase_pairs()
    assert pairs, "sibling phrase bank should yield winning pairs"
    for src, dst, lang in pairs:
        assert lang in t.FINAL_PT_EL_LATIN_PHRASE_LANGS
        assert t.estimate_tokens(dst) < t.estimate_tokens(src)


def test_pt_el_latin_tense_bank_new_sources_only():
    t = _tessera()
    main_srcs = {s.lower() for s, _, _ in t.es_fr_tense_pairs()}
    for src, dst, lang in t.pt_el_latin_tense_pairs():
        assert src.lower() not in main_srcs, (src, "collides with es_fr_tense")
        assert lang in (t.FINAL_TENSE_LANGS | t.FINAL_PT_EL_LATIN_PHRASE_LANGS)
        assert t.estimate_tokens(dst) < t.estimate_tokens(src)


def test_cell_phone_maps_to_cel_or_kin():
    t = _tessera()
    raw = "Call me on my cell phone later."
    out = t.apply_zh_de_phrases(raw)
    assert "cell phone" not in out.lower()
    assert any(s in out for s in ("cel", "κιν"))
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_as_a_result_cheapest_ergo_or_logo():
    t = _tessera()
    raw = "as a result"
    out = t.apply_zh_de_phrases(raw)
    assert out in {"ergo", "logo", "άρα"}
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_once_again_prefers_pali():
    t = _tessera()
    out = t.apply_zh_de_phrases("once again")
    assert out == "πάλι"
    assert t.estimate_tokens(out) < t.estimate_tokens("once again")


def test_sibling_does_not_steal_bahnhof_or_asap():
    """Additive sibling must not rewrite help3 ZH/DE / EN acronym winners."""
    t = _tessera()
    src = "Meet me at the train station as soon as possible."
    out = t.apply_zh_de_phrases(src)
    assert "Bahnhof" in out
    assert "ASAP" in out
    assert "gare" not in out.lower()


def test_i_will_do_it_maps_to_farei():
    t = _tessera()
    raw = "I will do it tomorrow."
    out = t.apply_es_fr_tense(raw)
    assert "farei" in out
    assert "will do it" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_i_did_it_maps_to_fiz():
    t = _tessera()
    out = t.apply_es_fr_tense("I did it.")
    assert "fiz" in out
    assert t.estimate_tokens(out) < t.estimate_tokens("I did it.")


def test_final_pass_includes_sibling_phrase():
    t = _tessera()
    raw = "Pay per month for the cell phone."
    before = t.estimate_tokens(raw)
    out = t.final_token_pass(raw)
    after = t.estimate_tokens(out)
    assert "/mês" in out or "/μήνα" in out
    assert "cel" in out or "κιν" in out
    assert after < before


def test_classical_ibo_not_in_tense_pairs():
    t = _tessera()
    forms = {dst for _, dst, _ in t.es_fr_tense_pairs()} | {
        dst for _, dst, _ in t.pt_el_latin_tense_pairs()
    }
    assert "ibo" not in forms


def test_tense_tranche2_take_future_wins():
    """before: I will take … → after: tomaré/tomarei/πάρω (cheapest)."""
    t = _tessera()
    src = "I will take it tomorrow."
    out = t.apply_es_fr_tense(src)
    assert any(s in out for s in ("tomaré", "tomarei", "πάρω"))
    assert "will take" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_tense_tranche2_think_past_wins():
    t = _tessera()
    src = "I thought so."
    out = t.apply_es_fr_tense(src)
    assert any(s in out for s in ("pensé", "pensei"))
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_tense_tranche2_going_to_take_not_eaten_by_voy():
    """I'm going now → voy/vou; I'm going to take … → take future, not voy to."""
    t = _tessera()
    prog = t.apply_es_fr_tense("I'm going now.")
    assert any(s in prog for s in ("voy", "vou", "πάω"))
    raw = "I'm going to take it now."
    out = t.apply_es_fr_tense(raw)
    assert "voy to" not in out.lower()
    assert "vou to" not in out.lower()
    assert any(s in out for s in ("tomaré", "tomarei", "πάρω"))
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_tense_tranche2_try_and_read_prog():
    t = _tessera()
    try_out = t.apply_es_fr_tense("I will try again.")
    assert "tentarei" in try_out
    assert t.estimate_tokens(try_out) < t.estimate_tokens("I will try again.")
    read_out = t.apply_es_fr_tense("I'm reading now.")
    assert any(s in read_out for s in ("leo", "leio", "lis", "lees"))
    assert t.estimate_tokens(read_out) < t.estimate_tokens("I'm reading now.")


def test_tense_tranche2_all_going_to_entries_use_full_future_phrase():
    t = _tessera()
    expected = {"take": "πάρω", "try": "tentarei", "find": "βρω",
                "call": "llamaré", "put": "porei", "bring": "trarei"}
    for verb, winner in expected.items():
        for prefix in ("I am going to ", "I'm going to "):
            assert t.apply_es_fr_tense(prefix + verb + " now.") == winner + " now."
    # Existing I am -> sou remains valid; the motion verb must not become voy/vou.
    assert t.apply_es_fr_tense("I am going to inspect now.") == "sou going to inspect now."
    for raw in ("I'm going to inspect now.",
                "I put", "I read", "I will tell", "I will make", "I will ask", "I will get"):
        assert t.apply_es_fr_tense(raw) == raw


def test_tense_tranche2_and_sibling_longest_sources_coexist():
    t = _tessera()
    raw = "I will do it; I did it; I want to go; I need to go; I'm going to take it."
    assert t.apply_es_fr_tense(raw) == "farei; fiz; quero ir; preciso ir; πάρω it."
    raw = "I will take my mobile phone to the train station as soon as possible."
    assert t.apply_es_fr_tense(t.apply_zh_de_phrases(raw)) == "πάρω my cel to the Bahnhof ASAP."


def test_tense_candidate_priority_is_independent_of_bank_order():
    t = _tessera()
    # Exercise each cost tie-breaker rather than accepting any candidate.
    cases = [
        ([("tomaré", "es"), ("πάρω", "el")], "πάρω"),
        ([("pondré", "es"), ("porei", "pt")], "porei"),
        ([("é", "pt"), ("ab", "en")], "é"),
        ([("b", "en"), ("a", "en")], "a"),
    ]
    for candidates, winner in cases:
        assert t._cheapest_repl("I am going to take", candidates) == winner
        assert t._cheapest_repl("I am going to take", list(reversed(candidates))) == winner
    banks = (t.es_fr_tense_pairs(), t.pt_el_latin_tense_pairs())
    for src in ("I will take", "I will do it", "I want to go", "I'm going to bring"):
        a = t._apply_phrase_pairs(src, t._merge_phrase_pair_banks(*banks))
        b = t._apply_phrase_pairs(src, t._merge_phrase_pair_banks(*reversed(banks)))
        assert a == b == t.apply_es_fr_tense(src)


def test_tranche2_and_sibling_combined_final_pass():
    """Tense additions and sibling phrases compete in the same final pass."""
    t = _tessera()
    raw = "I'm going to take my mobile phone once again."
    out = t.final_token_pass(raw)
    assert any(form in out for form in ("tomaré", "tomarei", "πάρω"))
    assert any(form in out for form in ("cel", "κιν"))
    assert "πάλι" in out
    assert "voy to" not in out and "vou to" not in out
    assert t.estimate_tokens(out) < t.estimate_tokens(raw)


def test_tranche2_cheapest_for_every_source():
    """Check the selected surface, not only membership among candidates."""
    t = _tessera()
    entries = t.load_es_fr_tense_bank()["entries"]
    start = next(i for i, e in enumerate(entries) if e["id"] == "take-fut-1s")
    stop = next((i for i, e in enumerate(entries) if e["id"] == "arrive-past-1s"), len(entries))
    tranche2 = entries[start:stop]
    assert len(tranche2) == 35
    pairs = t.es_fr_tense_pairs() + t.pt_el_latin_tense_pairs()
    for entry in tranche2:
        for src in entry["from"]:
            forms = [dst for source, dst, _ in pairs if source.lower() == src.lower()]
            expected = min(forms, key=lambda s: (t.estimate_tokens(s), len(s.encode("utf-8")), len(s), s)) if forms else src
            assert t.apply_es_fr_tense(src) == expected, (entry["id"], src)


def test_tranche2_partial_verbs_and_going_to_guard():
    """An incomplete verb cannot trigger a full tense entry."""
    t = _tessera()
    for verb in ("take", "try", "find", "call", "put", "bring"):
        for stem in ("I am going to ", "I'm going to ", "I will "):
            for end in range(1, len(verb)):
                raw = stem + verb[:end]
                out = t.apply_es_fr_tense(raw)
                # Existing be entries may shorten I am; the partial verb stays.
                assert out.endswith(stem[stem.index("going"):] + verb[:end] if "going" in stem else "will " + verb[:end])
                assert t.estimate_tokens(out) <= t.estimate_tokens(raw)
    for raw in ("I'm going to", "I put", "I read"):
        assert t.apply_es_fr_tense(raw) == raw


def test_tranche2_future_does_not_choose_present_forms():
    t = _tessera()
    for stem, forms in (
        ("call", {"llamaré", "chamarei"}),
        ("bring", {"traeré", "trarei"}),
        ("write", {"écrirai"}),
        ("wait", {"esperaré"}),
    ):
        for prefix in ("I will ", "I am going to ", "I'm going to ") if stem in {"call", "bring"} else ("I will ",):
            raw = prefix + stem
            out = t.apply_es_fr_tense(raw)
            assert out in forms, (raw, out)
            assert t.estimate_tokens(out) < t.estimate_tokens(raw)
    assert t.apply_es_fr_tense("I'll call") == "I'll call"
