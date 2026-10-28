"""Layer modules are executed once per pytest process."""

from __future__ import annotations

import sys

from tests._helpers import load


def test_load_returns_same_module_object():
    a = load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    b = load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    assert a is b
    assert sys.modules["zipilogue_rulebook"] is a


def test_density_layer_loader_reuses_morpho_zip():
    first = load("morpho_zip", "MorphoZip/morpho_zip.py")
    density = load("density_zip", "DensityZip/density_zip.py")
    again = density._load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert again is first
    assert load("morpho_zip", "MorphoZip/morpho_zip.py") is first
