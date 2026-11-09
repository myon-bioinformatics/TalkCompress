"""dist/*_min.py bundles (docs/distributions.md): header, isolation, rebuild."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_distributions as bd  # noqa: E402

MANIFEST = json.loads((ROOT / "distributions.json").read_text(encoding="utf-8"))
PROJECTS = MANIFEST["projects"]


def _header(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines()[2:16]:
        k, _, v = line[2:].partition(": ")
        out[k.rstrip(":")] = v
    return out


def test_manifest_pins_parent_minpy():
    tool = MANIFEST["tool"]
    assert MANIFEST["schema"] == bd.SCHEMA
    assert tool["repository"] == "myon-bioinformatics/myon-bioinformatics" and tool["source"] == "tools/minpy.py"
    assert re.fullmatch("[0-9a-f]{40}", tool["commit"]) and re.fullmatch("[0-9a-f]{64}", tool["sha256"])
    assert re.fullmatch("[0-9a-f]{40}", MANIFEST["source"])


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_committed_bundle_header_and_self_hash(name):
    item = PROJECTS[name]
    text = (ROOT / item["output"]).read_text(encoding="utf-8")
    h = _header(text)
    assert h["repository"] == bd.REPOSITORY and h["commit"] == MANIFEST["source"]
    assert h["entry"] == item["entry"] and h["python"] == MANIFEST["python"]
    assert h["allow"] == "", "stdlib-only bundle"
    digest = h["content-sha256"]
    zeroed = text.replace("# content-sha256: " + digest, "# content-sha256: " + "0" * 64, 1)
    assert hashlib.sha256(zeroed.encode("utf-8")).hexdigest() == digest, "bundle was edited by hand"


def test_license_shipped():
    assert (ROOT / "dist/LICENSE").read_bytes() == (ROOT / MANIFEST["license"]).read_bytes()


def test_kgraph_bundle_runs_isolated(tmp_path):
    (tmp_path / "kgraph_min.py").write_bytes((ROOT / "dist/kgraph_min.py").read_bytes())
    code = (
        "import sys; sys.path.insert(0, '.')\n"
        "import kgraph_min as k\n"
        "g = k.Graph(); g.add('a','Form'); g.add('b','Form'); g.link('a','follows','b')\n"
        "assert g.traverse('a', ['follows']) == ['b']\n"
        "assert k.dependency_order({'f': {'b'}}) == ['b', 'f']\n"
        "assert k.aggregate([{'l': 'pt', 's': 'pass'}], 'l', 's')['pt']['pass'] == 1\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr


def test_committed_bundles_match_rebuild():
    if MANIFEST["python"] != f"{sys.version_info.major}.{sys.version_info.minor}":
        pytest.skip(f"bundles are generated with Python {MANIFEST['python']} (bytes depend on the minor)")
    try:
        tool = bd.fetch_tool(ROOT, MANIFEST["tool"])
    except OSError as exc:  # offline: the pinned compiler cannot be fetched
        pytest.skip(f"pinned minpy unavailable: {exc}")
    res = bd.build(ROOT, MANIFEST, tool, check=True)
    assert res["ok"] and set(res["files"]) == {"dist/LICENSE", *(p["output"] for p in PROJECTS.values())}


def test_tool_hash_is_checked_before_import(tmp_path):
    fake = tmp_path / "minpy.py"
    fake.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        bd.load_tool(fake, MANIFEST["tool"]["sha256"])
