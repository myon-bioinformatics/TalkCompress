"""Regression: EN `you` never takes de ihr / nl jullie (plural) forms."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
ENTRIES = BANK["entries"]
BY_SRC = {e["from"][0]: e for e in ENTRIES}
NL_PLURAL = {"deden", "hadden", "wisten", "gingen", "kwamen", "zagen", "namen", "vonden",
             "wilden", "dachten", "zeiden", "gaven"}


def test_you_think_is_singular_not_de_ihr():
    e = BY_SRC["you think"]
    # de ihr `denkt` is gone; the surviving `denkt` is nl jij (singular), not de.
    assert not (e["lang"] == "de" and e["to"] == "denkt")
    assert all(c["form"] != "denkt" or c["lang"] == "nl" for c in e["candidates"])


@pytest.mark.parametrize("src", ["you have done", "you have had", "you have known"])
def test_nl_plural_rejected_for_you(src):
    e = BY_SRC.get(src)
    if e is not None:
        assert e["to"] not in {"deden", "hadden", "wisten"}


def test_no_nl_plural_for_any_you_cell():
    for e in ENTRIES:
        if e.get("subject") == "2":
            for c in e["candidates"]:
                assert not (c["lang"] == "nl" and c["form"] in NL_PLURAL), e["id"]
