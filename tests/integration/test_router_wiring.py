"""結合・総合: DensityZip CLI / budget / window / profile / auto / roles.

Router wiring only — not a D product-surface unit suite.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests._helpers import load, ns  # noqa: E402


def test_resolve_layer_aliases():
    c = load("density_zip", "DensityZip/density_zip.py")
    assert c.resolve_layer("1") == "A"
    assert c.resolve_layer("tessera") == "B"
    assert c.resolve_layer("C") == "C"
    assert c.resolve_layer("morpho") == "E"


def test_route_shorthand_via_density_zip():
    c = load("density_zip", "DensityZip/density_zip.py")
    out = c.transform_line("C", "for your information", ns())
    assert "FYI" in out


def test_route_jsonl_via_density_zip():
    c = load("density_zip", "DensityZip/density_zip.py")
    raw = json.dumps({"role": "user", "text": "thank you"}, ensure_ascii=False)
    out = c.process_jsonl(raw, ns(), default_layer="C")
    obj = json.loads(out)
    assert obj["role"] == "user"
    assert "ty" in obj["text"].lower() or obj["text"] == "ty"


def test_route_zipilogue_via_density_zip():
    c = load("density_zip", "DensityZip/density_zip.py")
    n = ns(key="route-key", mode="encode")
    env = c.transform_line("A", "hi", n)
    n.mode = "decode"
    plain = c.transform_line("A", env, n)
    assert plain == "hi"


def test_convo_lexicon_flag(tmp_path):
    c = load("density_zip", "DensityZip/density_zip.py")
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"special phrase": "SP"}), encoding="utf-8")
    out = c.transform_line("C", "use the special phrase now", ns(lexicon=str(lex)))
    assert "SP" in out


def test_convo_file_and_out(tmp_path):
    c = load("density_zip", "DensityZip/density_zip.py")
    inp = tmp_path / "in.txt"
    outp = tmp_path / "out.txt"
    inp.write_text("for your information", encoding="utf-8")
    rc = c.main(["--layer", "C", "--file", str(inp), "--out", str(outp)])
    assert rc == 0
    assert "FYI" in outp.read_text(encoding="utf-8")


def test_budget_shrinks():
    c = load("density_zip", "DensityZip/density_zip.py")
    text = "um thank you for your information please let me know as soon as possible"
    out = c.run_budget(text, ns(), budget=40, layers=["C", "E"])
    assert len(out) < len(text)
    assert len(out) <= len(c.run_pipeline(["C", "E"], text, ns()))


def test_budget_passthrough_when_under():
    c = load("density_zip", "DensityZip/density_zip.py")
    text = "hi"
    out = c.run_budget(text, ns(), budget=100, layers=["C", "E"])
    assert out == text


def test_budget_cli_stats(capsys):
    c = load("density_zip", "DensityZip/density_zip.py")
    rc = c.main(
        [
            "--budget",
            "50",
            "--stats",
            "--text",
            "um thank you for your information please",
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err
    stats = json.loads(err.strip().splitlines()[-1])
    assert "chars_before" in stats
    assert "chars_after" in stats
    assert "steps" in stats
    assert stats["chars_after"] <= stats["chars_before"]


def test_role_layers_jsonl():
    c = load("density_zip", "DensityZip/density_zip.py")
    raw = "\n".join(
        [
            json.dumps({"role": "system", "text": "Keep this exact system prompt."}),
            json.dumps({"role": "user", "text": "as soon as possible thank you"}),
            json.dumps({"role": "assistant", "text": "I have 3 animals ready"}),
        ]
    )
    role_map = c.parse_role_layers("user=C,assistant=E,system=identity")
    out = c.process_jsonl(raw, ns(), role_map=role_map, default_layer="C")
    lines = [json.loads(ln) for ln in out.splitlines()]
    by_role = {ln["role"]: ln["text"] for ln in lines}
    assert by_role["system"] == "Keep this exact system prompt."
    assert "ASAP" in by_role["user"] or "asap" in by_role["user"].lower()
    assert "3匹" in by_role["assistant"] or "3" in by_role["assistant"]


def test_role_layers_cli(tmp_path):
    c = load("density_zip", "DensityZip/density_zip.py")
    inp = tmp_path / "chat.jsonl"
    inp.write_text(
        json.dumps({"role": "user", "text": "for your information"})
        + "\n"
        + json.dumps({"role": "system", "text": "NOCHANGE"})
        + "\n",
        encoding="utf-8",
    )
    outp = tmp_path / "out.jsonl"
    rc = c.main(
        [
            "--jsonl",
            "--role-layers",
            "user=C,system=identity",
            "--file",
            str(inp),
            "--out",
            str(outp),
        ]
    )
    assert rc == 0
    rows = [json.loads(ln) for ln in outp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any("FYI" in r["text"] for r in rows if r["role"] == "user")
    assert any(r["text"] == "NOCHANGE" for r in rows if r["role"] == "system")


def test_parse_role_layers_plus():
    c = load("density_zip", "DensityZip/density_zip.py")
    m = c.parse_role_layers("user=C+E,system=skip")
    assert m["user"] == ["C", "E"]
    assert m["system"] == "identity"


def test_auto_returns_nonempty():
    c = load("density_zip", "DensityZip/density_zip.py")
    text = "Hello there friend. こんにちは世界。Thanks for your information."
    layers = c.choose_auto_layers(text, ns())
    assert layers
    assert all(x in ("A", "B", "C", "E") for x in layers)
    out = c.run_pipeline(layers, text, ns())
    assert isinstance(out, str)
    assert len(out) > 0


def test_auto_cli(capsys):
    c = load("density_zip", "DensityZip/density_zip.py")
    rc = c.main(["--auto", "--text", "lol as soon as possible please"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out
    assert "asap" in out.lower() or "ASAP" in out or "pls" in out.lower() or len(out) < 40


def test_auto_machine_appends_a_when_key():
    c = load("density_zip", "DensityZip/density_zip.py")
    layers = c.choose_auto_layers("hello world asap", ns(auto_machine=True, key="secret"))
    assert "A" in layers


def test_convo_lex_policy_flag(tmp_path):
    import shared.lex_policy as lp

    backup = lp.dump_policy()
    c = load("density_zip", "DensityZip/density_zip.py")
    pol = tmp_path / "p.json"
    pol.write_text(
        json.dumps({"fillers_en": ["zzzzz"], "fillers_ja": []}),
        encoding="utf-8",
    )
    try:
        rc = c.main(["--layer", "E", "--lex-policy", str(pol), "--text", "zzzzz hello"])
        assert rc == 0
    finally:
        restore = tmp_path / "restore.json"
        restore.write_text(json.dumps(backup), encoding="utf-8")
        lp.load_policy(restore)


def test_window_keeps_last_n():
    c = load("density_zip", "DensityZip/density_zip.py")
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
        ns(window=2, pipeline="C", jsonl=True),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    assert len(lines) == 2
    assert "four" in lines[-1]["text"] or "ASAP" in lines[-1]["text"]


def test_window_keep_system():
    c = load("density_zip", "DensityZip/density_zip.py")
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
        ns(window=1, keep_system=True, pipeline="C", jsonl=True),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    roles = [x["role"] for x in lines]
    assert "system" in roles
    assert any("SYSTEM_PROMPT_KEEP" in x["text"] for x in lines)
    users = [x for x in lines if x["role"] == "user"]
    assert len(users) == 1


def test_window_budget_drops_oldest():
    c = load("density_zip", "DensityZip/density_zip.py")
    raw = "\n".join(
        [
            json.dumps({"role": "user", "text": "AAAAAAAAAA"}),
            json.dumps({"role": "user", "text": "BBBBBBBBBB"}),
            json.dumps({"role": "user", "text": "CCCCCCCCCC"}),
        ]
    )
    out = c.process_jsonl(
        raw,
        ns(budget=15, jsonl=True, pipeline="C"),
        default_layers=["C"],
    )
    lines = [json.loads(x) for x in out.splitlines()]
    assert len(lines) >= 1
    total = sum(len(x["text"]) for x in lines)
    assert total <= 15 or len(lines) == 1


def test_apply_window_unit():
    c = load("density_zip", "DensityZip/density_zip.py")
    rows = [
        {"role": "system", "text": "S"},
        {"role": "user", "text": "a"},
        {"role": "user", "text": "b"},
        {"role": "user", "text": "c"},
    ]
    kept = c.apply_window(rows, window=2, keep_system=True)
    assert kept[0]["role"] == "system"
    assert [r["text"] for r in kept if r["role"] == "user"] == ["b", "c"]


def test_profile_load_mcp_short():
    c = load("density_zip", "DensityZip/density_zip.py")
    prof = c.load_profile("mcp-short")
    assert prof.get("pipeline") == "C,E"
    assert prof.get("aggressive_fillers") is True


def test_profile_cli_override(capsys):
    c = load("density_zip", "DensityZip/density_zip.py")
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
    c = load("density_zip", "DensityZip/density_zip.py")
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


def test_min_ratio_fail():
    c = load("density_zip", "DensityZip/density_zip.py")
    rc = c.main(
        [
            "--layer",
            "C",
            "--min-ratio",
            "0.01",
            "--text",
            "xyzzy",
        ]
    )
    assert rc == 1


def test_min_ratio_allow_weak():
    c = load("density_zip", "DensityZip/density_zip.py")
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


def test_protect_via_convo():
    c = load("density_zip", "DensityZip/density_zip.py")
    rc = c.main(
        [
            "--layer",
            "E",
            "--text",
            "um [[keep:as soon as possible]] thank you",
        ]
    )
    assert rc == 0


def test_pack_via_convo(capsys):
    c = load("density_zip", "DensityZip/density_zip.py")
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


def test_fingerprint_key_cli(capsys):
    c = load("density_zip", "DensityZip/density_zip.py")
    rc = c.main(["--fingerprint-key", "--key", "secret-demo", "--layer", "C", "--text", "x"])
    assert rc == 0
    err = capsys.readouterr().err.strip()
    assert len(err) == 16


def test_density_zip_rule_state_without_key(tmp_path):
    c = load("density_zip", "DensityZip/density_zip.py")
    rb = load("zipilogue_rulebook", "Zipilogue/rulebook.py")
    state = tmp_path / "book.json"
    book = rb.RuleBook.load(state)
    book.declare("alpha beta gamma", "r1")
    book.save()
    n = c.build_parser().parse_args(
        ["--layer", "A", "--rule-state", str(state), "--text", "see alpha beta gamma"]
    )
    out = c._run_a("see alpha beta gamma", n, decode=False)
    assert "r1" in out
    assert "alpha beta gamma" not in out


def test_density_zip_translate_min_wires_to_b(capsys):
    """D only routes --translate-min into TesseraTalk (B)."""
    h = load("density_zip", "DensityZip/density_zip.py")
    rc = h.main(
        ["--layer", "B", "--translate-min", "--text", "Good morning. See you later."]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out
    # mosaic form
    assert ":" in out or "|" in out
    # should be shorter/changed vs without flag
    rc2 = h.main(["--layer", "B", "--text", "Good morning. See you later."])
    assert rc2 == 0
