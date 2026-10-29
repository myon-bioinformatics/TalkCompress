"""Subject+have rows (I had → tive) must not fire as auxiliaries before a past participle."""

import pytest

from TesseraTalk import tessera_talk as t

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
    assert t.apply_es_fr_tense("I could") == "pude"


def test_conj_table_has_no_garbage_forms():
    import json
    import re
    from pathlib import Path

    data = json.loads(Path("TesseraTalk/fixtures/tense_conj_table.json").read_text(encoding="utf-8"))
    bad = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, str) and path.startswith("/conj") and re.search(r"[()\[\]{}]", o):
            bad.append((path, o))

    walk(data)
    assert not bad, bad
