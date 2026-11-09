"""Layer modules are executed once per pytest process."""

from __future__ import annotations

import sys

from tests._helpers import load


def test_load_returns_same_module_object():
    a = load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    b = load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    assert a is b
    assert sys.modules["rule_peer_codec_rulebook"] is a


def test_density_layer_loader_reuses_morpho_grammar_minimal():
    first = load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    density = load("density_facade_route", "DensityFacadeRoute/density_facade_route.py")
    again = density._load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert again is first
    assert load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py") is first
