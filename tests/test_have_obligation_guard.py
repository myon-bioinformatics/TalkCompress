"""Have-ending possession rows (I had → tive) never fire before 'to <verb>' or a bare verb."""

import pytest

from TesseraTalk import tessera_talk as t

_SUBJECTS = ("I", "you", "he", "she", "it", "we", "they", "this", "who", "which")
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
