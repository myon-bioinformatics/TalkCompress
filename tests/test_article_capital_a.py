"""大文字 A は文頭のときだけ冠詞として落とす（Plan A / vitamin A などのラベルは保持）。"""
import pytest

from MorphoZip.morpho_zip import compress, strip_articles

KEEP = [
    ("Plan A failed.", "Plan A failed."),
    ("Take vitamin A daily.", "Take vitamin A daily."),
    ("Type A blood.", "Type A blood."),
    ("He got grade A work.", "He got grade A work."),
    ("Use A4 paper.", "Use A4 paper."),
    ("A4 paper.", "A4 paper."),
    ("A/B test.", "A/B test."),
    ("Run A/B tests.", "Run A/B tests."),
    ("J. A. Smith came.", "J. A. Smith came."),
    ("A. Smith came.", "A. Smith came."),
    ("Plan A.", "Plan A."),
    ("Plan A, then B.", "Plan A, then B."),
    ("Plan A\nfailed.", "Plan A\nfailed."),
]

DROP = [
    ("A cat sat.", "cat sat."),
    ("Hi. A cat sat.", "Hi. cat sat."),
    ("Hi! A cat.", "Hi! cat."),
    ("Hi? A cat.", "Hi? cat."),
    ("x\nA cat.", "x\ncat."),
    ("(A cat)", "(cat)"),
    ("[A cat]", "[cat]"),
    ('"A cat"', '"cat"'),
    ("'A cat'", "'cat'"),
    ("river.\u2014A dog.", "river.\u2014dog."),
    ('called "Nurse." A chef.', 'called "Nurse." chef.'),
    ("[aside] A reminder.", "[aside] reminder."),
    ("(aside) A reminder.", "(aside) reminder."),
    ("Plan A. A dog.", "Plan A. dog."),
]

LOWER = [
    ("I saw a cat and an owl.", "I saw cat and owl."),
    ("The end. An ox.", "end. ox."),
    ("THE END", "END"),
    ("Take a vitamin pill.", "Take vitamin pill."),
]


@pytest.mark.parametrize(("src", "want"), KEEP + DROP + LOWER)
def test_strip_articles_capital_a(src, want):
    assert strip_articles(src) == want


@pytest.mark.parametrize("label", ["Plan A", "vitamin A", "Type A", "grade A"])
def test_compress_keeps_label_a(label):
    assert f"{label} " in compress(f"Then {label} worked well.")


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("A said no.", "A said no."),
        ("A is the key.", "A is key."),
        ("A and B match.", "A and B match."),
        ('He said "A or B".', 'He said "A or B".'),
        ("A furnished flat.", "A furnished flat."),  # -ed 後は安全側で保持
    ],
)
def test_sentence_initial_a_before_predicate_is_symbol(src, want):
    assert strip_articles(src) == want

@pytest.mark.parametrize('predicate', ['is', 'wins', 'said', 'and', 'furnished'])
@pytest.mark.parametrize('case', [str.title, str.upper, lambda s: s[:1]+s[1:].upper()])
def test_symbol_predicate_case_preserved(predicate, case):
    text = 'A ' + case(predicate) + ' B.'
    assert strip_articles(text) == text

@pytest.mark.parametrize('src,want', [
    ('a IS key.', 'IS key.'),
    ('Plan A failed.', 'Plan A failed.'),
    ('A cat sat.', 'cat sat.'),
    ('THE END', 'END'),
    ('An owl.', 'owl.'),
    ('A ıs key.', 'ıs key.'),  # dotless i is not the ASCII predicate is
    ('A İS key is short.', 'İS key is short.'),  # English cue bypasses personal-a guard
])
def test_article_casefold_is_scoped(src, want):
    assert strip_articles(src) == want
