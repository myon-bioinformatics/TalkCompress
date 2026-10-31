"""ASCII rules must not case-fold onto Turkish İ/ı, long s ſ or the Kelvin sign."""

import pytest

from Zipilogue.dialogue_lab import encode, validate_mapping

RULE = [{"long": "kiss", "short": "k"}]


@pytest.mark.parametrize("text", ["KİSS", "kıss", "kiſs"])
def test_encode_leaves_non_ascii_lookalikes(text):
    assert encode(text, RULE) == text


def test_encode_kelvin_sign_is_nfc_k():
    # NFC は U+212A（ケルビン記号）を正準等価な ASCII の K に置き換えるので、
    # encode の NFC 正規化後は普通の KISS として扱われる。
    assert encode("\u212aISS", RULE) == "k"


def test_encode_keeps_ascii_and_unicode_case_insensitivity():
    assert encode("KISS, Kiss kiss", RULE) == "k, k k"
    assert encode("Café CAFÉ", [{"long": "café", "short": "c"}]) == "c c"


def _train(text):
    return [{"text": text}]


def test_validate_code_does_not_collide_with_dotless_i():
    # observed is casefolded first (K/ſ already become k/s there: a conservative
    # rejection); ı survives casefold and must not match code "i" via re.I.
    payload = {"mapping": [{"long": "hello world", "short": "i"}]}
    assert validate_mapping(payload, _train("hello world ı")) == payload["mapping"]
    with pytest.raises(ValueError, match="collides"):
        validate_mapping(payload, _train("hello world I"))


def test_validate_code_inside_long_ignores_dotless_i():
    payload = {"mapping": [{"long": "ı like it", "short": "i"}, {"long": "hello there", "short": "h"}]}
    assert len(validate_mapping(payload, _train("ı like it hello there"))) == 2


def test_encode_non_ascii_long_with_lookalike_does_not_raise():
    # Non-ASCII long forms keep Unicode re.I, so "Ié" matches "ıé" but its
    # casefold misses the lookup: leave it as-is instead of KeyError.
    rule = [{"long": "ıé", "short": "q"}]
    assert encode("Ié yes", rule) == "Ié yes"
    assert encode("ıé", rule) == "q"
