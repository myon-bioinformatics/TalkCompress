"""'s (is|has|possessive) / 'd (would|had) type disambiguation sweep (B-final)."""
from __future__ import annotations

import re

import pytest

from TesseraTalk.tessera_talk import (
    _contraction_type,
    _subject_aux_variants,
    apply_es_fr_tense,
    tense_matrix_pairs,
)

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
