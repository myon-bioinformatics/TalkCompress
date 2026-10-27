"""ShorthandEdge (C) agreed-convention ledger loader.

C owns ``ShorthandEdge/ledger/conventions.json`` as the source of truth for
already-decided lex replacements and policy notes (first-round registration).
ShorthandEdge applies lex entries during compress by default.

Zipilogue RuleBook (A) remains a separate evolving slang ledger for machine
peers; this file is the static human-agreed registry.

D (DensityZip) is orchestration + density façade and does not own this ledger.

Ambiguity gate (C-owned): high-churn conjunction shortenings (moreover→also,
therefore→so, …) are skipped when the short form already collides in-text, or
when ``prefer_precision=True``. Furniture ``table``→机/桌 skips SQL/tech context.

Dual metrics (required on ``kind=lex``): registration is usable only when both
views are recorded — **token** via B TesseraTalk ``estimate_tokens``, and **bit**
via E MorphoZip ``utf8_bits`` (default) or ``closed_inventory_bits`` when an
inventory applies. Together they narrow candidate short forms. Policy rows may
omit ``metrics`` / set null. C calls B/E helpers; ownership stays with B/E.

Abbrev family (``family=abbrev``): C-only bucket for contractions (``c-ill`` /
``I will``→``I'll`` via ``apply_en_contractions``), chat acronyms (``c-asap``…),
and latin shorts (``e.g.`` / ``etc.`` / ``vs`` / ``i.e.``). Contraction rows set
``ledger_apply=false`` (registration only). Polarity: after C ``don't``/``can't``,
E may fold to ``!`` / ``!can`` on a ``C,E`` pipeline.

Emoji family (``family=emoji``): C-owned word→emoji shortenings (``ファイア``→``🔥``,
``heart``/``ハート``→``♡``, …). Synced from ``EMOJI_SPEC``; ``ledger_apply=true``
so ``apply_ledger_lex`` rewrites (unlike contractions). Dual metrics required;
utf8 must shrink on the sample. ``information``→``ℹ️`` stays on E etymon path.
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

# --- Dual metrics (token = B, bit = E); C records both on lex registration -----

_TOKEN_VIA = "B TesseraTalk estimate_tokens"
_BIT_VIA_UTF8 = "E MorphoZip utf8_bits"
_BIT_VIA_INV = "E MorphoZip closed_inventory_bits"


def _load_layer(mod_name: str, rel: str) -> Any:
    """Load a sibling layer module by path (B/E are not package imports)."""
    import importlib.util
    import sys

    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = _ROOT / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tessera() -> Any:
    return _load_layer("tessera_talk", "TesseraTalk/tessera_talk.py")


def _morpho() -> Any:
    return _load_layer("morpho_zip", "MorphoZip/morpho_zip.py")


def _ratio(before: int, after: int) -> float | None:
    if before == 0:
        return None if after == 0 else float("inf")
    return round(after / before, 4)


def compute_lex_metrics(
    src: str,
    dst: str,
    *,
    inventory_name: str | None = None,
    inventory_extended: bool = False,
) -> dict[str, Any]:
    """Compute dual metrics for one ``from``→``to`` registration pair.

    - ``token``: B TesseraTalk ``estimate_tokens`` before/after (+ delta/ratio)
    - ``bit``: E MorphoZip — ``utf8_bits`` always as secondary; when
      ``inventory_name`` is a known closed inventory, primary ``model`` is
      ``inventory`` (ceil(log2 N) per occurrence); otherwise ``utf8``.
      ``inventory_extended`` selects the extended closed pack (wider N).
    """
    estimate_tokens = _tessera().estimate_tokens
    morpho = _morpho()
    before_t = int(estimate_tokens(src))
    after_t = int(estimate_tokens(dst))
    before_u = int(morpho.utf8_bits(src))
    after_u = int(morpho.utf8_bits(dst))

    inv_block: dict[str, Any] | None = None
    model = "utf8"
    via_bit = _BIT_VIA_UTF8
    before_b, after_b = before_u, after_u
    if inventory_name:
        try:
            bits_per = int(
                morpho.closed_inventory_bits(
                    inventory_name, extended=inventory_extended
                )
            )
            raw = morpho.closed_bit_cost(
                inventory_name, "", extended=inventory_extended
            )
            inv_block = {
                "name": inventory_name,
                "bits_per": bits_per,
                "n": int(raw["inventory_n"]),
                "extended": bool(inventory_extended),
                "note": (
                    "inventory ceil(log2 N) per occurrence; "
                    "utf8 remains secondary under bit.utf8"
                ),
            }
            model = "inventory"
            via_bit = f"{_BIT_VIA_INV}({inventory_name})"
            # One occurrence each side of the mapping → same width (slot cost).
            before_b, after_b = bits_per, bits_per
        except KeyError:
            inv_block = None

    return {
        "token": {
            "before": before_t,
            "after": after_t,
            "delta": after_t - before_t,
            "ratio": _ratio(before_t, after_t),
            "sample_from": src,
            "via": _TOKEN_VIA,
        },
        "bit": {
            "model": model,
            "before": before_b,
            "after": after_b,
            "delta": after_b - before_b,
            "ratio": _ratio(before_b, after_b),
            "sample_from": src,
            "via": via_bit,
            "utf8": {
                "before": before_u,
                "after": after_u,
                "delta": after_u - before_u,
            },
            "inventory": inv_block,
        },
    }


def metrics_for_convention(convention: dict[str, Any]) -> dict[str, Any] | None:
    """Build dual metrics for a lex convention (first ``from`` → ``to``).

    Returns None for non-lex / missing to. Optional ``inventory`` field on the
    convention selects E closed-inventory bit model.
    """
    if convention.get("kind") != "lex":
        return None
    to = str(convention.get("to", ""))
    srcs = [str(x) for x in (convention.get("from") or []) if str(x)]
    if not to or not srcs:
        return None
    inv = convention.get("inventory")
    inv_name = str(inv) if isinstance(inv, str) and inv else None
    extended = bool(convention.get("extended"))
    return compute_lex_metrics(
        srcs[0], to, inventory_name=inv_name, inventory_extended=extended
    )


def validate_lex_metrics(
    convention: dict[str, Any],
    *,
    strict: bool = True,
) -> list[str]:
    """Return issue strings when a lex entry lacks usable dual metrics.

    Policy / non-lex: always OK (metrics may be null/absent).
    Lex: requires ``metrics.token`` and ``metrics.bit`` with before/after ints.
    When ``strict``, missing either is an error; otherwise a warning-style note.
    """
    if convention.get("kind") != "lex":
        return []
    cid = str(convention.get("id", "?"))
    issues: list[str] = []
    metrics = convention.get("metrics")
    if not isinstance(metrics, dict):
        msg = f"{cid}: lex entry missing metrics object (need token + bit)"
        issues.append(msg if strict else f"warn: {msg}")
        return issues
    for key in ("token", "bit"):
        block = metrics.get(key)
        if not isinstance(block, dict):
            msg = f"{cid}: metrics.{key} required"
            issues.append(msg if strict else f"warn: {msg}")
            continue
        for side in ("before", "after"):
            if not isinstance(block.get(side), int):
                msg = f"{cid}: metrics.{key}.{side} must be int"
                issues.append(msg if strict else f"warn: {msg}")
    bit = metrics.get("bit") if isinstance(metrics.get("bit"), dict) else None
    if bit is not None and bit.get("model") not in (None, "utf8", "inventory"):
        msg = f"{cid}: metrics.bit.model must be utf8|inventory"
        issues.append(msg if strict else f"warn: {msg}")
    return issues


def validate_ledger_metrics(
    path: str | Path | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    """Validate dual metrics on all lex conventions in the ledger."""
    issues: list[str] = []
    for c in list_conventions(path):
        issues.extend(validate_lex_metrics(c, strict=strict))
    return issues


def ensure_lex_metrics(convention: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``convention`` with ``metrics`` filled for lex rows."""
    out = dict(convention)
    if out.get("kind") != "lex":
        if "metrics" not in out:
            out["metrics"] = None
        return out
    computed = metrics_for_convention(out)
    if computed is not None:
        out["metrics"] = computed
    return out



def sync_abbrev_contraction_lex(
    path: str | Path | None = None,
    *,
    write: bool = True,
    skip_zero_utf8: bool = True,
) -> dict[str, Any]:
    """Upsert C abbrev contraction rows from ``EN_CONTRACTION_SPEC``.

    Derives dual metrics; skips pairs whose utf8 bit delta is ≥ 0 when
    ``skip_zero_utf8`` (default). Sets ``family=abbrev`` / ``abbrev_kind=contraction``
    / ``ledger_apply=false``. Also tags known latin + acronym abbrev rows with
    ``family=abbrev`` when missing. Bumps meta notes for the abbrev bucket.
    """
    from shared.lex_policy import en_contraction_ledger_rows

    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    data = load_ledger(p)
    by_id = {
        str(c.get("id")): i
        for i, c in enumerate(data["conventions"])
        if isinstance(c, dict) and c.get("id")
    }
    skipped: list[str] = []
    upserted: list[str] = []
    for row in en_contraction_ledger_rows():
        filled = ensure_lex_metrics(row)
        utf8 = (filled.get("metrics") or {}).get("bit", {}).get("utf8") or {}
        delta = utf8.get("delta")
        if skip_zero_utf8 and isinstance(delta, int) and delta >= 0:
            skipped.append(str(filled["id"]))
            continue
        cid = str(filled["id"])
        if cid in by_id:
            # Preserve any extra keys; overwrite core + metrics from live spec.
            idx = by_id[cid]
            old = data["conventions"][idx]
            merged = dict(old)
            for k, v in filled.items():
                merged[k] = v
            data["conventions"][idx] = merged
        else:
            data["conventions"].append(filled)
            by_id[cid] = len(data["conventions"]) - 1
        upserted.append(cid)

    # Tag existing abbrev-bucket rows (acronyms + latin shorts)
    latin_ids = {
        "conj-for-example": "latin",
        "conj-that-is": "latin",
        "conj-etc": "latin",
        "conj-vs": "latin",
    }
    for c in data["conventions"]:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", ""))
        if cid in latin_ids:
            c.setdefault("family", "abbrev")
            c.setdefault("abbrev_kind", latin_ids[cid])
        elif cid.startswith("c-") and c.get("kind") == "lex":
            c.setdefault("family", "abbrev")
            if c.get("abbrev_kind") is None:
                # contractions already set; remaining c-* are chat acronyms
                if c.get("rewrite_via") == "apply_en_contractions":
                    c["abbrev_kind"] = "contraction"
                else:
                    c["abbrev_kind"] = "acronym"

    meta = data.setdefault("meta", {})
    notes = meta.setdefault("notes", [])
    abbrev_note = (
        "family=abbrev (C-only): contractions (c-ill / I'll-family via "
        "apply_en_contractions; ledger_apply=false), chat acronyms (c-asap…), "
        "latin shorts (e.g./etc./vs/i.e.). Polarity: after C don't/can't, E may "
        "fold don't→! / can't→!can on C,E pipeline."
    )
    if isinstance(notes, list) and abbrev_note not in notes:
        notes.append(abbrev_note)
    meta["abbrev_sync"] = {
        "upserted": upserted,
        "skipped_nonshrink_utf8": skipped,
        "source": "shared.lex_policy.EN_CONTRACTION_SPEC",
    }
    ver = data.get("version", 1)
    try:
        data["version"] = max(int(ver), 2)
    except (TypeError, ValueError):
        data["version"] = 2
    if write:
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        load_ledger.cache_clear() if hasattr(load_ledger, "cache_clear") else None
    return data



def sync_emoji_lex(
    path: str | Path | None = None,
    *,
    write: bool = True,
    skip_zero_utf8: bool = True,
) -> dict[str, Any]:
    """Upsert C emoji rows from ``EMOJI_SPEC`` (family=emoji, ledger_apply=true).

    Derives dual metrics; skips pairs whose utf8 bit delta is ≥ 0 when
    ``skip_zero_utf8`` (default). Bumps meta notes for the emoji bucket.
    """
    from shared.lex_policy import emoji_ledger_rows

    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    data = load_ledger(p)
    by_id = {
        str(c.get("id")): i
        for i, c in enumerate(data["conventions"])
        if isinstance(c, dict) and c.get("id")
    }
    skipped: list[str] = []
    upserted: list[str] = []
    for row in emoji_ledger_rows():
        filled = ensure_lex_metrics(row)
        utf8 = (filled.get("metrics") or {}).get("bit", {}).get("utf8") or {}
        delta = utf8.get("delta")
        if skip_zero_utf8 and isinstance(delta, int) and delta >= 0:
            skipped.append(str(filled["id"]))
            continue
        cid = str(filled["id"])
        if cid in by_id:
            idx = by_id[cid]
            old = data["conventions"][idx]
            merged = dict(old)
            for k, v in filled.items():
                merged[k] = v
            data["conventions"][idx] = merged
        else:
            data["conventions"].append(filled)
            by_id[cid] = len(data["conventions"]) - 1
        upserted.append(cid)

    meta = data.setdefault("meta", {})
    notes = meta.setdefault("notes", [])
    emoji_note = (
        "family=emoji (C-only): word→emoji shortenings (ファイア→🔥, heart/ハート→♡, …) "
        "via EMOJI_SPEC; ledger_apply=true (apply_ledger_lex). Dual metrics; utf8 must "
        "shrink. information→ℹ️ stays E. Bare fire/idea/eyes/… utf8-flat forms may live "
        "in DEFAULT_MAP runtime extras only."
    )
    if isinstance(notes, list) and emoji_note not in notes:
        notes.append(emoji_note)
    meta["emoji_sync"] = {
        "upserted": upserted,
        "skipped_nonshrink_utf8": skipped,
        "source": "shared.lex_policy.EMOJI_SPEC",
    }
    ver = data.get("version", 1)
    try:
        data["version"] = max(int(ver), 2)
    except (TypeError, ValueError):
        data["version"] = 2
    if write:
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        load_ledger.cache_clear() if hasattr(load_ledger, "cache_clear") else None
    return data


def backfill_ledger_metrics(
    path: str | Path | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Fill dual metrics on every lex convention; optionally write JSON.

    Policy rows get ``metrics: null`` when absent. Bumps ``version`` to ≥2 and
    ensures a meta note about dual metrics.
    """
    p = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    data = load_ledger(p)
    note = (
        "lex metrics (required): token = B TesseraTalk estimate_tokens; "
        "bit = E MorphoZip utf8_bits (default) or closed_inventory_bits when "
        "inventory applies. Both views narrow registration candidates."
    )
    meta = data.setdefault("meta", {})
    notes = meta.setdefault("notes", [])
    if isinstance(notes, list) and note not in notes:
        notes.append(note)
    new_conventions: list[Any] = []
    for c in data["conventions"]:
        if not isinstance(c, dict):
            new_conventions.append(c)
            continue
        new_conventions.append(ensure_lex_metrics(c))
    data["conventions"] = new_conventions
    ver = data.get("version", 1)
    try:
        data["version"] = max(int(ver), 2)
    except (TypeError, ValueError):
        data["version"] = 2
    if write:
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return data


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
        if c.get("ledger_apply") is False:
            continue
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
        if c.get("ledger_apply") is False:
            continue  # registration-only (e.g. EN contractions via apply_en_contractions)
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
    p.add_argument(
        "--backfill-metrics",
        action="store_true",
        help="compute token+bit dual metrics for all lex rows and write ledger",
    )
    p.add_argument(
        "--sync-contractions",
        action="store_true",
        help="upsert C abbrev contractions from EN_CONTRACTION_SPEC + tag family=abbrev",
    )
    p.add_argument(
        "--sync-emoji",
        action="store_true",
        help="upsert C word→emoji rows from EMOJI_SPEC + tag family=emoji",
    )
    p.add_argument(
        "--validate-metrics",
        action="store_true",
        help="check lex rows have metrics.token and metrics.bit (exit 1 on fail)",
    )
    p.add_argument(
        "--warn-metrics",
        action="store_true",
        help="with --validate-metrics: warn only (exit 0) instead of strict fail",
    )
    args = p.parse_args(argv)
    if args.sync_contractions:
        data = sync_abbrev_contraction_lex(args.path, write=True)
        info = (data.get("meta") or {}).get("abbrev_sync") or {}
        print(
            f"synced abbrev contractions upserted={info.get('upserted')} "
            f"skipped_utf8={info.get('skipped_nonshrink_utf8')} "
            f"→ {args.path or DEFAULT_LEDGER_PATH}"
        )
        return 0
    if args.sync_emoji:
        data = sync_emoji_lex(args.path, write=True)
        info = (data.get("meta") or {}).get("emoji_sync") or {}
        print(
            f"synced emoji upserted={info.get('upserted')} "
            f"skipped_utf8={info.get('skipped_nonshrink_utf8')} "
            f"→ {args.path or DEFAULT_LEDGER_PATH}"
        )
        return 0
    if args.backfill_metrics:
        data = backfill_ledger_metrics(args.path, write=True)
        n_lex = sum(1 for c in data["conventions"] if isinstance(c, dict) and c.get("kind") == "lex")
        print(f"backfilled dual metrics for {n_lex} lex conventions → {args.path or DEFAULT_LEDGER_PATH}")
        return 0
    if args.validate_metrics:
        issues = validate_ledger_metrics(args.path, strict=not args.warn_metrics)
        for line in issues:
            print(line)
        if issues and not args.warn_metrics:
            return 1
        if not issues:
            print("ok: all lex conventions have token + bit metrics")
        return 0
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
                        "metrics": c.get("metrics"),
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
