"""Shared loaders for TalkCompress tests (layers + 結合)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def ns(**kwargs):
    """Namespace for DensityZip transform helpers (結合テスト用)."""
    c = load("density_zip", "DensityZip/density_zip.py")
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
        strip=False,
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
        jsonl=False,
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
        keep_articles=False,
        spelled_nums=False,
        rule_state=None,
    )
    defaults.update(kwargs)
    return c.argparse.Namespace(**defaults)
