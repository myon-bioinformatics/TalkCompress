import pytest

from MorphoZip.morpho_zip import compress, strip_articles


@pytest.mark.parametrize(
    "text",
    ["Mark it ‘A’ now.", 'Mark it "A" now.', "Mark it 'A' now.", "Grade “A” work."],
)
def test_quoted_capital_a_keeps_quotes(text):
    for fn in (strip_articles, compress):
        out = fn(text)
        assert "A" in out and out.count("A") == text.count("A")
        assert any(q + "A" in out for q in "\"'‘“"), out


def test_quoted_capital_a_same_as_other_letters():
    a = strip_articles('Mark it "A" now.')
    b = strip_articles('Mark it "B" now.')
    assert a.replace("A", "B") == b


def test_quoted_lowercase_article_still_unwrapped():
    assert strip_articles('Say "the" twice.') == "Say the twice."
    assert strip_articles("Say “a” once.") == "Say a once."
