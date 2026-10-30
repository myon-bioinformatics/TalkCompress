from shared.svg_dsl import canonicalize
import json

import pytest

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


def test_extract_svg_excludes_reasoning_only_generation():
    assert extract_svg("<think>" + SRC + "</think>No final drawing.") == ""
    assert extract_svg("<think>" + SRC) == ""
    assert extract_svg("<think>reasoning</think>```svg\n" + SRC + "\n```") == SRC
    assert extract_svg("Some thoughts: <think>" + SRC) == ""
    assert extract_svg("```text\n<think>" + SRC + "\n```") == ""
    assert extract_svg(SRC + "</think>No final drawing") == ""
    assert extract_svg("prefix<think>" + SRC + "</think>" + SRC) == SRC


def test_extract_svg_preserves_literal_reasoning_tags_inside_cdata():
    source = '<svg width="64" height="64" viewBox="0 0 64 64"><text><![CDATA[<think>literal</think>]]></text></svg>'
    assert extract_svg(source) == source
    assert extract_svg("Here:\n```svg\n" + source + "\n```") == source


@pytest.mark.parametrize("stage", ["describe", "generate"])
def test_unfinished_generation_stages_are_recorded_without_scoring(stage):
    calls = []
    def ask(prompt):
        calls.append(prompt)
        if stage == "describe" or "Output the SVG only" in prompt:
            raise RuntimeError("unfinished output")
        return "description"
    report = run(SRC, ask)
    assert report["status"] == "incomplete" and not report["dsl_ok"]
    assert report["hits"] == 0 and report["errors"][0].startswith(stage + ":")
    assert len(calls) == (1 if stage == "describe" else 2)


def test_probes_take_expected_values_from_original():
    probes = probes_from(canonicalize(SRC))
    expected = {p.expected for p in probes}
    assert {"20", "16", "64", "図", "#ff0000", "#000000", "#00aa00"} <= expected


def test_perfect_generation_with_typed_answers_scores_full():
    def ask(prompt):
        if prompt.startswith("Below is an SVG drawing"):
            return "a circle, a rectangle, a line and a text"
        if "Output the SVG only" in prompt:
            return "```svg\n" + SRC + "\n```"
        if "radius of every circle" in prompt:
            return "[20]"
        if "width of every rect" in prompt:
            return "[16]"
        if "x2 coordinate of every line" in prompt:
            return "[64]"
        if "text content of every" in prompt:
            return '["図"]'
        return '["#ff0000", "#000000", "#00aa00"]'
    report = run(SRC, ask)
    assert report["dsl_ok"]
    assert report["score"] == 1.0


def wrap(body):
    return '<svg width="64" height="64" viewBox="0 0 64 64">' + body + '</svg>'


def answerer(svg, answer):
    def ask(prompt):
        if prompt.startswith("Below is an SVG drawing"):
            return "description"
        if "Output the SVG only" in prompt:
            return svg
        return answer(prompt) if callable(answer) else answer
    return ask


def test_original_coordinates_cannot_leak_expected_radius_in_question():
    source = wrap('<circle cx="20" cy="30" r="20"/>')
    wrong = wrap('<circle cx="20" cy="30" r="1"/>')
    probe = probes_from(canonicalize(source))[0]
    assert "20" not in probe.question and "30" not in probe.question
    report = run(source, answerer(wrong, lambda prompt: prompt.split("Question: ")[1]))
    assert report["score"] == 0
    assert report["results"][0]["status"] == "unscorable"
    assert run(source, answerer(wrong, "[1]"))["score"] == 0


def test_context_echo_is_not_a_completed_typed_answer():
    report = run(SRC, answerer(SRC, lambda prompt: prompt))
    assert report["score"] == 0
    assert report["unscorable"] == report["total"]


@pytest.mark.parametrize("body, expected", [
    ('<circle r="20"/>', "20"), ('<circle/>', "0"),
    ('<rect width="12" height="8"/>', "12"), ('<rect/>', "0"),
    ('<line x2="12"/>', "12"), ('<line/>', "0"),
])
def test_svg_default_attributes_do_not_crash_probes_or_pipeline(body, expected):
    source = wrap(body)
    probe = probes_from(canonicalize(source))[0]
    assert probe.expected == expected
    report = run(source, answerer(source, f"[{expected}]"))
    assert report["dsl_ok"] and report["score"] == 1


@pytest.mark.parametrize("answer", [
    "20", '"20"', '["20"]', "[true]", "[null]", "[NaN]", "[Infinity]",
    "[-Infinity]", "[[20]]", '{"value":20}', "[20,20]", "[]", "[20] [20]",
    "[20] trailing text", "The answer is [20]", "```json\n[20]\n```", "[20",
    "<think>[20]</think>", "<think>[20]", "",
    "[1e9999999999999999999999999999999999999999]",
])
def test_malformed_partial_or_non_numeric_answers_do_not_score(answer):
    source = wrap('<circle r="20"/>')
    report = run(source, answerer(source, answer))
    assert report["score"] == 0
    assert report["unscorable"] == 1
    assert report["status"] == "incomplete"


def test_only_completed_final_json_is_scored():
    source = wrap('<circle r="20"/>')
    assert run(source, answerer(source, '<think>[20]</think>[1]'))["score"] == 0
    assert run(source, answerer(source, '<think>[1]</think>[20]'))["score"] == 1
    assert run(source, answerer(source, '<think>nested<think>[1]</think></think>[20]'))["score"] == 1
    assert run(source, answerer(source, 'template reasoning</think>[20]'))["score"] == 1


def test_reasoning_tags_inside_json_strings_are_literal_svg_text():
    source = wrap('<text>correct</text>')
    answer = '["<think>wrong</think>correct"]'
    report = run(source, answerer(source, answer))
    assert report["score"] == 0
    assert report["results"][0]["answer"] == answer
    literal = wrap('<text>&lt;think&gt;literal&lt;/think&gt;</text>')
    assert run(literal, answerer(literal, '["<think>literal</think>"]'))["score"] == 1
    assert run(literal, answerer(literal, '<think>reasoning</think>["<think>literal</think>"]'))["score"] == 1


def test_duplicates_are_scored_by_position_with_one_answer_per_attribute():
    source = wrap('<circle r="20"/><circle r="20"/><circle r="7"/>')
    calls = []
    def reply(prompt):
        calls.append(prompt)
        return "[20,7,20]"
    report = run(source, answerer(source, reply))
    assert report["hits"] == 1 and report["total"] == 3
    assert len(calls) == 1
    assert run(source, answerer(source, "[20,20,7]"))["score"] == 1


def test_numeric_json_values_compare_without_rounding_answers():
    source = wrap('<circle r="0.1"/>')
    assert run(source, answerer(source, "[1e-1]"))["score"] == 1
    assert run(source, answerer(source, "[0.10001]"))["score"] == 0


def test_text_values_are_complete_ordered_strings_not_substrings():
    source = wrap('<text>item</text><text>item</text><text>last</text>')
    assert run(source, answerer(source, '["item", "item", "last"]'))["score"] == 1
    assert run(source, answerer(source, '["item plus", "last", "item"]'))["score"] == 0


def test_unfinished_marker_is_not_a_magic_correct_text_answer():
    source = wrap('<text>&lt;&lt;unfinished&gt;&gt;</text>')
    def fail(prompt):
        raise RuntimeError("unfinished output")
    report = run(source, answerer(source, fail))
    assert report["score"] == 0 and report["unscorable"] == 1


def test_explicit_colors_are_unordered_but_must_be_unique_and_typed():
    source = wrap('<g fill="#f00"><circle r="2" stroke="#abc"/></g>')
    def reply(prompt):
        return "[2]" if "radius of every" in prompt else '["#aabbcc", "#ff0000"]'
    assert run(source, answerer(source, reply))["score"] == 1
    for colors in ['["#ff0000","#ff0000"]', '["#ff0000",123]', '["#f00","#abc"]']:
        def wrong(prompt):
            return "[2]" if "radius of every" in prompt else colors
        report = run(source, answerer(source, wrong))
        assert report["hits"] == 1 and report["unscorable"] == 2


def test_empty_drawing_has_no_applicable_probes():
    source = wrap("")
    report = run(source, answerer(source, lambda prompt: pytest.fail("no probe call expected")))
    assert report["dsl_ok"] and report["score"] is None
    assert report["total"] == 0 and report["status"] == "not_applicable"
    assert report["prompt_version"] == report["scorer_version"] == "2"


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


def test_cli_writes_meta_and_reports(tmp_path):
    import json
    from shared.svg_l3 import main

    fig = tmp_path / "f.svg"
    fig.write_text(SRC, encoding="utf-8")
    out = tmp_path / "report.json"
    # A model that never writes an SVG: the run must finish, record the failure, and exit 1.
    rc = main([str(fig), "--cmd", "python3 -c \"import sys; sys.stdin.read(); print('no svg')\"",
               "--model", "test-model", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 1
    assert data["meta"]["model"] == "test-model"
    assert data["meta"]["stage"] == "L3"
    assert data["reports"][0]["figure"] == "f.svg"
    assert len(data["reports"][0]["source_sha256"]) == 64
    assert data["reports"][0]["dsl_ok"] is False
