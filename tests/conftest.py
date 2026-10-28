"""Shared pytest hooks for TalkCompress tests."""

from __future__ import annotations


def pytest_addoption(parser):
    group = parser.getgroup("pd-corpus")
    group.addoption(
        "--pd-seed",
        action="store",
        type=int,
        default=42,
        help="RNG seed for PD corpus random smoke (default: 42)",
    )
    group.addoption(
        "--pd-n",
        action="store",
        type=int,
        default=5,
        help="Number of PD passages to sample per smoke test (default: 5)",
    )
