"""ConvoHub (D) agreed-convention ledger loader.

D owns ``ConvoHub/ledger/conventions.json`` as the source of truth for
already-decided policies and lex replacements across A–E. Layers (typically E
for etymon/symbol/字 substitutions) load via this module rather than hardcoding
only in MorphoZip.

Zipilogue RuleBook (A) remains a separate evolving slang ledger for machine
peers; this file is the static human-agreed registry.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = _ROOT / "ConvoHub" / "ledger" / "conventions.json"


def default_ledger_path() -> Path:
    return DEFAULT_LEDGER_PATH


def load_ledger(path: str | Path | None = None) -> dict[str, Any]:
    """Load the ConvoHub conventions ledger JSON (source of truth under D)."""
    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"ledger must be a JSON object: {p}")
    if "conventions" not in data or not isinstance(data["conventions"], list):
        raise ValueError(f"ledger missing conventions list: {p}")
    return data


def list_conventions(
    path: str | Path | None = None,
    *,
    kind: str | None = None,
    apply_layer: str | None = None,
) -> list[dict[str, Any]]:
    """Return convention entries, optionally filtered by kind / apply_layer."""
    data = load_ledger(path)
    out: list[dict[str, Any]] = []
    for c in data["conventions"]:
        if not isinstance(c, dict):
            continue
        if kind is not None and c.get("kind") != kind:
            continue
        if apply_layer is not None and str(c.get("apply_layer", "")).upper() != apply_layer.upper():
            continue
        out.append(c)
    return out


def lex_replacements(
    path: str | Path | None = None,
    *,
    apply_layer: str = "E",
) -> list[tuple[str, str]]:
    """Flatten lex conventions for ``apply_layer`` into (from, to) pairs.

    Longer ``from`` strings are listed first so phrase matches win over words.
    """
    pairs: list[tuple[str, str]] = []
    for c in list_conventions(path, kind="lex", apply_layer=apply_layer):
        to = str(c.get("to", ""))
        if not to:
            continue
        for src in c.get("from") or []:
            s = str(src)
            if s:
                pairs.append((s, to))
    pairs.sort(key=lambda kv: len(kv[0]), reverse=True)
    return pairs


def apply_ledger_lex(
    text: str,
    path: str | Path | None = None,
    *,
    apply_layer: str = "E",
) -> str:
    """Apply D-ledger lex replacements owned by ``apply_layer`` (default E).

    ASCII sources use word boundaries; non-ASCII (JA/ZH) use plain replace.
    """
    out = text
    for src, dst in lex_replacements(path, apply_layer=apply_layer):
        if src.isascii() and all(ch.isascii() for ch in src):
            # Multi-word phrases still get \\b at ends
            out = re.sub(rf"(?i)\b{re.escape(src)}\b", dst, out)
        else:
            out = out.replace(src, dst)
    return out


@lru_cache(maxsize=4)
def _cached_pairs(path_str: str, apply_layer: str) -> tuple[tuple[str, str], ...]:
    return tuple(lex_replacements(path_str, apply_layer=apply_layer))


def apply_ledger_lex_cached(
    text: str,
    path: str | Path | None = None,
    *,
    apply_layer: str = "E",
) -> str:
    """Same as ``apply_ledger_lex`` but caches the replacement table per path."""
    p = str(Path(path) if path is not None else DEFAULT_LEDGER_PATH)
    out = text
    for src, dst in _cached_pairs(p, apply_layer.upper()):
        if src.isascii() and all(ch.isascii() for ch in src):
            out = re.sub(rf"(?i)\b{re.escape(src)}\b", dst, out)
        else:
            out = out.replace(src, dst)
    return out


def convention_ids(path: str | Path | None = None) -> list[str]:
    return [str(c.get("id")) for c in list_conventions(path) if c.get("id")]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="TalkCompress ConvoHub (D) convention ledger")
    p.add_argument("--path", default=None, help="ledger JSON (default: ConvoHub/ledger/conventions.json)")
    p.add_argument("--list", action="store_true", help="list convention ids / summaries")
    p.add_argument("--apply", metavar="TEXT", help="apply E-layer lex replacements to TEXT")
    p.add_argument("--layer", default="E", help="apply_layer filter (default E)")
    args = p.parse_args(argv)
    if args.list:
        for c in list_conventions(args.path):
            print(
                json.dumps(
                    {
                        "id": c.get("id"),
                        "kind": c.get("kind"),
                        "apply_layer": c.get("apply_layer"),
                        "to": c.get("to"),
                        "from": c.get("from"),
                        "rationale": c.get("rationale"),
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    if args.apply is not None:
        print(apply_ledger_lex(args.apply, args.path, apply_layer=args.layer))
        return 0
    # default: dump ledger
    print(json.dumps(load_ledger(args.path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
