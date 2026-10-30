import pytest

from shared.svg_dsl import SvgDslError, analyze, canonicalize, fmt_num, is_idempotent

HEAD = 'xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"'

SAMPLE = f"""<?xml version="1.0"?>
<svg {HEAD}>
  <!-- a comment is dropped -->
  <rect x="8" y="8" width="240" height="240" fill="none" stroke="#000" stroke-width="2"/>
  <circle cx="128" cy="128" r="40" fill="#FFF" stroke="#abc"/>
  <path d="M10,20L30 40 Z" stroke="#000000"/>
  <text x="16" y="32" font-family="Noto Sans CJK JP, sans-serif" font-size="12">千ヶ谷 &amp; 図</text>
</svg>
"""

EXPECTED = """<svg height="256" viewBox="0 0 256 256" width="256" xmlns="http://www.w3.org/2000/svg">
  <rect fill="none" height="240" stroke="#000000" stroke-width="2" width="240" x="8" y="8"/>
  <circle cx="128" cy="128" fill="#ffffff" r="40" stroke="#aabbcc"/>
  <path d="M 10 20 L 30 40 Z" stroke="#000000"/>
  <text font-family="Noto Sans CJK JP, sans-serif" font-size="12" x="16" y="32">千ヶ谷 &amp; 図</text>
</svg>
"""


def wrap(body: str, head: str = HEAD) -> str:
    return f"<svg {head}>{body}</svg>"


def test_sample_gives_fixed_canonical_text():
    assert canonicalize(SAMPLE) == EXPECTED


def test_canonical_is_idempotent():
    assert is_idempotent(SAMPLE)
    assert canonicalize(EXPECTED) == EXPECTED


def test_attribute_order_does_not_change_output():
    a = wrap('<rect x="1" y="2" width="3" height="4"/>')
    b = wrap('<rect height="4" width="3" y="2" x="1"/>')
    assert canonicalize(a) == canonicalize(b)


def test_color_is_lowercase_six_digit():
    out = canonicalize(wrap('<rect x="0" y="0" width="8" height="8" fill="#ABC" stroke="none"/>'))
    assert 'fill="#aabbcc"' in out
    assert 'stroke="none"' in out


@pytest.mark.parametrize(
    "raw, expected",
    [("0.10", "0.1"), ("2.50", "2.5"), ("-0.001", "0"), ("10.0", "10"), ("1.005", "1"), ("3", "3")],
)
def test_numbers_rounded_and_trimmed(raw, expected):
    assert fmt_num(raw) == expected


def test_path_separators_and_spacing_are_normalized():
    out = canonicalize(wrap('<path d="M10,20L30 40 Z" stroke="#000"/>'))
    assert 'd="M 10 20 L 30 40 Z"' in out


def test_implicit_lineto_after_moveto_is_kept_as_numbers():
    out = canonicalize(wrap('<path d="M0 0 10 10 20 20" stroke="#000"/>'))
    assert 'd="M 0 0 10 10 20 20"' in out


def test_text_is_nfc_and_whitespace_collapsed():
    decomposed = "が"  # が as base + combining voiced mark
    out = canonicalize(wrap(f'<text x="0" y="8" font-family="Noto Sans CJK JP">{decomposed}   図\n 表</text>'))
    assert "が 図 表" in out


def test_text_special_characters_escaped():
    out = canonicalize(wrap('<text x="0" y="8" font-family="Noto Sans CJK JP">a &lt; b &amp; c</text>'))
    assert "a &lt; b &amp; c" in out


def test_missing_xmlns_is_added_on_output():
    src = '<svg width="8" height="8" viewBox="0 0 8 8"><rect x="0" y="0" width="8" height="8"/></svg>'
    assert canonicalize(src).startswith('<svg height="8" viewBox="0 0 8 8" width="8" xmlns="http://www.w3.org/2000/svg">')


@pytest.mark.parametrize(
    "body",
    [
        '<script>alert(1)</script>',
        '<foreignObject x="0" y="0" width="8" height="8"/>',
        '<image x="0" y="0" width="8" height="8" href="a.png"/>',
        '<use href="#a"/>',
        '<rect x="0" y="0" width="8" height="8" transform="rotate(10)"/>',
        '<rect x="0" y="0" width="8" height="8" onclick="x()"/>',
        '<path d="M0 0 A5 5 0 0 1 10 10" stroke="#000"/>',
        '<rect x="0" y="0" width="8" height="8" fill="red"/>',
        '<text x="0" y="8" font-family="Meiryo">x</text>',
        '<text x="0" y="8" font-family="Noto Sans CJK JP"><tspan>x</tspan></text>',
        '<x:foo xmlns:x="urn:example"/>',
    ],
)
def test_rejects_out_of_scope_content(body):
    head = 'xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8"'
    result = analyze(wrap(body, head))
    assert not result.ok
    with pytest.raises(SvgDslError):
        canonicalize(wrap(body, head))


def test_rejects_doctype():
    assert not analyze('<!DOCTYPE svg><svg width="8" height="8" viewBox="0 0 8 8"/>').ok


def test_rejects_viewbox_mismatch():
    result = analyze('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 16 16"/>')
    assert not result.ok
    assert any("viewBox" in e for e in result.errors)


def test_size_not_multiple_of_8_is_warning_only():
    src = '<svg xmlns="http://www.w3.org/2000/svg" width="250" height="250" viewBox="0 0 250 250"/>'
    result = analyze(src)
    assert result.ok
    assert result.warnings and "multiple of 8" in result.warnings[0]


def test_bad_path_reports_error_not_exception():
    result = analyze(wrap('<path d="M 10 20 L 30" stroke="#000"/>'))
    assert not result.ok


def test_decimal_coordinates_are_allowed_and_rounded():
    out = canonicalize(wrap('<rect x="0.125" y="1.5" width="10.5" height="8" fill="none"/>'))
    assert 'x="0.12"' in out
    assert 'width="10.5"' in out


def test_root_size_must_be_integer():
    result = analyze('<svg xmlns="http://www.w3.org/2000/svg" width="10.5" height="8" viewBox="0 0 10.5 8"/>')
    assert not result.ok
