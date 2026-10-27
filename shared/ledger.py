"""ShorthandEdge (C) agreed-convention ledger loader.

C owns ``ShorthandEdge/ledger/conventions.json`` as the source of truth for
already-decided lex replacements and policy notes (first-round registration).
ShorthandEdge applies lex entries during compress by default.

Zipilogue RuleBook (A) remains a separate evolving slang ledger for machine
peers; this file is the static human-agreed registry.

D (DispatchHub) is router-only and does not own this ledger.

Ambiguity gate (C-owned): high-churn conjunction shortenings (moreover→also,
therefore→so, …) are skipped when the short form already collides in-text, or
when ``prefer_precision=True``. Furniture ``table``→机/桌 skips SQL/tech context.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = _ROOT / "ShorthandEdge" / "ledger" / "conventions.json"

# Default SQL/tech cues for furniture-table skip (also overridable per convention).
_DEFAULT_SQL_NEAR = (
    "sql",
    "select",
    "join",
    "schema",
    "database",
    "databases",
    "db",
    "varchar",
    "primary",
    "foreign",
    "index",
    "insert",
    "update",
    "delete",
    "truncate",
    "where",
    "group",
    "order",
    "having",
    "into",
    "values",
    "constraint",
)
_SQL_PHRASE_RE = re.compile(
    r"(?i)\b(?:create|drop|alter|truncate)\s+tables?\b"
    r"|\binsert\s+into\b"
    r"|\bupdate\s+\w+\s+set\b"
    r"|\bfrom\s+[a-z_][\w]*\b(?=.*\b(?:where|join|group|order|select|limit)\b)"
    r"|\b(?:where|join|group\s+by|order\s+by|select)\b.*\bfrom\b"
)


def default_ledger_path() -> Path:
    return DEFAULT_LEDGER_PATH


def load_ledger(path: str | Path | None = None) -> dict[str, Any]:
    """Load the ShorthandEdge conventions ledger JSON (source of truth under C)."""
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
    apply_layer: str = "C",
) -> list[tuple[str, str]]:
    """Flatten lex conventions for ``apply_layer`` into (from, to) pairs.

    Longer ``from`` strings are listed first so phrase matches win over words.
    Ignores gate metadata (use ``apply_ledger_lex`` for gated apply).
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


def _word_present(text: str, word: str) -> bool:
    if not word:
        return False
    if word.isascii() and all(ch.isascii() for ch in word):
        return re.search(rf"(?i)\b{re.escape(word)}\b", text) is not None
    return word in text


def sql_tech_context(text: str, *, extra_near: list[str] | None = None) -> bool:
    """True when text looks like SQL / DB tech (keep English ``table``)."""
    if _SQL_PHRASE_RE.search(text):
        return True
    near = set(_DEFAULT_SQL_NEAR)
    if extra_near:
        near.update(w.lower() for w in extra_near)
    lowered_tokens = set(re.findall(r"[a-z_][\w]*", text.lower()))
    # bare "from" alone is too common in EN furniture ("from the table"); require
    # another SQL cue, or treat create/drop/alter + table via phrase regex above.
    weak = {"from", "into", "values", "group", "order", "having", "update", "delete"}
    strong_hits = (lowered_tokens & near) - weak
    if strong_hits:
        return True
    if (lowered_tokens & weak) and (lowered_tokens & (near - weak)):
        return True
    return False


def _ambiguity_skip(
    text: str,
    src: str,
    dst: str,
    convention: dict[str, Any],
    *,
    prefer_precision: bool,
) -> bool:
    """Return True when a high-churn shortening should keep the original."""
    flag = convention.get("ambiguity_sensitive")
    if flag is False:
        return False
    wavy = {"also", "so", "but", "and", "or"}
    sensitive = bool(flag) or (
        str(convention.get("id", "")).startswith("conj-")
        and src.isascii()
        and dst.isascii()
        and " " not in dst
        and len(src) > len(dst)
        and dst.lower() in wavy
    )
    if not sensitive:
        return False
    if prefer_precision:
        return True
    # Collision: after removing one src match, dst still present → keep original.
    tmp = text
    if src.isascii() and all(ch.isascii() for ch in src):
        tmp = re.sub(rf"(?i)\b{re.escape(src)}\b", " ", tmp, count=1)
    else:
        tmp = tmp.replace(src, " ", 1)
    if _word_present(tmp, dst):
        return True
    return False


def _skip_convention(text: str, convention: dict[str, Any]) -> bool:
    """Context skip for a whole convention (e.g. furniture table in SQL)."""
    if convention.get("skip_sql_tech"):
        extra = convention.get("skip_near")
        extra_list = [str(x) for x in extra] if isinstance(extra, list) else None
        if sql_tech_context(text, extra_near=extra_list):
            return True
    skip_near = convention.get("skip_near")
    if isinstance(skip_near, list) and skip_near and not convention.get("skip_sql_tech"):
        # Legacy: any listed token as whole word → skip
        for tok in skip_near:
            if _word_present(text, str(tok)):
                return True
    skip_re = convention.get("skip_if_re")
    if isinstance(skip_re, str) and skip_re:
        if re.search(skip_re, text, flags=re.IGNORECASE):
            return True
    return False


def apply_ledger_lex(
    text: str,
    path: str | Path | None = None,
    *,
    apply_layer: str = "C",
    prefer_precision: bool = False,
) -> str:
    """Apply C-ledger lex replacements owned by ``apply_layer`` (default C).

    ASCII sources use word boundaries; non-ASCII (JA/ZH) use plain replace.

    Gates (C-owned):
    - ``skip_sql_tech`` / ``skip_near`` / ``skip_if_re`` on a convention
    - ambiguity: ``ambiguity_sensitive`` or wavy conj shorts; skip on in-text
      collision of ``to``, or when ``prefer_precision=True``
    """
    out = text
    # Build (src, dst, convention) sorted by src length desc
    items: list[tuple[str, str, dict[str, Any]]] = []
    for c in list_conventions(path, kind="lex", apply_layer=apply_layer):
        to = str(c.get("to", ""))
        if not to:
            continue
        for src in c.get("from") or []:
            s = str(src)
            if s:
                items.append((s, to, c))
    items.sort(key=lambda t: len(t[0]), reverse=True)

    for src, dst, convention in items:
        if _skip_convention(out, convention):
            continue
        if _ambiguity_skip(out, src, dst, convention, prefer_precision=prefer_precision):
            continue
        if src.isascii() and all(ch.isascii() for ch in src):
            out = re.sub(rf"(?i)\b{re.escape(src)}\b", dst, out)
        else:
            out = out.replace(src, dst)
    return out


@lru_cache(maxsize=8)
def _cached_lex_items(path_str: str, apply_layer: str) -> tuple[tuple[str, str, str], ...]:
    """Cache (src, dst, convention_id) — gates still need live convention lookup."""
    items: list[tuple[str, str, str]] = []
    for c in list_conventions(path_str, kind="lex", apply_layer=apply_layer):
        to = str(c.get("to", ""))
        cid = str(c.get("id", ""))
        if not to:
            continue
        for src in c.get("from") or []:
            s = str(src)
            if s:
                items.append((s, to, cid))
    items.sort(key=lambda t: len(t[0]), reverse=True)
    return tuple(items)


def apply_ledger_lex_cached(
    text: str,
    path: str | Path | None = None,
    *,
    apply_layer: str = "C",
    prefer_precision: bool = False,
) -> str:
    """Same as ``apply_ledger_lex`` (gates included). Cache is path/layer keyed."""
    # Gates need full convention dicts; reuse apply_ledger_lex for correctness.
    return apply_ledger_lex(
        text, path, apply_layer=apply_layer, prefer_precision=prefer_precision
    )


def convention_ids(path: str | Path | None = None) -> list[str]:
    return [str(c.get("id")) for c in list_conventions(path) if c.get("id")]


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="TalkCompress ShorthandEdge (C) convention ledger")
    p.add_argument(
        "--path",
        default=None,
        help="ledger JSON (default: ShorthandEdge/ledger/conventions.json)",
    )
    p.add_argument("--list", action="store_true", help="list convention ids / summaries")
    p.add_argument("--apply", metavar="TEXT", help="apply C-layer lex replacements to TEXT")
    p.add_argument("--layer", default="C", help="apply_layer filter (default C)")
    p.add_argument(
        "--prefer-precision",
        action="store_true",
        help="skip ambiguity-sensitive shortenings (moreover stays moreover, …)",
    )
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
                        "allowed_to": c.get("allowed_to"),
                        "from": c.get("from"),
                        "rationale": c.get("rationale"),
                        "ambiguity_sensitive": c.get("ambiguity_sensitive"),
                        "skip_sql_tech": c.get("skip_sql_tech"),
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    if args.apply is not None:
        print(
            apply_ledger_lex(
                args.apply,
                args.path,
                apply_layer=args.layer,
                prefer_precision=args.prefer_precision,
            )
        )
        return 0
    print(json.dumps(load_ledger(args.path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
