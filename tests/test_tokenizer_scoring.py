"""o200k_base build-time scoring, runtime independence, agreement + compat reports."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402
import tokenizer_compat as tc  # noqa: E402

BANK = json.loads(tm.BANK_PATH.read_text(encoding="utf-8"))


def test_runtime_does_not_import_tiktoken():
    tree = ast.parse((ROOT / "TesseraTalk/tessera_talk.py").read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in getattr(n, "names", [])} | {
        (n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not names & {"tiktoken", "tokenizers"}


def test_en_baselines_include_contractions():
    assert "we've seen" in tm.en_baselines("we have seen")
    assert "he's going" in tm.en_baselines("he is going")
    assert "I'll take" in tm.en_baselines("I will take")
    assert "they're doing" in tm.en_baselines("they are doing")


def test_leading_space_scoring():
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    assert tm.o200k_tokens("zagen") == len(enc.encode(" zagen"))


def test_every_entry_prescored_and_beats_en_cheapest():
    for e in BANK["entries"]:
        assert e["scored_by"] == "o200k_base" and len(e["candidates"]) == 1
        src, to = e["from"][0], e["to"]
        en = min(tm.en_baselines(src), key=lambda f: (tm.o200k_tokens(f), len(f.encode())))
        assert (tm.o200k_tokens(to), len(to.encode())) < (tm.o200k_tokens(en), len(en.encode())), e["id"]


def test_agreement_metric_reported():
    r = tc.agreement()
    assert r["sample_n"] > 30 and r["matrix_n"] > 1000
    assert 0 <= r["sample_exact"] <= r["sample_n"] and 0 <= r["winner_flips"] <= r["cells_judged"]
    # regression floor (main before calibration: sample 15/37, matrix 798/3097, flips 100/1211;
    # calibrated: 25/37, 3091/3097, 0/1211); raise as estimate_tokens improves
    assert r["sample_exact"] >= 25 and r["matrix_exact"] >= 3091
    assert r["winner_flips"] == 0


def test_compat_report_matches_bank():
    d = json.loads(tc.COMPAT_JSON.read_text(encoding="utf-8"))
    assert {r["id"] for r in d["cells"]} == {e["id"] for e in BANK["entries"]}
    assert d["beats_en_count"]["o200k_base"] == d["adopted"]
    for n, (repo, rev) in tc.HF_TOKENIZERS.items():
        if n in d["tokenizers"]:
            assert d["tokenizers"][n] == {"kind": "hf", "repo": repo, "revision": rev}


def test_hf_tokenizers_optional_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(tc, "CACHE", tmp_path)

    def boom(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(tc.urllib.request, "urlopen", boom)
    toks, skipped = tc.load_tokenizers()
    assert set(skipped) == set(tc.HF_TOKENIZERS) and "o200k_base" in toks


def test_roundtrip_doc_up_to_date():
    assert (ROOT / "docs/roundtrip_impact.md").read_text(encoding="utf-8") == rt.impact_doc(rt.load())
