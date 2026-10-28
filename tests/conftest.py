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
    mid = parser.getgroup("mid-split")
    mid.addoption(
        "--mid-seed",
        action="store",
        type=int,
        default=99,
        help="RNG seed for mid-split / truncated smoke (default: 99)",
    )
    mid.addoption(
        "--mid-n",
        action="store",
        type=int,
        default=4,
        help="PD passages to sample per mid-split smoke test (default: 4)",
    )
