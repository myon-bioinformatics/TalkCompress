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
    assert "高速" in out
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
    t = _tessera()
    src = "I will go tomorrow."
    out = t.apply_es_fr_tense(src)
    assert "iré" in out
    assert "will go" not in out.lower()
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_es_fr_tense_progressive_to_present():
    t = _tessera()
    src = "I'm going now."
    out = t.apply_es_fr_tense(src)
    assert "voy" in out
    assert t.estimate_tokens(out) < t.estimate_tokens(src)


def test_es_fr_tense_bank_all_drop_tokens():
    t = _tessera()
    for src, dst, lang in t.es_fr_tense_pairs():
        assert lang in {"es", "fr"}
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
    t = _tessera()
    src = "I will go to the train station as soon as possible."
    before = t.estimate_tokens(src)
    out = t.final_token_pass(src)
    after = t.estimate_tokens(out)
    assert "iré" in out
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
