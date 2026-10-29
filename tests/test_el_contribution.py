"""Smoke for scripts/el_contribution.py (deterministic, read-only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_el_contribution_smoke():
    spec = importlib.util.spec_from_file_location("el_contribution", ROOT / "scripts/el_contribution.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.measure()
    assert r["lines"] > 0
    assert r["with_el"]["tokens"] <= r["src"]["tokens"]
    assert r["with_el"]["tokens"] <= r["no_el"]["tokens"]
    ids = {f["id"] for f in r["bank_flips"]}
    # o200k: "I will take" -> tomaré (2 = 2 with πάρω, fewer bytes) so only find flips to el
    assert "find-fut-1s" in ids
    assert mod.measure() == r
