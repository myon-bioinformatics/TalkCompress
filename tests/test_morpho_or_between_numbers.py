"""MorphoZip: or/oder/ou between two numbers must not turn into a fraction-like "3 / 4"."""
import typing

import pytest

from tests._helpers import load

mz = load("morpho_zip", "MorphoZip/morpho_zip.py")


@pytest.mark.parametrize(
    "src, kept",
    [
        ("He did not say 3 or 4.", "3 or 4"),
        ("Es dauert 2 oder 3 Tage.", "2 oder 3"),
        ("Il faut 2 ou 3 jours.", "2 ou 3"),
    ],
)
def test_conjunction_between_numbers_kept(src, kept):
    out = mz.compress(src)
    assert kept in out
    assert "/" not in out


@pytest.mark.parametrize(
    "src, short",
    [
        ("tea or coffee", "tea / coffee"),
        ("option 3 or later", "3 / later"),
        ("either or 4", "/ 4"),
        ("Tee oder Kaffee", "Tee / Kaffee"),
        ("Seite 3 oder später", "3 / später"),
        ("entweder oder 4", "/ 4"),
        ("page 3 ou plus tard", "3 / plus"),
        ("soit ou 4", "/ 4"),
        ("thé ou café", "thé / café"),
    ],
)
def test_conjunction_still_shortened_elsewhere(src, short):
    out = mz.compress(src)
    assert short in out


def test_protect_rule_hints_resolve():
    # from __future__ annotations: an undefined name only fails when hints are resolved
    hints = typing.get_type_hints(mz._protect_rule)
    assert hints["return"].__args__[1] is typing.Any
