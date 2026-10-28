"""Shared loaders for TalkCompress tests (layers + 結合)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]

# One exec per (module name, path) for the pytest process. MorphoZip compiles
# a large regex inventory at import (~0.3s); local _load helpers used to redo
# that on every test. lex_policy overrides stay live: layers call into
# shared.lex_policy, which reads those globals at call time, so a cached
# layer still sees load_policy() / reload without a fresh exec.
_CACHE: dict[tuple[str, str], ModuleType] = {}
_DENSITY_BOUND = "_talkcompress_cached_load"


def load(name: str, rel: str) -> ModuleType:
    """Load a repo module by path, once per process.

    ``name`` is the ``sys.modules`` key. A later call with the same name and
    path returns the same module object and re-pins ``sys.modules``.
    """
    path = (ROOT / rel).resolve()
    key = (name, str(path))
    cached = _CACHE.get(key)
    if cached is not None:
        sys.modules[name] = cached
        if name == "density_zip":
            _bind_density_loader(cached)
        return cached

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _CACHE[key] = mod
    if name == "density_zip":
        _bind_density_loader(mod)
    return mod


def _bind_density_loader(mod: ModuleType) -> None:
    """Point the test-loaded DensityZip layer loader at this cache.

    Production ``DensityZip._load`` re-executes each layer on every hop
    (MorphoZip's import cost). Tests reach D through ``load``; routing that
    private loader here keeps the suite on one copy. The CLI module on disk
    is unchanged.
    """
    if getattr(mod, _DENSITY_BOUND, False):
        return

    def _cached(mod_name: str, rel: str) -> ModuleType:
        return load(mod_name, rel)

    mod._load = _cached  # type: ignore[attr-defined]
    setattr(mod, _DENSITY_BOUND, True)


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
