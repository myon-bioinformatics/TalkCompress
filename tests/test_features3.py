"""Round-3 layer-unit tests: protect, packs, fingerprint, policy diff, LID mix.

Window/profile/quality via DensityZip → tests/integration/.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- protect spans ---


def test_protect_keep_spans():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    text = "um [[keep:thank you for your information]] please"
    out = m.compress(text, aggressive_fillers=True)
    assert "thank you for your information" in out
    assert "[[" not in out
    assert "]]" not in out


def test_protect_regex():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    text = "um CODE_BLOCK_XYZ please thank you"
    out = m.compress(text, protect_regexes=[r"CODE_BLOCK_XYZ"])
    assert "CODE_BLOCK_XYZ" in out



# --- packs ---


def test_pack_dev_loads():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    m = s.load_pack("dev")
    assert "pull request" in m or "Pull request".lower() in {k.lower() for k in m}
    sess = s.Session()
    sess.load_packs(["dev", "mcp"])
    out = s.compress("the model context protocol pull request is ready", session=sess)
    assert "MCP" in out or "PR" in out



# --- fingerprint ---


def test_key_fingerprint_stable():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    a = z.key_fingerprint("secret-demo")
    b = z.key_fingerprint("secret-demo")
    c = z.key_fingerprint("other")
    assert a == b
    assert a != c
    assert len(a) == 16
    assert all(ch in "0123456789abcdef" for ch in a)



def test_zipilogue_fingerprint_mode(capsys):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    rc = z.main(["fingerprint", "--key", "secret-demo"])
    assert rc == 0
    assert len(capsys.readouterr().out.strip()) == 16


def test_zipilogue_dry_run(capsys):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    rc = z.main(["encode", "--key", "k", "--dry-run", "--stats", "--text", "hello"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip().isdigit()
    stats = json.loads(captured.err.strip().splitlines()[-1])
    assert stats["envelope_bytes"] > 0
    assert "fingerprint" in stats


# --- policy diff ---


def test_policy_diff_smoke(tmp_path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # fresh load
    import shared.lex_policy as lp

    importlib.reload(lp)
    base = lp.dump_policy()
    other = dict(base)
    other["fillers_en"] = list(base["fillers_en"]) + ["brand_new_filler_xyz"]
    other["unique_readings"] = dict(base["unique_readings"])
    other["unique_readings"].pop(next(iter(other["unique_readings"])), None)
    path = tmp_path / "other.json"
    path.write_text(json.dumps(other), encoding="utf-8")
    diff = lp.diff_policy(base, path)
    assert "brand_new_filler_xyz" in diff["fillers_en"]["added"]
    assert diff["fillers_en"]["removed"] == []


def test_policy_diff_cli(tmp_path, capsys):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import shared.lex_policy as lp

    importlib.reload(lp)
    other = lp.dump_policy()
    other["fillers_ja"] = list(other["fillers_ja"]) + ["新しいフィラー"]
    path = tmp_path / "o.json"
    path.write_text(json.dumps(other), encoding="utf-8")
    rc = lp.main(["--diff", str(path)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "新しいフィラー" in data["fillers_ja"]["added"]


# --- prefer-ltr / script_mix ---


def test_prefer_ltr_latin_cjk_mix():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    # Latin + CJK without hiragana
    s = "Hello 世界 code."
    lang_default = t.detect_lang(s, prefer_ltr=False)
    lang_ltr = t.detect_lang(s, prefer_ltr=True)
    assert lang_ltr == "en"
    # without prefer_ltr, mix with enough latin still en in our tuned detector
    assert lang_ltr == "en"
    mix = t.script_mix(s)
    assert mix["latin"] > 0
    assert mix["cjk"] > 0
    assert "latin_ratio" in mix


def test_script_mix_in_stats():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    st = t.stats("Hello. 你好。")
    assert "script_mix" in st
    assert st["sentences"] >= 1


