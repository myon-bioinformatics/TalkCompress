"""Offline guards against uv replacing the selected CI matrix interpreter."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import sys

import pytest

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


SVG_WORKFLOW = WORKFLOW.with_name('svg-l3.yml')


def _svg_job_steps(job_name):
    text = SVG_WORKFLOW.read_text()
    job = re.search(rf'(?ms)^  {job_name}:\n(.*?)(?=^  \S|\Z)', text).group(1)
    return re.split(r'(?m)^      - ', job)[1:]


def _assert_svg_python_setup(steps):
    setup_indexes = [i for i, step in enumerate(steps) if step.startswith('uses: astral-sh/setup-uv@')]
    assert len(setup_indexes) == 1
    setup_index = setup_indexes[0]
    setup = steps[setup_index]
    for setting in (
        'uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3',
        'version: "0.13.3"', 'python-version: "3.12.15"',
        'activate-environment: true', 'enable-cache: false',
    ):
        assert setting in setup
    python_steps = [i for i, step in enumerate(steps)
                    if '\n        run:' in step and
                    re.search(r'\bpython(?:3)?\b', step.split('\n        run:', 1)[1])]
    assert python_steps
    assert all(setup_index < i for i in python_steps)


@pytest.mark.parametrize('job_name', ['plan', 'l3'])
def test_svg_python_is_pinned_and_activated_before_every_call(job_name):
    _assert_svg_python_setup(_svg_job_steps(job_name))


@pytest.mark.parametrize('job_name', ['plan', 'l3'])
def test_svg_setup_guard_rejects_missing_or_late_setup(job_name):
    steps = _svg_job_steps(job_name)
    setup = next(step for step in steps if step.startswith('uses: astral-sh/setup-uv@'))
    without_setup = [step for step in steps if step is not setup]
    for invalid in (without_setup, without_setup + [setup]):
        with pytest.raises(AssertionError):
            _assert_svg_python_setup(invalid)


def test_svg_model_workflow_stays_manual_only():
    events = SVG_WORKFLOW.read_text().split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
    assert re.findall(r'^  ([\w]+):', events, re.MULTILINE) == ['workflow_dispatch']
