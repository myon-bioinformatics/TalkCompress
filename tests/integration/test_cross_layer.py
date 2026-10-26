"""結合・総合: pipeline / compare / layer ownership across C→E.

Not DispatchHub unit tests — D is only the provisional router under test as wiring.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests._helpers import load, ns  # noqa: E402


def test_pipeline_c_then_e():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    text = "um thank you for your information"
    out = c.run_pipeline(["C", "E"], text, ns())
    assert "um" not in out.lower()
    from shared.lex_policy import INFO_GLYPH

    assert "FYI" in out or "ty" in out.lower() or INFO_GLYPH in out
    assert len(out) < len(text)


def test_pipeline_a_without_key_errors():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    try:
        c.run_pipeline(["A", "C"], "hi", ns(key=None))
        raised = False
    except SystemExit as e:
        raised = True
        assert "key" in str(e).lower()
    assert raised


def test_parse_pipeline():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    assert c.parse_pipeline("C,E") == ["C", "E"]
    assert c.parse_pipeline("3,4") == ["C", "E"]
    assert c.parse_pipeline("shorthand,morpho") == ["C", "E"]


def test_pipeline_c_e_classic_three_animals():
    from shared.lex_policy import INFO_GLYPH

    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    classic = "um 私は will find out the information about three animals"
    pipe = c.run_pipeline(["C", "E"], classic, ns())
    assert "um" not in pipe.lower()
    assert "ascrt" in pipe.lower()
    assert "I'll" in pipe
    assert INFO_GLYPH in pipe
    assert "3匹" in pipe


def test_layer_ownership_matrix_c_then_e_pipe():
    """Alsoぎ: C→E pipe for classic example (C/E alone covered in layer tests)."""
    from shared.lex_policy import INFO_GLYPH

    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    classic = "um 私は will find out the information about three animals"
    pipe = c.run_pipeline(["C", "E"], classic, ns())
    assert "um" not in pipe.lower()
    assert "ascrt" in pipe.lower()
    assert "3匹" in pipe
    assert INFO_GLYPH in pipe
    assert "I'll" in pipe


def test_classic_matrix_pipe_with_ledger():
    from shared.lex_policy import INFO_GLYPH

    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    classic = "um 私は will find out the information about three animals"
    pipe = c.run_pipeline(["C", "E"], classic, ns())
    assert "um" not in pipe.lower()
    assert "ascrt" in pipe.lower()
    assert "3匹" in pipe
    assert INFO_GLYPH in pipe
    assert "I'll" in pipe
    assert pipe == "I'll ascrt ℹ️ about 3匹" or (
        "I'll" in pipe and "ascrt" in pipe.lower() and INFO_GLYPH in pipe and "3匹" in pipe
    )


def test_compare_json_shape():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    rows = c.compare_layers("thank you for your information about 3 animals", ns())
    assert len(rows) >= 3
    for row in rows:
        assert "layer" in row
        assert "chars_before" in row
        assert "chars_after" in row
        assert "ratio" in row
        assert isinstance(row["ratio"], float)
    layers = {r["layer"] for r in rows}
    assert "C" in layers
    assert "E" in layers
    assert "C,E" in layers


def test_convo_pipeline_cli():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        rc = c.main(["--pipeline", "C,E", "--text", "um thank you"])
        assert rc == 0
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert "um" not in out.lower()
    assert len(out.strip()) > 0


def test_convo_compare_cli():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        rc = c.main(["--compare", "--text", "as soon as possible please"])
        assert rc == 0
    finally:
        sys.stdout = old
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) >= 3
    for ln in lines:
        obj = json.loads(ln)
        assert "ratio" in obj


def test_trace_shape():
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    trace: list = []
    c.run_pipeline(["C", "E"], "um thank you for your information", ns(), trace=trace)
    assert len(trace) == 2
    for step in trace:
        assert "step" in step
        assert "layer" in step
        assert "chars_before" in step
        assert "chars_after" in step
        assert "sample_delta" in step
    assert trace[0]["layer"] == "C"
    assert trace[1]["layer"] == "E"


def test_trace_cli(capsys):
    c = load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    rc = c.main(["--pipeline", "C,E", "--trace", "--text", "um thank you"])
    assert rc == 0
    err = capsys.readouterr().err
    obj = json.loads(err.strip().splitlines()[-1])
    assert "trace" in obj
    assert len(obj["trace"]) >= 1
