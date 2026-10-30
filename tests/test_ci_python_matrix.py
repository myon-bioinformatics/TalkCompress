"""Offline guards against uv replacing the selected CI matrix interpreter."""
from pathlib import Path
import os
import shlex
import subprocess
import sys

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/ci.yml'


def test_uv_python_is_bound_to_matrix_for_test_job():
    text = WORKFLOW.read_text()
    test_job = text.split('\n  test:\n', 1)[1].split('\n  failure-identity:', 1)[0]
    assert '\n    env:\n' in test_job
    assert '\n      UV_PYTHON: ${{ matrix.python-version }}\n' in test_job
    assert 'uv sync --locked --python "$(python -c' in test_job
    assert 'uv run --locked python -m pytest -q' in test_job
    assert 'uv run --locked pytest ' not in test_job
    assert 'pytest-${{ matrix.python-version }}.xml' in test_job


def _runtime_assertion():
    lines = WORKFLOW.read_text().splitlines()
    command = next(line.strip() for line in lines if line.strip().startswith('uv run --locked python -c '))
    argv = shlex.split(command)
    assert argv[:5] == ['uv', 'run', '--locked', 'python', '-c']
    assert len(argv) == 6
    return argv[-1]


def test_runtime_guard_accepts_actual_interpreter():
    result = subprocess.run([sys.executable, '-c', _runtime_assertion()],
                            env={**os.environ, 'UV_PYTHON': f'{sys.version_info.major}.{sys.version_info.minor}'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert sys.executable in result.stdout


def test_runtime_guard_rejects_mislabeled_interpreter():
    wrong_minor = sys.version_info.minor + 1
    result = subprocess.run([sys.executable, '-c', _runtime_assertion()],
                            env={**os.environ, 'UV_PYTHON': f'{sys.version_info.major}.{wrong_minor}'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'AssertionError' in result.stderr
