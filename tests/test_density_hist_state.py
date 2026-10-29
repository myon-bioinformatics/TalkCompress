from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "window_chat.jsonl"


def _run(*extra: str) -> list[dict]:
    cmd = [
        sys.executable,
        str(ROOT / "DensityZip" / "density_zip.py"),
        "--pipeline",
        "C,E",
        "--jsonl",
        "--keep-system",
        "--file",
        str(SAMPLE),
        *extra,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=ROOT).stdout
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


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
