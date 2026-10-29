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
