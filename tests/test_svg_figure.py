import json
from pathlib import Path

import pytest

from shared.svg_dsl import analyze, canonicalize
from shared.svg_figure import _boundary, build

EXAMPLES = sorted(Path(__file__).resolve().parents[1].joinpath("examples/figures").glob("*.json"))


@pytest.mark.parametrize("spec_path", EXAMPLES, ids=lambda p: p.stem)
def test_example_figure_is_valid_dsl_and_idempotent(spec_path):
    svg = build(json.loads(spec_path.read_text(encoding="utf-8")))
    result = analyze(svg)
    assert result.ok, result.errors
    assert canonicalize(result.canonical) == result.canonical


def test_example_svg_files_match_their_specs():
    for spec_path in EXAMPLES:
        expected = build(json.loads(spec_path.read_text(encoding="utf-8")))
        assert spec_path.with_suffix(".svg").read_text(encoding="utf-8") == expected, spec_path.name


def test_edge_leaves_the_box_boundary_not_the_center():
    box = {"x": 60, "y": 80, "w": 80, "h": 40}  # center (100, 100)
    assert _boundary(box, (300, 100)) == (140, 100)  # right edge
    assert _boundary(box, (100, 300)) == (100, 120)  # bottom edge


def test_unknown_edge_mode_is_rejected():
    spec = {"items": [
        {"type": "box", "id": "a", "x": 0, "y": 0, "w": 40, "h": 40},
        {"type": "box", "id": "b", "x": 80, "y": 0, "w": 40, "h": 40},
        {"type": "edge", "from": "a", "to": "b", "mode": "curve"}]}
    with pytest.raises(ValueError):
        build(spec)


def test_chart_writes_tick_labels_and_escaped_text():
    spec = {"items": [
        {"type": "chart", "box": [96, 40, 600, 400],
         "x": {"min": 0, "max": 10, "ticks": [0, 5, 10]},
         "y": {"min": 0, "max": 1, "ticks": [0, 0.5, 1]},
         "series": [{"points": [[0, 0], [10, 1]]}], "labels": {"x": "A & B"}}]}
    svg = build(spec)
    for label in ("0.5", "5", "A &amp; B"):
        assert label in svg
    assert analyze(svg).ok


def test_l2_renders_example_figure_when_chromium_present():
    pytest.importorskip("playwright.sync_api")
    from shared.svg_render import Renderer, l2_check
    try:
        r = Renderer()
    except Exception as exc:
        pytest.skip(f"chromium unavailable: {exc}")
    try:
        report = l2_check(build(json.loads(EXAMPLES[0].read_text(encoding="utf-8"))), r)
        assert report["ok"]
    finally:
        r.close()
