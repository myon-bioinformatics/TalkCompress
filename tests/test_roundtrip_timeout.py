"""scripts/roundtrip.run: 1 試行のタイムアウトで他の結果を失わない。"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip  # noqa: E402

_SCRIPT = (
    "import os,sys,time\n"
    "sys.stdin.read()\n"
    "if os.environ['ROUNDTRIP_SEED']=='2': time.sleep(30)\n"
    "print('I have eaten.' if os.environ['ROUNDTRIP_SEED']=='1' else 'no')\n"
)


def test_timeout_keeps_other_results() -> None:
    data = {"templates": ["{s}."], "seeds": [1, 2, 3], "records": {}}
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(_SCRIPT)}"
    entries = [{"lang": "nl", "from": ["I have eaten"], "to": "ik at"}]
    out = roundtrip.run(data, cmd, entries=entries, timeout=2)
    rec = out["records"]["nl:ik at"]
    assert rec["trials"] == 2
    assert rec["restored"] == 1
    assert rec["timeouts"] == 1
    assert rec["failures"] == ["Ik at."]
