"""#147: correction is scoped by block/control, without changing shared tokenization."""
import pytest
from TesseraTalk.tessera_talk import estimate_tokens, _pretokens


@pytest.mark.parametrize('text, expected', [
    ('ශ්‍රී', 4),  # o200k=2; main=5. Residual error is deliberately retained.
    ('ස්\u200dතූතියි.', 7),  # o200k=7; main=8
    ('ខ្ញុំ\u200bគឺជាអ្នក\u200bគេង\u200bល្វាស ។', 17),  # o200k=15; main=20
    ('ກ\u200bຂ', 4),  # main=5
])
def test_supported_interior_controls(text, expected):
    assert estimate_tokens(text) == expected


@pytest.mark.parametrize('text, expected', [
    ('ক্‍ষ', 3), ('ক্‌ষ', 3), ('ক\u200bখ', 3),
    ('ଓଡ଼ିଆ', 2), ('ଓ\u200bଡ଼ିଆ', 4), ('ଓ\u200cଡ଼ିଆ', 4), ('ଓ\u200dଡ଼ିଆ', 4),
    ('👨‍👩‍👧‍👦', 11), ('👩🏽‍💻', 7), ('❤️', 1), ('☺️', 2),
    ('ක\u200bក', 3), ('ক\u200bක', 3), ('ක\u200d👩', 4),
    ('\u200bក', 2), ('ក\u200b', 2), ('ក\u200b\u200bក', 3),
    ('அກ\u200bຂ', 4), ('কກ\u200bຂ', 4), ('ກ\u200bຂক', 7),
    ('කක\u200dකক', 5), ('កខ\u200bគஅ', 5),
    ('ක\u200cක', 3), ('क्‍ष', 4), ('ไทยລາວ', 7),
])
def test_excluded_controls_and_scripts_keep_baseline(text, expected):
    assert estimate_tokens(text) == expected


def test_shared_pretokensr_still_splits_controls():
    assert _pretokens('ក\u200bខ') == [('i', 'ក'), ('p', '\u200b'), ('i', 'ខ')]
    assert _pretokens('ශ්‍රී') == [('i', 'ශ්'), ('e', '\u200d'), ('i', 'රී')]
