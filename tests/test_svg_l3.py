from shared.svg_dsl import canonicalize
from shared.svg_l3 import extract_svg, probes_from, run

SRC = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="20" fill="#f00" stroke="#000" stroke-width="2"/>
  <rect x="8" y="8" width="16" height="12" fill="none" stroke="#0a0"/>
  <line x1="0" y1="60" x2="64" y2="60" stroke="#000"/>
  <text x="32" y="36" text-anchor="middle" font-family="Noto Sans CJK JP" font-size="8">図</text>
</svg>"""


def test_extract_svg_from_fenced_answer():
    text = "Here:\n```svg\n<svg width=\"8\" height=\"8\" viewBox=\"0 0 8 8\"/>\n```"
    assert extract_svg(text).startswith("<svg") and extract_svg(text).endswith("/>")


def test_extract_svg_returns_empty_when_absent():
    assert extract_svg("no drawing here") == ""


def test_probes_take_expected_values_from_original():
    probes = probes_from(canonicalize(SRC))
    expected = {p.expected for p in probes}
    assert {"20", "16", "64", "図", "#ff0000", "#000000", "#00aa00"} <= expected


def test_perfect_generation_with_context_copy_answerer_scores_full():
    # The model "writes" the original back, and the answerer copies its context.
    def ask(prompt):
        if prompt.startswith("Below is an SVG drawing"):
            return "a circle, a rectangle, a line and a text"
        if "Output the SVG only" in prompt:
            return "```svg\n" + SRC + "\n```"
        return prompt  # echoing the context answers every probe
    report = run(SRC, ask)
    assert report["dsl_ok"]
    assert report["score"] == 1.0


def test_invalid_generation_fails_at_validation():
    def ask(prompt):
        if "Output the SVG only" in prompt:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8"><script/></svg>'
        return "x"
    report = run(SRC, ask)
    assert not report["dsl_ok"]
    assert report["errors"]


def test_unanswered_probes_score_zero():
    def ask(prompt):
        if "Output the SVG only" in prompt:
            return SRC
        if "Context:" in prompt:
            raise RuntimeError("model command failed (1)")
        return "some description"
    report = run(SRC, ask)
    assert report["dsl_ok"]
    assert report["score"] == 0.0
