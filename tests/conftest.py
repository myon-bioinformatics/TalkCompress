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


def pytest_terminal_summary(terminalreporter):
    """Report stdlib estimate_tokens vs o200k_base agreement in every CI run
    (yardstick for eventually dropping the tiktoken dev dependency)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        import tokenizer_compat as tc

        r = tc.agreement()
    except Exception as e:  # report-only: never fail the run here
        terminalreporter.write_line(f"token agreement: unavailable ({type(e).__name__}: {e})")
        return
    terminalreporter.section("token agreement (stdlib vs o200k_base, report-only)")
    terminalreporter.write_line(
        f"sample exact {r['sample_exact']}/{r['sample_n']}, matrix exact {r['matrix_exact']}/{r['matrix_n']}, "
        f"winner flips {r['winner_flips']}/{r['cells_judged']}"
    )
