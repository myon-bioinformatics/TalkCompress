"""TesseraTalk (B): LID/RLE mosaic + translation token-min patterns.

B weight: translation-based token savings (EN/JA/ZH + natural short forms).
Unlike C ShorthandEdge, B does not apply the agreed ledger patches.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _tessera():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


# --- LID / RLE mosaic (keep expanding patterns) ---


def test_lid_multi_sentence_en_ja_zh():
    t = _tessera()
    src = "Hello there. こんにちは。你好世界。"
    tagged = t.tag_sentences(src)
    langs = [lang for lang, _ in tagged]
    assert "en" in langs
    assert "ja" in langs
    assert "zh" in langs


def test_lid_language_switch_run_and_rle():
    t = _tessera()
    src = "One. Two. Three. 第一。第二。Hello again. World."
    mosaic = t.compress(src, rle=True)
    # EN run at start: one en: then bare sentences
    assert mosaic.startswith("en:")
    assert mosaic.count("en:") >= 1
    assert "ja:" in mosaic or "zh:" in mosaic
    back = t.expand(mosaic)
    assert "One" in back and "Three" in back
    assert "Hello again" in back


def test_rle_omits_repeat_tags_across_switch_back():
    t = _tessera()
    src = "Alpha. Beta. こんにちは。また。Gamma. Delta."
    mosaic = t.compress(src, rle=True)
    parts = mosaic.split("|")
    # After first en:, next EN in same run should be bare; after ja run, en returns with tag
    assert parts[0].startswith("en:")
    # at least one bare (no lang:) part exists in an EN run
    bare = [p for p in parts if ":" not in p[:8] or (not p[:3].isalpha() and ":" in p)]
    # simpler: count full tags less than sentence count
    tagged = t.tag_sentences(src)
    full = t.compress(src, rle=False)
    assert full.count(":") >= mosaic.count(":")
    assert len(tagged) >= 5
    assert "Gamma" in t.expand(mosaic)


def test_mosaic_zh_pure_cjk_detect():
    t = _tessera()
    assert t.detect_lang("今天天气很好。") == "zh"
    mosaic = t.compress("今天天气很好。明天见。", rle=True)
    assert mosaic.startswith("zh:")
    assert mosaic.count("zh:") == 1  # RLE one tag for run


def test_mosaic_paragraph_preserve_with_switches():
    t = _tessera()
    src = "Hello.\n\nこんにちは。\n\n你好。"
    mosaic = t.compress(src, preserve_newlines=True, rle=True)
    assert "¶" in mosaic
    back = t.expand(mosaic, preserve_newlines=True)
    assert back.count("\n\n") >= 2
    assert "Hello" in back and "你好" in back


# --- estimate_tokens ranking ---


def test_estimate_tokens_cjk_denser_than_long_english():
    t = _tessera()
    en = "Thank you very much."
    zh = "多谢。"
    assert t.estimate_tokens(zh) < t.estimate_tokens(en)


def test_estimate_tokens_empty():
    t = _tessera()
    assert t.estimate_tokens("") == 0
    assert t.estimate_tokens("   ") == 0


# --- pick shorter translation ---


def test_pick_en_to_zh_when_shorter():
    t = _tessera()
    chosen, lang, n = t.pick_shortest_translation("Good morning.")
    assert lang == "zh"
    assert chosen == "早。"
    assert n < t.estimate_tokens("Good morning.")


def test_pick_en_natural_abbrev_asap():
    t = _tessera()
    chosen, lang, _ = t.pick_shortest_translation("Please reply as soon as possible.")
    assert "ASAP" in chosen
    assert lang == "en"
    assert t.estimate_tokens(chosen) < t.estimate_tokens(
        "Please reply as soon as possible."
    )


def test_pick_en_natural_abbrev_fyi():
    t = _tessera()
    chosen, lang, _ = t.pick_shortest_translation(
        "For your information, the build is ready."
    )
    assert "FYI" in chosen
    assert lang == "en"


def test_pick_ja_to_shorter_ja_or_other():
    t = _tessera()
    src = "今日はとても良い天気ですね。"
    chosen, lang, n = t.pick_shortest_translation(src)
    assert n < t.estimate_tokens(src)
    assert chosen != src
    assert lang in ("ja", "zh", "en")


def test_pick_zh_to_shorter_when_tokens_drop():
    t = _tessera()
    src = "我们今天下午三点开会讨论这个问题。"
    chosen, lang, n = t.pick_shortest_translation(src)
    assert n < t.estimate_tokens(src)
    assert chosen != src


def test_pick_info_three_animals_natural_short():
    t = _tessera()
    src = "I will find out the information about three animals."
    chosen, lang, n = t.pick_shortest_translation(src)
    assert n < t.estimate_tokens(src)
    # natural short / digit form OK for B
    assert "3" in chosen or "三" in chosen or "匹" in chosen


def test_keep_original_when_not_shorter():
    t = _tessera()
    # OK. candidates are all longer or equal
    chosen, lang, n = t.pick_shortest_translation("OK.")
    assert chosen == "OK."
    assert lang == "src"
    assert n == t.estimate_tokens("OK.")


def test_keep_original_unknown_sentence():
    t = _tessera()
    src = "Xylophone zebra quantum foobar uniquely long."
    chosen, lang, _ = t.pick_shortest_translation(src)
    assert chosen == src
    assert lang == "src"


def test_explicit_candidates_override_bank():
    t = _tessera()
    chosen, lang, n = t.pick_shortest_translation(
        "Hello world forever and ever.",
        candidates={"zh": "你好。", "en": "Hi forever and ever and ever."},
    )
    assert chosen == "你好。"
    assert lang == "zh"
    assert n < t.estimate_tokens("Hello world forever and ever.")


def test_allow_langs_filters_candidates():
    t = _tessera()
    # Good morning. zh wins globally; restrict to en → Morning.
    chosen, lang, _ = t.pick_shortest_translation(
        "Good morning.", allow_langs={"en"}
    )
    assert lang == "en"
    assert chosen == "Morning."


# --- minify_by_translation + compress(translate_min=True) ---


def test_minify_multi_sentence_mixed():
    t = _tessera()
    src = "Good morning. Please reply as soon as possible."
    out = t.minify_by_translation(src)
    assert "早" in out or "Morning" in out
    assert "ASAP" in out


def test_compress_translate_min_mosaic():
    t = _tessera()
    src = "Good morning. 今日はとても良い天気ですね。"
    mosaic = t.compress(src, translate_min=True, rle=True)
    # After minify, expect short forms then mosaic tags
    plain = t.minify_by_translation(src)
    assert t.estimate_tokens(plain) < t.estimate_tokens(src)
    back = t.expand(mosaic)
    assert len(back) > 0
    # should not be identical to raw long forms
    assert "Good morning" not in back or "早" in mosaic or "Morning" in mosaic


def test_see_you_later_natural_short():
    t = _tessera()
    chosen, _, n = t.pick_shortest_translation("See you later.")
    assert n < t.estimate_tokens("See you later.")
    assert chosen in ("CUL8R.", "再见。", "またね。") or len(chosen) < len(
        "See you later."
    )


# --- regression: B ≠ C ledger ---


def test_b_does_not_apply_c_ledger_under_alone():
    t = _tessera()
    # No bank entry for bare "under" / "below" as C-style patch
    for raw in ("under", "below", "beneath", "above"):
        chosen, lang, _ = t.pick_shortest_translation(raw)
        assert chosen == raw
        assert lang == "src"
        assert chosen not in ("下", "上")


def test_b_under_sentence_uses_translation_not_ledger_patch():
    t = _tessera()
    src = "The cat is under the table."
    chosen, lang, n = t.pick_shortest_translation(src)
    assert n < t.estimate_tokens(src)
    # Must not be the C ledger one-char swap "…下…" via under→下 alone on English
    # Accept full translation; reject English with only under replaced by 下
    assert chosen != "The cat is 下 the table."
    assert "under" not in chosen.lower() or chosen == src


def test_b_bumpy_not_c_凹凸_ledger():
    t = _tessera()
    src = "The road is bumpy."
    chosen, _, _ = t.pick_shortest_translation(src)
    # C ledger maps bumpy → 凹凸; B must not emit bare 凹凸 from ledger
    assert chosen != "凹凸"
    assert chosen != "The road is 凹凸."


def test_b_minify_leaves_unknown_ledger_words():
    t = _tessera()
    src = "Stay under below above bumpy uneven."
    out = t.minify_by_translation(src)
    # no bank hit → unchanged; crucially no C ledger substitutions
    assert out == src or "下" not in out
    assert "凹凸" not in out


def test_translation_bank_loads():
    t = _tessera()
    data = t.load_translation_bank()
    assert "entries" in data
    assert len(data["entries"]) >= 8
    idx = t.translation_index()
    assert t._norm_lookup_key("Good morning.") in idx


def test_how_are_you_shorter():
    t = _tessera()
    chosen, lang, n = t.pick_shortest_translation("How are you?")
    assert n < t.estimate_tokens("How are you?")
    assert chosen != "How are you?"
