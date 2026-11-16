"""SentenceCalibratedMosaic (B) 最終パス: 誤発火させないガード（助動詞・義務・法助動詞・埋め込み主語・短縮形・that の役割）。

- aux_participle_guard: Subject+have rows (I had → tive) must not fire as auxiliaries before a past participle.
- have_obligation_guard: Have-ending possession rows (I had → tive) never fire before 'to <verb>' or a bare verb.
- modal_infinitive_guard: Modal rows (I must → debo, I could → pude) never fire before an English verb.
- embedded_subject_guard: Pro-drop only at clause start: embedded-clause subjects are never lost.
- contraction_type: 's (is|has|possessive) / 'd (would|had) type disambiguation sweep (B-final).
- that_role: Explicit role classifier for ``that`` + comma / discourse-adverb handling.
"""

from __future__ import annotations

from SentenceCalibratedMosaic import sentence_calibrated_mosaic as t
from SentenceCalibratedMosaic.sentence_calibrated_mosaic import _contraction_type
from SentenceCalibratedMosaic.sentence_calibrated_mosaic import _subject_aux_variants
from SentenceCalibratedMosaic.sentence_calibrated_mosaic import apply_es_fr_tense
from SentenceCalibratedMosaic.sentence_calibrated_mosaic import tense_matrix_pairs
from pathlib import Path
from tests._helpers import load as _load
import json
import re

import pytest


# ──── aux_participle_guard ────────────────────────────────────────

"""Subject+have rows (I had → tive) must not fire as auxiliaries before a past participle."""


POSSESSIVE_SHORTS = ("tive", "tuve")


@pytest.mark.parametrize("src", ["I had gone", "we had done", "she had seen", "I had been", "he had gone"])
def test_had_plus_participle_never_left_half_converted(src):
    out = t.apply_es_fr_tense(src)
    # Either the full phrase is converted by the matrix, or EN stays intact.
    assert out == src or " " not in out or not out.lower().endswith(src.split()[-1].lower()), out
    for short in POSSESSIVE_SHORTS:
        assert not out.startswith(short + " "), (src, out)
    assert t.estimate_tokens(out) <= t.estimate_tokens(src)


def test_i_had_gone_stays_english():
    assert t.apply_es_fr_tense("I had gone") == "I had gone"


def test_full_pluperfect_still_compressed_by_matrix():
    assert t.apply_es_fr_tense("I had done") == "fizera"
    assert t.apply_es_fr_tense("she had seen") == "vira"


def test_i_had_possessive_still_converted():
    assert t.apply_es_fr_tense("I had a book") == "tive a book"
    assert t.apply_es_fr_tense("I had") in POSSESSIVE_SHORTS


def test_regular_ed_participle_guarded():
    out = t.apply_es_fr_tense("I had walked home")
    assert not out.startswith(("tive ", "tuve ")), out


_SUBJECTS = ("I", "you", "he", "she", "it", "we", "they", "this", "who", "which")


_AUXES = ("had", "have", "has", "'d", "'ve", "'s", "will have", "'ll have",
          "would have", "could have", "should have", "must have", "might have")


_PPS = ("gone", "done", "seen", "been", "had", "taken", "eaten", "walked", "broken", "left")


def test_no_converted_aux_with_unconverted_english_participle():
    """Type guard: possessive-have / modal rows never yield 'tive gone' / 'pude have gone'."""
    bad = []
    for s in _SUBJECTS:
        for a in _AUXES:
            head = f"{s}{a}" if a.startswith("'") else f"{s} {a}"
            for p in _PPS:
                for tail in ("", " home"):
                    src = f"{head} {p}{tail}"
                    out = t.apply_es_fr_tense(src)
                    # you→U alone (apply_you_u) is not an aux conversion.
                    kept = (src, t.apply_you_u(src))
                    heads = {head.lower(), t.apply_you_u(head).lower()}
                    if out in kept or any(out.lower().startswith(h + " ") for h in heads):
                        continue
                    words = out.split()
                    pp_at = words[-2] if tail else words[-1]
                    if pp_at == p:
                        bad.append((src, out))
    assert not bad, bad[:10]


def test_modal_before_have_participle_not_converted():
    assert t.apply_es_fr_tense("I could have gone") == "I could have gone"
    assert t.apply_es_fr_tense("I must have seen it") == "I must have seen it"
    assert t.apply_es_fr_tense("I could") == "pude"  # reversal undone: docs/reaudit_b_4bot_context_roundtrip_20261110.md


def test_conj_table_has_no_garbage_forms():
    import json
    import re
    from pathlib import Path

    data = json.loads(Path("SentenceCalibratedMosaic/fixtures/tense_conj_table.json").read_text(encoding="utf-8"))
    bad = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, str) and path.startswith("/conj") and re.search(r"[()\[\]{}]", o):
            bad.append((path, o))

    walk(data)
    assert not bad, bad


# ──── have_obligation_guard ───────────────────────────────────────

"""Have-ending possession rows (I had → tive) never fire before 'to <verb>' or a bare verb."""


_HAVES = ("had", "have", "has", "'ve", "'s", "'d")


_VERBS = ("go", "do", "see", "eat", "come", "make", "take", "be", "say",
          "get", "know", "think", "buy", "live", "work", "leave")


def _head(s, a):
    return f"{s}{a}" if a.startswith("'") else f"{s} {a}"


def _shorts():
    return {
        r.lower()
        for p, r, _ in t._merge_phrase_pair_banks(
            t.es_fr_tense_pairs(), t.pt_el_latin_tense_pairs(), t.tense_matrix_pairs()
        )
        if t._HAVE_AUX_TAIL_RE.search(p) and " " not in r
    }


def test_no_converted_have_before_to_or_bare_verb():
    shorts = _shorts()
    assert "tive" in shorts
    bad = []
    for s in _SUBJECTS:
        for a in _HAVES:
            for v in _VERBS:
                for mid in ("to ", ""):
                    for tail in ("", " it", " home"):
                        src = f"{_head(s, a)} {mid}{v}{tail}"
                        out = t.apply_es_fr_tense(src)
                        w = out.lower().split()
                        nxt = (mid.strip() or v)
                        for i, x in enumerate(w[:-1]):
                            if x in shorts and w[i + 1] == nxt:
                                bad.append((src, out))
    assert not bad, bad[:10]


@pytest.mark.parametrize("src", ["I had to go", "I had go", "she had to eat it", "we had to do it"])
def test_obligation_stays_english(src):
    assert t.apply_es_fr_tense(src) == src


@pytest.mark.parametrize("src,want", [("I had a book", "tive a book"), ("I had.", "tive.")])
def test_possession_still_converts(src, want):
    assert t.apply_es_fr_tense(src) == want


# ──── modal_infinitive_guard ──────────────────────────────────────

"""Modal rows (I must → debo, I could → pude) never fire before an English verb."""


_MODALS = ("must", "can", "could", "should", "would", "will", "may", "might", "shall",
           "'ll", "'d", "cannot", "can't", "won't", "couldn't")


_VERBS_modal_infinitive_guard = ("go", "do", "see", "eat", "come", "make", "take", "be", "have", "say",
          "get", "know", "think", "want", "like", "buy", "live", "work", "not go")


# Every short form a modal-only row can produce.
_MODAL_SHORTS = sorted(
    {
        r.lower()
        for p, r, _ in t._merge_phrase_pair_banks(
            t.es_fr_tense_pairs(), t.pt_el_latin_tense_pairs(), t.tense_matrix_pairs()
        )
        if t._MODAL_TAIL_RE.search(p)
    }
)


def _head_modal_infinitive_guard(s, m):
    return f"{s}{m}" if m.startswith("'") else f"{s} {m}"


def test_modal_shorts_discovered():
    assert {"debo", "pude"} <= set(_MODAL_SHORTS)  # pude reversal undone (reaudit_b_4bot)


def test_no_converted_modal_with_english_verb():
    bad = []
    for s in _SUBJECTS:
        for m in _MODALS:
            for v in _VERBS_modal_infinitive_guard:
                for tail in ("", " it", " home"):
                    src = f"{_head_modal_infinitive_guard(s, m)} {v}{tail}"
                    out = t.apply_es_fr_tense(src)
                    words = out.lower().split()
                    for i, w in enumerate(words[:-1]):
                        if w in _MODAL_SHORTS and words[i + 1] == v.split()[0]:
                            bad.append((src, out))
    assert not bad, bad[:10]


@pytest.mark.parametrize(
    "src", ["I must go", "I could see", "I could not go", "I must eat it"]
)
def test_modal_plus_bare_infinitive_stays_english(src):
    assert t.apply_es_fr_tense(src) == src


@pytest.mark.parametrize(
    "src,want", [("I must", "debo"), ("I could", "pude"), ("I must.", "debo."),
                 ("I'll go", "vou"), ("I would like", "gostaria")]
)
def test_full_modal_phrases_still_compress(src, want):
    assert t.apply_es_fr_tense(src) == want


def test_no_converted_aux_or_modal_before_english_verb_general():
    """General sweep: no short of a phrase-final aux/modal row is followed by the EN verb."""
    aux_tail = re.compile(
        r"(?:" + t._MODAL_TAIL_RE.pattern + r"|(?:\b(?:had|have|has)|'ve|'s)$)", re.I
    )
    shorts = {
        r.lower()
        for p, r, _ in t._merge_phrase_pair_banks(
            t.es_fr_tense_pairs(), t.pt_el_latin_tense_pairs(), t.tense_matrix_pairs()
        )
        if aux_tail.search(p) and " " not in r
    }
    pps = ("gone", "done", "seen", "been", "walked", "taken")
    bad = []
    for s in _SUBJECTS:
        for a in _MODALS + ("had", "have", "has", "'ve", "'s"):
            # modals govern a bare infinitive; have-auxes govern a participle.
            nexts = _VERBS_modal_infinitive_guard + tuple("have " + p for p in pps) if a in _MODALS else pps
            for v in nexts:
                src = f"{_head_modal_infinitive_guard(s, a)} {v}"
                out = t.apply_es_fr_tense(src)
                w = out.lower().split()
                if len(w) >= 2 and w[0] in shorts and w[1] == v.split()[0]:
                    bad.append((src, out))
    assert not bad, bad[:10]


# ──── embedded_subject_guard ──────────────────────────────────────

"""Pro-drop only at clause start: embedded-clause subjects are never lost."""


ROOT = Path(__file__).resolve().parents[1]


BANK = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/tense_matrix.json").read_text(encoding="utf-8"))


SUBJ = {"i", "you", "he", "she", "it", "we", "they"}


MAINS = ["I think", "She said", "We know", "They hope"]


CONNECTORS = ["that", "which", "who", "if", "when", "because", "", "and"]


def _t():
    return _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def _embedded_sources():
    seen = {}
    for e in BANK["entries"]:
        for src in e["from"]:
            subj = re.split(r"['’ ]", src, maxsplit=1)[0].lower()
            if subj in SUBJ:
                seen.setdefault((subj, e["tense"]), src)
    return sorted(seen.items())


EMB = _embedded_sources()


def test_sweep_covers_all_subjects_and_many_tenses():
    assert {s for (s, _), _src in EMB} == SUBJ
    assert len({t for (_, t), _src in EMB}) >= 8


@pytest.mark.parametrize("main", MAINS)
@pytest.mark.parametrize("conn", CONNECTORS)
def test_embedded_subject_never_lost(main, conn):
    t = _t()
    for (subj, _tense), src in EMB:
        lead = f"{main} {conn} ".replace("  ", " ") if conn else f"{main} "
        out = t.apply_es_fr_tense(lead + src)
        tail = out.split(" ", 2)[-1] if conn else out
        head = src.split(" ", 1)[0]
        # you is kept as its 1-char surface U (apply_you_u), never dropped.
        heads = (head, "U") if head.lower() == "you" else (head,)
        assert any(
            re.search(rf"(?<![A-Za-z']){re.escape(h)}(?![A-Za-z'])", out, re.I) for h in heads
        ), (lead + src, out)
        assert tail


def test_regression_examples():
    t = _t()
    assert t.apply_es_fr_tense("I think that he is going") == "denk that he is going"
    assert t.apply_es_fr_tense("I know he is going") == "sé he is going"
    assert t.apply_es_fr_tense("he is going") == "he is going"  # o200k: "he's going" (2) unbeaten
    assert t.apply_es_fr_tense("Yes. He is going") == "Yes. He is going"
    assert t.apply_es_fr_tense("I said, he went").endswith("he went")


# ──── contraction_type ────────────────────────────────────────────

"""'s (is|has|possessive) / 'd (would|had) type disambiguation sweep (B-final)."""


SUBJECTS = ["I", "you", "he", "she", "it", "we", "they", "who"]


# right-context classes → expected reading of the contraction
D_CTX = {
    "had": ["gone", "done", "seen", "given", "said", "had", "wanted", "thought"],
    "would": ["go", "like", "rather", "see", "do"],
}


S_CTX = {
    "has": ["been", "gone", "had"],
    "is": ["going", "coming", "doing", "seeing", "giving"],
    # ambiguous (passive/adjective is vs perfect has) → must stay EN
    "ambiguous": ["finished", "done", "seen", "said", "given", "tired", "happy"],
}


def _full_winner(full: str) -> str:
    return apply_es_fr_tense(full + ".")


@pytest.mark.parametrize("subj", SUBJECTS)
@pytest.mark.parametrize("kind", sorted(D_CTX))
def test_d_contraction_type_correct_or_en(subj: str, kind: str) -> None:
    for word in D_CTX[kind]:
        short = f"{subj}'d {word}."
        out = apply_es_fr_tense(short)
        if out == short:
            continue
        # Converted → must equal the winner of the correctly-typed full form.
        assert out == _full_winner(f"{subj} {kind} {word}"), (short, out)


@pytest.mark.parametrize("subj", ["he", "she", "it", "who"])
@pytest.mark.parametrize("kind", sorted(S_CTX))
def test_s_contraction_type_correct_or_en(subj: str, kind: str) -> None:
    for word in S_CTX[kind]:
        short = f"{subj}'s {word}."
        out = apply_es_fr_tense(short)
        if kind == "ambiguous":
            assert out == short, (short, out)
        elif out != short:
            assert out == _full_winner(f"{subj} {kind} {word}"), (short, out)


@pytest.mark.parametrize(
    "text",
    [
        "John's book.", "John's gone.", "the dog's been fed.", "Mary's going home.",
        "my friend's seen it.", "let's go.", "let's see.", "Tom'd gone.",
        "it's finished.", "it's done.", "he's tired.", "that's gone.",
    ],
)
def test_possessive_and_unknown_heads_never_convert(text: str) -> None:
    assert apply_es_fr_tense(text) == text


def test_no_mistyped_twins_in_matrix_sources() -> None:
    for src, _repl, _lang in tense_matrix_pairs():
        m = re.match(r"(\S+)'([sd]) (\S+)", src)
        if not m:
            continue
        aux = {"s": ("is", "has"), "d": ("would", "had")}[m.group(2)]
        assert any(_contraction_type(a, m.group(3)) for a in aux), src


def test_variants_are_typed() -> None:
    assert "he's gone" in _subject_aux_variants("he has gone")
    assert "he's done" not in _subject_aux_variants("he has done")
    assert "he's going" in _subject_aux_variants("he is going")
    assert "I'd go" in _subject_aux_variants("I would go")
    assert "I'd gone" not in _subject_aux_variants("I would gone")
    assert "I'd seen" in _subject_aux_variants("I had seen")
    assert "I'd come" not in _subject_aux_variants("I had come")  # would|had
    assert "I'd go" not in _subject_aux_variants("I had go")


# ──── that_role ───────────────────────────────────────────────────

"""Explicit role classifier for ``that`` + comma / discourse-adverb handling."""


def _roles(s: str) -> list[str]:
    t = _t()
    return [t.classify_that_role(s, m.start()) for m in re.finditer(r"(?<![A-Za-z])that(?![A-Za-z])", s, re.I)]


COMPLEMENTIZER = [
    "dedicated to the proposition that all men are created equal",
    "the fact that he is going",
    "I think that he is going",
    "She said that we will go",
    "We know that they were here",
    "I believe that it is true",
    "I am sure that we will go",
    "I'm glad that you came",
    "the idea that we could win",
    "the news that he had left",
    "They hope that I am right",
    "It is clear that she is going",
]


RELATIVE = [
    "the man that is going",
    "the car that was here",
    "a book that has gone",
    "the people that were waiting",
    "the book that I read",
    "the house that we built",
    "every plan that they made",
    "the idea that is going",
]


DETERMINER = ["that book is good", "I want that car", "Look at that dog", "That man is here"]


DEMONSTRATIVE = ["that is going", "I like that.", "That was fun", "I know that.", "That, however, is fine"]


@pytest.mark.parametrize("s", COMPLEMENTIZER)
def test_complementizer(s):
    assert _roles(s)[-1] == "complementizer"
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s))  # stays EN


@pytest.mark.parametrize("s", RELATIVE)
def test_relative(s):
    assert _roles(s)[-1] == "relative"


@pytest.mark.parametrize("s", DETERMINER)
def test_determiner(s):
    assert _roles(s)[0] == "determiner"
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s), re.I)


@pytest.mark.parametrize("s", DEMONSTRATIVE)
def test_demonstrative(s):
    assert "demonstrative" in _roles(s)
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s), re.I)


def test_gettysburg_both_roles():
    s = "conceived in Liberty, and dedicated to the proposition that all men are created equal"
    assert _roles(s) == ["complementizer"]
    assert _t().apply_es_fr_tense(s) == s


def test_relative_subject_slot_becomes_que_only():
    t = _t()
    assert t.apply_es_fr_tense("the man that is going").startswith("the man que ")
    # object relative / complementizer / determiner / demonstrative: that stays
    for s in ["the book that I read", "I think that he is going", "that book", "that is", "I like that."]:
        assert re.search(r"\bthat\b", t.apply_es_fr_tense(s), re.I), s


def test_unclassifiable_stays_english():
    t = _t()
    assert t.classify_that_role("people that are going", 7) == "unknown"
    assert "that" in t.apply_es_fr_tense("people that are going")


COMMA_CASES = [
    "However, he is going",
    "Yes. However, he is going",
    "I know, however, he is going",
    "he is, however, going",
    "Therefore, we will go, and he is going",
    "If he goes, he will go",
    "In fact, she is coming",
    "The man, who is going, is here",
]


@pytest.mark.parametrize("s", COMMA_CASES)
def test_commas_always_preserved(s):
    out = _t().apply_es_fr_tense(s)
    assert out.count(",") == s.count(",")


@pytest.mark.parametrize("adv", ["However", "Therefore", "Moreover", "In fact", "Of course", "Nevertheless"])
def test_sentence_initial_discourse_adverb_keeps_clause_start(adv):
    t = _t()
    base = t.apply_es_fr_tense("he is going")
    assert t.apply_es_fr_tense(f"{adv}, he is going") == f"{adv}, {base}"
    assert t.apply_es_fr_tense(f"Yes. {adv}, he is going") == f"Yes. {adv}, {base}"


def test_mid_sentence_parenthetical_does_not_unlock_pro_drop():
    t = _t()
    assert t.apply_es_fr_tense("I know, however, he is going").endswith("however, he is going")
    assert t.apply_es_fr_tense("he is, however, going") == "he is, however, going"
