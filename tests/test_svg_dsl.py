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


@pytest.mark.parametrize("path", [
    "M", "m", "M Z", "M0 0 L", "M0 0 C L1 2", "M0 0 H Z",
    "M0 0 V", "M0 0 S", "M0 0 Q", "M0 0 T", "M0 0 m",
    "M0 0 L1 2 3", "M0 0 C1 2 3 4 5", "M0 0 Z 1 2",
])
def test_every_path_command_requires_a_complete_first_argument_group(path):
    source = wrap(f'<path d="{path}"/>')
    result = analyze(source)
    assert not result.ok
    assert result.canonical is None
    with pytest.raises(SvgDslError):
        canonicalize(source)


@pytest.mark.parametrize("path", [
    "M0 0", "m0 0 1 2 3 4", "M0 0 Z", "M0 0 Z L1 2 Z",
    "M0 0 M1 2", "M0 0 L1 2 3 4", "M0 0 H1 2 V3 4",
    "M0 0 C1 2 3 4 5 6 7 8 9 10 11 12",
    "M0 0 S1 2 3 4 Q5 6 7 8 T9 10 11 12 Z",
])
def test_complete_and_implicit_path_groups_remain_valid(path):
    source = wrap(f'<path d="{path}"/>')
    assert analyze(source).ok
    assert is_idempotent(source)


@pytest.mark.parametrize("raw, expected", [
    ("1e50", "1" + "0" * 50), ("-1e50", "-1" + "0" * 50),
    ("1e-1000000", "0"), ("-1e-1000000", "0"),
    ("0e1000000", "0"), ("-0e1000000", "0"),
    ("0.005", "0"), ("0.015", "0.02"), ("-0.015", "-0.02"),
    ("9.995", "10"), ("1e1023", "1" + "0" * 1023),
])
def test_numbers_have_bounded_context_independent_expansion(raw, expected):
    assert fmt_num(raw) == expected
    assert fmt_num(expected) == expected


def test_number_rounding_does_not_inherit_precision_or_rounding_traps():
    from decimal import Inexact, ROUND_UP, Rounded, localcontext

    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert fmt_num("1.005") == "1"
        assert fmt_num("1.015") == "1.02"
        assert fmt_num("1e50") == "1" + "0" * 50
        assert analyze(wrap('<circle cx="1e50"/>')).ok


@pytest.mark.parametrize("raw", [
    "1e1024", "-1e1024", "1e1000000", "-1e1000000",
    "1e9999999999999999999999999999999999999999999",
    "9" * 1024 + ".995", "NaN", "sNaN", "Infinity", "-Infinity",
])
def test_extreme_or_nonfinite_numbers_return_dsl_errors(raw):
    with pytest.raises(SvgDslError):
        fmt_num(raw)
    result = analyze(wrap(f'<circle cx="{raw}"/>'))
    assert not result.ok
    assert result.canonical is None
    assert result.errors


@pytest.mark.parametrize("attribute", ["width", "height"])
def test_root_dimensions_reject_huge_exponent_before_integer_expansion(attribute):
    attrs = {"width": "8", "height": "8", "viewBox": "0 0 8 8"}
    attrs[attribute] = "1e1000000"
    source = "<svg " + " ".join(f'{key}="{value}"' for key, value in attrs.items()) + "/>"
    result = analyze(source)
    assert not result.ok
    assert any(attribute in error for error in result.errors)


def test_large_bounded_root_dimensions_canonicalize_without_decimal_exception():
    width = "1" + "0" * 50
    source = f'<svg width="1e50" height="8" viewBox="0 0 {width} 8"/>'
    result = analyze(source)
    assert result.ok
    assert f'width="{width}"' in result.canonical
    assert is_idempotent(source)


def test_optional_shape_coordinates_stay_legal_svg_defaults():
    source = wrap('<circle r="20"/><rect width="10" height="8"/><line x2="10"/>')
    assert analyze(source).ok
    assert is_idempotent(source)
