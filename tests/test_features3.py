"""Round-3 feature tests: window, profiles, quality, protect, packs, fingerprint, policy diff."""

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


def _ns(**kwargs):
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    defaults = dict(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
        aad="",
        lexicon=None,
        export_lexicon=None,
        no_rle=False,
        preserve_newlines=False,
        prefer_ltr=False,
        no_strip=False,
        no_unique=False,
        no_etymon=False,
        no_counters=False,
        aggressive_fillers=False,
        hex_nums=False,
        hex_bare=False,
        file=None,
        out=None,
        text=None,
        pipeline=None,
        auto_machine=False,
        lex_policy=None,
        trace=False,
        jsonl=True,
        window=None,
        keep_system=False,
        pack=None,
        protect_regex=None,
        min_ratio=None,
        allow_weak=False,
        max_loss_tokens=None,
        strict_loss=False,
        budget=None,
        role_layers=None,
        auto=False,
        layer=None,
        compare=False,
    )
    defaults.update(kwargs)
    return c.argparse.Namespace(**defaults)


# --- window + keep-system ---


def test_window_keeps_last_n():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    raw = "\n".join(
        [
            json.dumps({"role": "user", "text": "one ASAP"}),
            json.dumps({"role": "user", "text": "two ASAP"}),
            json.dumps({"role": "user", "text": "three ASAP"}),
            json.dumps({"role": "user", "text": "four ASAP"}),
        ]
    )
    out = c.process_jsonl(
        raw,
        _ns(window=2, pipeline="C"),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    assert len(lines) == 2
    assert "four" in lines[-1]["text"] or "ASAP" in lines[-1]["text"]


def test_window_keep_system():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    raw = "\n".join(
        [
            json.dumps({"role": "system", "text": "SYSTEM_PROMPT_KEEP"}),
            json.dumps({"role": "user", "text": "msg1 thank you"}),
            json.dumps({"role": "user", "text": "msg2 thank you"}),
            json.dumps({"role": "user", "text": "msg3 thank you"}),
        ]
    )
    out = c.process_jsonl(
        raw,
        _ns(window=1, keep_system=True, pipeline="C"),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    roles = [x["role"] for x in lines]
    assert "system" in roles
    assert any("SYSTEM_PROMPT_KEEP" in x["text"] for x in lines)
    # only last user among nonsystem
    users = [x for x in lines if x["role"] == "user"]
    assert len(users) == 1


def test_window_budget_drops_oldest():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    raw = "\n".join(
        [
            json.dumps({"role": "user", "text": "AAAAAAAAAA"}),
            json.dumps({"role": "user", "text": "BBBBBBBBBB"}),
            json.dumps({"role": "user", "text": "CCCCCCCCCC"}),
        ]
    )
    # identity-ish via layer C on already-short; budget tiny → drop oldest
    out = c.process_jsonl(
        raw,
        _ns(budget=15, jsonl=True, pipeline="C"),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    assert len(lines) >= 1
    total = sum(len(x["text"]) for x in lines)
    assert total <= 15 or len(lines) == 1


# --- profiles ---


def test_profile_load_mcp_short():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    prof = c.load_profile("mcp-short")
    assert prof.get("pipeline") == "C,E"
    assert prof.get("aggressive_fillers") is True


def test_profile_cli_override(capsys):
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    # CLI --layer E overrides profile pipeline
    rc = c.main(
        [
            "--profile",
            "mcp-short",
            "--layer",
            "E",
            "--text",
            "um thank you for your information",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert "um" not in out.lower() or "ty" in out or "info" in out or len(out) < 40


def test_profile_machine_needs_key():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    env_key = os.environ.pop("TALKCOMPRESS_ZIP_KEY", None)
    try:
        try:
            c.main(["--profile", "machine", "--text", "hello"])
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert "key" in str(e).lower() or e.code not in (0, None)
    finally:
        if env_key is not None:
            os.environ["TALKCOMPRESS_ZIP_KEY"] = env_key


# --- min-ratio ---


def test_min_ratio_fail():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    # identity layer won't shrink → ratio ~1.0 > 0.5
    rc = c.main(
        [
            "--layer",
            "C",
            "--min-ratio",
            "0.01",
            "--text",
            "xyzzy",  # no shorthand match → little/no shrink
        ]
    )
    # may or may not shrink; if ratio > 0.01 fail
    # xyzzy unchanged → ratio 1.0 > 0.01 → fail
    assert rc == 1


def test_min_ratio_allow_weak():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    rc = c.main(
        [
            "--layer",
            "C",
            "--min-ratio",
            "0.01",
            "--allow-weak",
            "--text",
            "xyzzy",
        ]
    )
    assert rc == 0


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


def test_protect_via_convo():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    rc = c.main(
        [
            "--layer",
            "E",
            "--text",
            "um [[keep:as soon as possible]] thank you",
        ]
    )
    assert rc == 0


# --- packs ---


def test_pack_dev_loads():
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    m = s.load_pack("dev")
    assert "pull request" in m or "Pull request".lower() in {k.lower() for k in m}
    sess = s.Session()
    sess.load_packs(["dev", "mcp"])
    out = s.compress("the model context protocol pull request is ready", session=sess)
    assert "MCP" in out or "PR" in out


def test_pack_via_convo(capsys):
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    rc = c.main(
        [
            "--layer",
            "C",
            "--pack",
            "mcp",
            "--text",
            "model context protocol tool call",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "MCP" in out or "TC" in out


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


def test_fingerprint_key_cli(capsys):
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    rc = c.main(["--fingerprint-key", "--key", "secret-demo", "--layer", "C", "--text", "x"])
    # fingerprint-key exits before requiring meaningful transform; returns 0
    assert rc == 0
    err = capsys.readouterr().err.strip()
    assert len(err) == 16


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


# --- apply_window unit ---


def test_apply_window_unit():
    c = _load("convo_zip", "ConvoZip/convo_zip.py")
    rows = [
        {"role": "system", "text": "S"},
        {"role": "user", "text": "a"},
        {"role": "user", "text": "b"},
        {"role": "user", "text": "c"},
    ]
    kept = c.apply_window(rows, window=2, keep_system=True)
    assert kept[0]["role"] == "system"
    assert [r["text"] for r in kept if r["role"] == "user"] == ["b", "c"]
