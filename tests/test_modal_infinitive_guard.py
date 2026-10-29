"""Modal rows (I must → debo, I could → pude) never fire before an English verb."""

import re

import pytest

from TesseraTalk import tessera_talk as t

_SUBJECTS = ("I", "you", "he", "she", "it", "we", "they", "this", "who", "which")
_MODALS = ("must", "can", "could", "should", "would", "will", "may", "might", "shall",
           "'ll", "'d", "cannot", "can't", "won't", "couldn't")
_VERBS = ("go", "do", "see", "eat", "come", "make", "take", "be", "have", "say",
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


def _head(s, m):
    return f"{s}{m}" if m.startswith("'") else f"{s} {m}"


def test_modal_shorts_discovered():
    assert {"debo", "pude"} <= set(_MODAL_SHORTS)


def test_no_converted_modal_with_english_verb():
    bad = []
    for s in _SUBJECTS:
        for m in _MODALS:
            for v in _VERBS:
                for tail in ("", " it", " home"):
                    src = f"{_head(s, m)} {v}{tail}"
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
            nexts = _VERBS + tuple("have " + p for p in pps) if a in _MODALS else pps
            for v in nexts:
                src = f"{_head(s, a)} {v}"
                out = t.apply_es_fr_tense(src)
                w = out.lower().split()
                if len(w) >= 2 and w[0] in shorts and w[1] == v.split()[0]:
                    bad.append((src, out))
    assert not bad, bad[:10]
