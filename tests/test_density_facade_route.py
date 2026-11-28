"""DensityFacadeRoute (D) CLI: --hist-state、--final-zh-de と --mode、stdout と --out の改行。

- density_hist_state
- density_mode_final_pass: --final-zh-de must not turn a non-compress --mode into compress (DensityFacadeRoute).
- density_output_newlines: Density's stdout and --out agree after Shorthand preserves line endings.
"""

from __future__ import annotations

from DensityFacadeRoute import density_facade_route as dz
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys

import pytest


# ──── density_hist_state ──────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]


def load_vendored(name, relpath):
    """Load a vendored file by path under a repo-unique name (cli_args README: Loading a vendored copy)."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / relpath)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


_cli_args = load_vendored("talkcompress_cli_args", "vendor/cli_args.py")
Command = _cli_args.Command
run_command = _cli_args.run_command


SAMPLE = ROOT / "examples" / "window_chat.jsonl"


def _run(*extra: str) -> list[dict]:
    cmd = [
        sys.executable,
        str(ROOT / "DensityFacadeRoute" / "density_facade_route.py"),
        "--pipeline",
        "C,E",
        "--jsonl",
        "--keep-system",
        "--file",
        str(SAMPLE),
        *extra,
    ]
    result = run_command(Command(cmd), cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]


def test_hist_state_replaces_old_rows_with_one_state_block():
    rows = _run("--window", "2", "--hist-state")
    states = [r for r in rows if r["text"].startswith("[state]")]
    assert len(states) == 1
    assert states[0]["role"] == "system"
    assert len(rows) == 4  # system + state + last 2 rows


def test_without_hist_state_window_only_drops_rows():
    rows = _run("--window", "2")
    assert not any(r["text"].startswith("[state]") for r in rows)
    assert len(rows) == 3  # system + last 2 rows


def test_density_hist_state_keeps_independent_budget(tmp_path):
    from shared.keep_check import check
    source = 'Budget 42; issue #142; https://example.com/a on 2026-10-30 commit abc1234'
    sample = tmp_path / 'chat.jsonl'
    sample.write_text(json.dumps({'role': 'assistant', 'text': source}) + '\n', encoding='utf-8')
    # Isolate history integration from the intentionally lossy text layers.
    rows = _run('--file', str(sample), '--role-layers', 'assistant=identity',
                '--window', '0', '--hist-state')
    state = next(r['text'] for r in rows if r['text'].startswith('[state]'))
    assert check(source, state).ok
    assert '42' in state.split('識別子・数値: ')[1].split('次の一手:')[0].splitlines()


# ──── density_mode_final_pass ─────────────────────────────────────

"""--final-zh-de must not turn a non-compress --mode into compress (DensityFacadeRoute)."""


_spec = importlib.util.spec_from_file_location("density_facade_route_mode_final", ROOT / "DensityFacadeRoute" / "density_facade_route.py")


dz_density_mode_final_pass = importlib.util.module_from_spec(_spec)


_spec.loader.exec_module(dz_density_mode_final_pass)


def _run_density_mode_final_pass(capsys, *argv: str) -> tuple[str, str]:
    assert dz_density_mode_final_pass.main(list(argv)) == 0
    cap = capsys.readouterr()
    return cap.out.rstrip("\n"), cap.err


@pytest.mark.parametrize(
    "argv",
    [
        ("--layer", "C", "--mode", "expand", "--text", "fyi"),
        ("--layer", "E", "--mode", "pack", "--text", "the cats are running"),
        ("--layer", "B", "--mode", "tag", "--text", "hello world"),
    ],
)
def test_final_flag_keeps_mode(capsys, argv):
    assert _run_density_mode_final_pass(capsys, *argv, "--final-zh-de")[0] == _run_density_mode_final_pass(capsys, *argv)[0]


def test_final_flag_still_appended_on_compress(capsys):
    _, err = _run_density_mode_final_pass(capsys, "--layer", "C", "--final-zh-de", "--trace", "--text", "für die Bürger")
    layers = [t["layer"] for t in json.loads(err.strip().splitlines()[-1])["trace"]]
    assert layers == ["C", dz_density_mode_final_pass.FINAL_ZH_DE_STEP]


def test_final_flag_still_appended_on_encode(capsys):
    _, err = _run_density_mode_final_pass(capsys, "--layer", "A", "--key", "k" * 32, "--final-zh-de", "--trace", "--text", "hello")
    layers = [t["layer"] for t in json.loads(err.strip().splitlines()[-1])["trace"]]
    assert layers == ["A", dz_density_mode_final_pass.FINAL_ZH_DE_STEP]


# ──── density_output_newlines ─────────────────────────────────────

"""Density's stdout and --out agree after Shorthand preserves line endings."""


@pytest.mark.parametrize("route", [("--layer", "C"), ("--pipeline", "C")])
@pytest.mark.parametrize("text, expected", [
    ("hello", "hello\n"),
    ("hello\n", "hello\n"),
    ("hello\n\n", "hello\n\n"),
    ("hello\r\n", "hello\r\n"),
    ("", "\n"),
])
def test_density_stdout_matches_file_without_extra_newline(route, text, expected, capsys, tmp_path):
    assert dz.main([*route, "--text", text]) == 0
    assert capsys.readouterr().out == expected
    output = tmp_path / "output.txt"
    assert dz.main([*route, "--text", text, "--out", str(output)]) == 0
    assert capsys.readouterr().out == ""
    # Path.write_text uses native newline translation; keep actual bytes exact.
    assert output.read_bytes() == expected.replace("\n", os.linesep).encode("utf-8")


def test_decode_with_final_flag_preserves_original_task(capsys):
    key = "k" * 32
    assert dz.main(["--layer", "A", "--mode", "encode", "--key", key,
                    "--text", "hello world"]) == 0
    encrypted = capsys.readouterr().out.rstrip("\n")
    assert dz.main(["--layer", "A", "--mode", "decode", "--key", key,
                    "--text", encrypted, "--final-zh-de"]) == 0
    assert capsys.readouterr().out == "hello world\n"


def test_explicit_encode_mode_keeps_requested_final_pass(capsys):
    assert dz.main(["--layer", "A", "--mode", "encode", "--key", "k" * 32,
                    "--text", "hello", "--final-zh-de", "--trace"]) == 0
    trace = json.loads(capsys.readouterr().err.strip().splitlines()[-1])["trace"]
    assert [step["layer"] for step in trace] == ["A", dz.FINAL_ZH_DE_STEP]
