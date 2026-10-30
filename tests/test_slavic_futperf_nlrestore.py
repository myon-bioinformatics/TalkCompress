"""Follow-up to #49: cs/pl stative perfect, future-perfect `you` sg/pl, and the
nl restore rule (a round-trip-gated nl form may come back only when dropping it
costs >= 1 token, never for bytes, and never when its round-trip was measured
as failing)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tm_fu", ROOT / "scripts/tense_matrix.py")
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)
CONJ = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]
REPORT = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]


def test_slavic_stative_perf_has_no_form():
    for verb in ("know", "have", "want"):
        for slot in ("1s", "1p", "2s", "2p"):
            assert tm._slavic(verb, "perf", slot) == []
    assert tm._slavic("find", "perf", "1s")  # non-stative keeps cs/pl perfect


def test_futperf_you_has_no_romance_form():
    for verb in ("know", "do", "go"):
        langs = {c["lang"] for c in tm._candidates(CONJ, "2", "futperf", verb, "")}
        assert not langs & {"es", "pt", "it", "fr"}, verb
    we = {c["lang"] for c in tm._candidates(CONJ, "1p", "futperf", "do", "")}
    assert "fr" in we


def test_futperf_you_cells_stay_english():
    cells = [c for c in REPORT if c["tense"] == "futperf" and c["src"].startswith("you ")]
    assert len(cells) == 12
    assert all(c["status"] != "adopt" for c in cells)


def _tok(f):
    return len(f.split())


def test_restore_nl_needs_a_token_gain():
    nl = {"form": "a", "lang": "nl"}
    de = {"form": "b c", "lang": "de"}
    cell = {}
    cands = tm.restore_nl(cell, [de, nl], [nl], 3, _tok)
    assert cell == {"roundtrip_restored": ["a"]} and nl in cands and de in cands
    # tie on tokens (byte-only difference) -> not restored
    de1 = {"form": "bbbbbbbb", "lang": "de"}
    cell = {}
    assert tm.restore_nl(cell, [de1, nl], [nl], 3, _tok) == [de1] and cell == {}
    # EN floor counts too
    assert tm.restore_nl({}, [nl], [nl], 1, _tok) == []
    assert tm.restore_nl({}, [nl], [nl], 2, _tok) == [nl]


def test_measured_failures_never_restored():
    assert tm._rt_status("ging", "nl") == "never"
    for c in REPORT:
        for f in c.get("roundtrip_restored", []):
            assert tm._rt_status(f, "nl") == "unverified"
