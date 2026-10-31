"""Density's stdout and --out agree after Shorthand preserves line endings."""
from __future__ import annotations

import json
import os
import pytest

from DensityZip import density_zip as dz


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
