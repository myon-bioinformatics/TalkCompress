"""--final-zh-de must not turn a non-compress --mode into compress (DensityZip)."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("density_zip_mode_final", ROOT / "DensityZip" / "density_zip.py")
dz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dz)


def _run(capsys, *argv: str) -> tuple[str, str]:
    assert dz.main(list(argv)) == 0
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
    assert _run(capsys, *argv, "--final-zh-de")[0] == _run(capsys, *argv)[0]


def test_final_flag_still_appended_on_compress(capsys):
    _, err = _run(capsys, "--layer", "C", "--final-zh-de", "--trace", "--text", "für die Bürger")
    layers = [t["layer"] for t in json.loads(err.strip().splitlines()[-1])["trace"]]
    assert layers == ["C", dz.FINAL_ZH_DE_STEP]


def test_final_flag_still_appended_on_encode(capsys):
    _, err = _run(capsys, "--layer", "A", "--key", "k" * 32, "--final-zh-de", "--trace", "--text", "hello")
    layers = [t["layer"] for t in json.loads(err.strip().splitlines()[-1])["trace"]]
    assert layers == ["A", dz.FINAL_ZH_DE_STEP]
