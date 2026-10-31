#!/usr/bin/env python3
"""DensityZip (D): cross-layer orchestration + density metric façade / shared CLI.

Decided name (2026-10-27): replaces provisional DispatchHub. Not Hub/Convo/Dispatch.
Distinct from **Zipilogue** (A) and **MorphoZip** (E) — always use the full name.

Supports single ``--layer``, sequential ``--pipeline C,E``, ``--budget``,
``--role-layers``, ``--auto``, ``--trace``, ``--window``, ``--profile``,
quality gates, packs, protect spans, file I/O, ``--compare``, and
Zipilogue ``--rule-state`` (A evolving slang ledger; key optional).

Density façade: ``--compare`` / ``--budget`` / ``--stats`` surface token-ish
metrics (budget, ``content_token_loss``, B ``estimate_tokens`` via wiring) and
bit-ish metrics (E ``density()`` / ``pronoun_bit_cost`` aggregated here).
B owns ``estimate_tokens``; E owns pronoun inventory bits; C owns the ledger.
Final pipeline step ``B-final-zh-de`` / ``B-final-token`` (``--final-zh-de`` /
``--final-token`` / ``--auto`` default end): B ``final_token_pass`` (alias
``final_zh_de_token_pass``) — phrase candidate bank (ZH/DE compounds, EN acronyms
via cheapest) + ES/FR short tense + zh|de sentence minify to **reduce** tokens
after A–E (複合名詞 etc. are candidate labels, not a noun-only policy).

Agreed human conventions (under/below→下, 凹凸, …) live under
``ShorthandEdge/ledger/conventions.json`` and are applied by **C**, not D.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]

_LAYER_ALIASES: dict[str, str] = {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "E",
    "a": "A",
    "b": "B",
    "c": "C",
    "d": "D",
    "e": "E",
    "zipilogue": "A",
    "tessera": "B",
    "tessera_talk": "B",
    "shorthand": "C",
    "shorthand_edge": "C",
    "density": "D",
    "density_zip": "D",
    "densityzip": "D",
    "morpho": "E",
    "morpho_zip": "E",
    "identity": "identity",
    "skip": "identity",
    # Final token pass (B-owned; not a new layer letter).
    # Canonical id stays B-final-zh-de for CLI compat; prefer final-token aliases.
    "b-final-zh-de": "B-final-zh-de",
    "final-zh-de": "B-final-zh-de",
    "zhde": "B-final-zh-de",
    "zh-de": "B-final-zh-de",
    "b-final-token": "B-final-zh-de",
    "final-token": "B-final-zh-de",
    "final_token": "B-final-zh-de",
}

FINAL_ZH_DE_STEP = "B-final-zh-de"
FINAL_TOKEN_STEP = FINAL_ZH_DE_STEP  # preferred name


def _load(mod_name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_layer(raw: str) -> str:
    key = raw.strip()
    if key in _LAYER_ALIASES:
        return _LAYER_ALIASES[key]
    low = key.lower()
    if low in _LAYER_ALIASES:
        return _LAYER_ALIASES[low]
    # Preserve synthetic final-step id
    if low in (
        "b-final-zh-de",
        "final-zh-de",
        "zhde",
        "zh-de",
        "b-final-token",
        "final-token",
        "final_token",
    ):
        return FINAL_ZH_DE_STEP
    return key.upper()


def parse_pipeline(raw: str) -> list[str]:
    """Parse comma-separated layer aliases into canonical A/B/C/E codes."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise SystemExit("--pipeline needs at least one layer (e.g. C,E)")
    layers = [resolve_layer(p) for p in parts]
    for layer in layers:
        if layer == "D":
            raise SystemExit("D (DensityZip) is this router; omit from --pipeline")
        if layer == "identity":
            continue
        if layer == FINAL_ZH_DE_STEP:
            continue
        if layer not in ("A", "B", "C", "E"):
            raise SystemExit(f"unknown pipeline layer: {layer}")
    return layers


def parse_role_layers(raw: str) -> dict[str, str | list[str]]:
    """Parse ``user=C,assistant=E,system=identity`` into role → layer or pipeline list.

    Values may be a single layer or a comma-free alias; use ``+`` for multi-step
    per role (e.g. ``user=C+E``). Plain commas separate role assignments.
    """
    mapping: dict[str, str | list[str]] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"role-layers entry needs role=layer: {part}")
        role, spec = part.split("=", 1)
        role = role.strip().lower()
        spec = spec.strip()
        if "+" in spec:
            layers = [resolve_layer(x) for x in spec.split("+") if x.strip()]
            mapping[role] = layers
        else:
            mapping[role] = resolve_layer(spec)
    return mapping




# --- round-3: profiles / window / quality ---

_PROFILE_FLAG_KEYS = (
    "layer",
    "pipeline",
    "budget",
    "role_layers",
    "auto",
    "auto_machine",
    "aggressive_fillers",
    "strip",
    "no_rle",
    "preserve_newlines",
    "prefer_ltr",
    "translate_min",
    "translation_bank",
    "translate_engine",
    "final_zh_de",
    "no_final_zh_de",
    "zh_de_phrase_bank",
    "es_fr_tense_bank",
    "hex_nums",
    "hex_bare",
    "no_strip",
    "no_unique",
    "no_etymon",
    "no_counters",
    "keep_articles",
    "spelled_nums",
    "langs",
    "aad",
    "lexicon",
    "lex_policy",
    "pack",
    "protect_regex",
    "min_ratio",
    "max_loss_tokens",
    "allow_weak",
    "strict_loss",
    "stats",
    "trace",
    "window",
    "keep_system",
    "mode",
)


def load_profile(name: str | None = None, path: str | None = None) -> dict[str, Any]:
    """Load a JSON profile from ``profiles/<name>.json`` or an explicit path."""
    if path:
        p = pathlib.Path(path)
    elif name:
        p = ROOT / "profiles" / f"{name}.json"
    else:
        raise SystemExit("profile requires --profile NAME or --profile-file PATH")
    if not p.is_file():
        raise SystemExit(f"profile not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"profile must be a JSON object: {p}")
    # drop documentation-only keys
    return {k: v for k, v in data.items() if not str(k).startswith("comment") and k != "comment"}


def apply_profile(args: argparse.Namespace, profile: dict[str, Any], *, cli_explicit: set[str]) -> None:
    """Apply profile keys onto args. CLI-explicit flags win over profile values.

    ``cli_explicit`` is the set of dest names the user passed on the command line.
    """
    # Map profile JSON keys (kebab or snake) → argparse dest
    aliases = {
        "role-layers": "role_layers",
        "auto-machine": "auto_machine",
        "aggressive-fillers": "aggressive_fillers",
        "no-rle": "no_rle",
        "preserve-newlines": "preserve_newlines",
        "prefer-ltr": "prefer_ltr",
        "translate-min": "translate_min",
        "translation-bank": "translation_bank",
        "translate-engine": "translate_engine",
        "final-zh-de": "final_zh_de",
        "no-final-zh-de": "no_final_zh_de",
        "zh-de-phrase-bank": "zh_de_phrase_bank",
        "es-fr-tense-bank": "es_fr_tense_bank",
        "hex-nums": "hex_nums",
        "hex-bare": "hex_bare",
        "strip": "strip",
        "no-strip": "no_strip",
        "no-unique": "no_unique",
        "no-etymon": "no_etymon",
        "no-counters": "no_counters",
        "keep-articles": "keep_articles",
        "spelled-nums": "spelled_nums",
        "lex-policy": "lex_policy",
        "protect-regex": "protect_regex",
        "min-ratio": "min_ratio",
        "max-loss-tokens": "max_loss_tokens",
        "allow-weak": "allow_weak",
        "strict-loss": "strict_loss",
        "keep-system": "keep_system",
    }
    # If CLI fixed a routing mode, do not also apply the other from profile.
    skip = set(cli_explicit)
    if "layer" in cli_explicit:
        skip.update({"pipeline", "auto", "compare"})
    if "pipeline" in cli_explicit:
        skip.update({"layer", "auto", "compare"})
    if "auto" in cli_explicit:
        skip.update({"layer", "pipeline", "compare"})
    if "compare" in cli_explicit:
        skip.update({"layer", "pipeline", "auto"})

    for raw_key, val in profile.items():
        dest = aliases.get(raw_key, raw_key.replace("-", "_"))
        if dest not in _PROFILE_FLAG_KEYS and dest not in ("pack",):
            continue
        if dest in skip:
            continue
        setattr(args, dest, val)


def _parse_jsonl_rows(raw: str) -> list[dict[str, Any]]:
    """Parse JSONL into row dicts with role/text; plain lines become {role:None,text:...}."""
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        role = None
        body = line
        if line.lstrip().startswith("{"):
            try:
                obj: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                obj = {}
            if obj:
                role = obj.get("role")
                body = str(obj.get("text") or obj.get("content") or obj.get("message") or "")
                rows.append({"role": role, "text": body, "raw_obj": obj})
                continue
        rows.append({"role": role, "text": body, "raw_obj": None})
    return rows


def apply_window(
    rows: list[dict[str, Any]],
    *,
    window: int | None = None,
    budget: int | None = None,
    keep_system: bool = False,
) -> list[dict[str, Any]]:
    """Drop oldest messages after compress.

    Precedence (documented): callers must compress each line *first*, then call
    this. If both ``window`` and ``budget`` are set: first keep last N by
    ``window``, then drop oldest further until total chars ≤ budget.
    With ``keep_system``, ``role=system`` lines are never dropped (they still
    count toward budget/window totals).
    """
    if not rows:
        return rows

    def _is_system(r: dict[str, Any]) -> bool:
        return keep_system and str(r.get("role") or "").lower() == "system"

    out = list(rows)
    if window is not None and window >= 0:
        if keep_system:
            systems = [r for r in out if _is_system(r)]
            nonsys = [r for r in out if not _is_system(r)]
            nonsys = nonsys[-window:] if window > 0 else []
            # preserve relative order: systems in original positions among kept nonsys
            # simpler: all systems first (stable among themselves) then last N nonsys
            # Better: filter to systems ∪ last-window nonsys keeping original order
            keep_ids = set(id(r) for r in systems) | set(id(r) for r in nonsys)
            # recompute nonsys by index from end
            nonsys_idx = [i for i, r in enumerate(out) if not _is_system(r)]
            keep_nonsys = set(nonsys_idx[-window:] if window > 0 else [])
            out = [
                r
                for i, r in enumerate(out)
                if _is_system(r) or i in keep_nonsys
            ]
        else:
            out = out[-window:] if window > 0 else []

    if budget is not None and budget >= 0:
        def total_chars(rs: list[dict[str, Any]]) -> int:
            return sum(len(str(r.get("text") or "")) for r in rs)

        while len(out) > 0 and total_chars(out) > budget:
            # drop oldest non-system if keep_system, else oldest
            drop_at = None
            for i, r in enumerate(out):
                if _is_system(r):
                    continue
                drop_at = i
                break
            if drop_at is None:
                # only system lines left but still over budget — stop (cannot drop)
                break
            out.pop(drop_at)
    return out


def content_token_loss(before: str, after: str) -> int:
    """Rough whitespace-split heuristic: tokens present in before but not after (multiset)."""
    import collections

    def toks(s: str) -> collections.Counter:
        return collections.Counter(t for t in re.split(r"\s+", s.strip()) if t)

    b, a = toks(before), toks(after)
    lost = 0
    for tok, n in b.items():
        lost += max(0, n - a.get(tok, 0))
    return lost


def check_quality(
    before: str,
    after: str,
    args: argparse.Namespace,
) -> int:
    """Return exit code contribution: 0 ok, 1 fail. Prints warnings to stderr when soft."""
    rc = 0
    before_n = len(before)
    after_n = len(after)
    ratio = (after_n / before_n) if before_n else 0.0
    min_ratio = getattr(args, "min_ratio", None)
    if min_ratio is not None:
        # insufficient shrink if ratio > R (still large)
        if before_n > 0 and ratio > float(min_ratio):
            msg = {
                "quality": "weak_shrink",
                "chars_before": before_n,
                "chars_after": after_n,
                "ratio": round(ratio, 4),
                "min_ratio": float(min_ratio),
            }
            if getattr(args, "allow_weak", False):
                if getattr(args, "stats", False):
                    print(json.dumps(msg, ensure_ascii=False), file=sys.stderr)
            else:
                print(json.dumps(msg, ensure_ascii=False), file=sys.stderr)
                rc = 1

    max_loss = getattr(args, "max_loss_tokens", None)
    if max_loss is not None:
        lost = content_token_loss(before, after)
        if lost > int(max_loss):
            msg = {
                "quality": "token_loss",
                "lost_tokens": lost,
                "max_loss_tokens": int(max_loss),
            }
            print(json.dumps(msg, ensure_ascii=False), file=sys.stderr)
            if getattr(args, "strict_loss", False):
                rc = 1
    return rc


def _read_input(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return pathlib.Path(args.file).read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _write_output(text: str, args: argparse.Namespace) -> None:
    out_path = getattr(args, "out", None)
    if out_path:
        pathlib.Path(out_path).write_text(
            text if text.endswith("\n") else text + "\n", encoding="utf-8"
        )
    else:
        print(text)


def _resolve_zip_key(args: argparse.Namespace) -> str | None:
    key = getattr(args, "key", None)
    if getattr(args, "key_file", None):
        key = pathlib.Path(args.key_file).read_text(encoding="utf-8").rstrip("\r\n")
    if not key:
        key = os.environ.get("TALKCOMPRESS_ZIP_KEY") or None
    return key


def _sample_delta(before: str, after: str, limit: int = 48) -> str:
    """Short note on what changed (first differing snippet)."""
    if before == after:
        return "="
    # find first differing index
    n = min(len(before), len(after))
    i = 0
    while i < n and before[i] == after[i]:
        i += 1
    b_snip = before[i : i + limit].replace("\n", "⏎")
    a_snip = after[i : i + limit].replace("\n", "⏎")
    return f"@{i}: {b_snip!r}→{a_snip!r}"


def _run_a(text: str, args: argparse.Namespace, *, decode: bool = False) -> str:
    """A: shared RuleBook shortenings, optionally wrapped in MAC envelope.

    --rule-state alone → rule encode/decode.
    --key alone → classic envelope.
    both → rule-encode then envelope (or unwrap then rule-decode).
    """
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = _resolve_zip_key(args)
    rule_state = getattr(args, "rule_state", None)
    aad = getattr(args, "aad", None) or ""
    if not key and not rule_state:
        raise SystemExit(
            "layer 1 / Zipilogue requires --rule-state and/or --key/--key-file/TALKCOMPRESS_ZIP_KEY"
        )

    rb_mod = None
    book = None
    if rule_state:
        rb_mod = _load("zipilogue_rulebook", "Zipilogue/rulebook.py")
        book = rb_mod.RuleBook.load(rule_state)

    if decode:
        plain = text
        if key:
            plain = z.decode(text.strip().encode("ascii"), key=key, aad=aad).decode(
                "utf-8", errors="replace"
            )
        if book is not None:
            plain = book.decode_with_rules(plain)
        return plain

    payload = text
    if book is not None:
        # observe so counts grow when DensityZip routes through A with a RuleBook
        book.observe(payload)
        payload = book.encode_with_rules(payload)
        book.save()
    if key:
        return z.encode(payload.encode("utf-8"), key=key, aad=aad).decode("ascii")
    return payload


def _run_b(text: str, args: argparse.Namespace) -> str:
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    mode = getattr(args, "mode", None) or "compress"
    langs = None
    if args.langs:
        langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    rle = not getattr(args, "no_rle", False)
    pn = getattr(args, "preserve_newlines", False)
    pl = getattr(args, "prefer_ltr", False)
    tm = bool(getattr(args, "translate_min", False))
    bank = getattr(args, "translation_bank", None) or None
    te = getattr(args, "translate_engine", None) or "fixture"
    if getattr(args, "stats", False) and mode != "expand":
        print(json.dumps(t.stats(text, langs, prefer_ltr=pl), ensure_ascii=False), file=sys.stderr)
    if mode == "tag":
        if tm:
            text = t.minify_by_translation(
                text, bank_path=bank, preserve_newlines=pn, translate_engine=te
            )
        return t.render(t.tag_sentences(text, langs, preserve_newlines=pn, prefer_ltr=pl))
    if mode == "expand":
        return t.expand(text, preserve_newlines=pn)
    return t.compress(
        text,
        langs,
        rle=rle,
        preserve_newlines=pn,
        prefer_ltr=pl,
        translate_min=tm,
        translation_bank=bank,
        translate_engine=te,
    )


def _run_c(text: str, args: argparse.Namespace) -> str:
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    sess = s.Session()
    packs = getattr(args, "pack", None)
    if packs:
        # profile may set pack as a single string
        if isinstance(packs, str):
            packs = [packs]
        sess.load_packs(list(packs))
    lexicon = getattr(args, "lexicon", None)
    if lexicon:
        sess.load_lexicon(lexicon)
    if args.state and pathlib.Path(args.state).exists():
        sess.load(args.state)
    mode = getattr(args, "mode", None) or "compress"
    if mode == "expand":
        return s.expand(text, session=sess)
    out = s.compress(text, session=sess)
    if args.state:
        sess.save(args.state)
    export = getattr(args, "export_lexicon", None)
    if export:
        sess.export_lexicon_to(export)
    return out


def _run_e(text: str, args: argparse.Namespace) -> str:
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    mode = getattr(args, "mode", None) or "compress"
    if mode == "expand":
        return m.expand(text, counters=not getattr(args, "no_counters", False))
    if mode == "pack":
        return m.pack_tokens(text)
    protect = getattr(args, "protect_regex", None)
    if isinstance(protect, str):
        protect = [protect]
    # E default: no filler strip (C owns fillers). --strip / --aggressive-fillers opt in.
    want_strip = bool(getattr(args, "strip", False)) or bool(
        getattr(args, "aggressive_fillers", False)
    )
    if getattr(args, "no_strip", False):
        want_strip = False
    out = m.compress(
        text,
        strip=want_strip,
        unique=not getattr(args, "no_unique", False),
        etymon=not getattr(args, "no_etymon", False),
        aggressive_fillers=getattr(args, "aggressive_fillers", False),
        counters=not getattr(args, "no_counters", False),
        spelled_nums=getattr(args, "spelled_nums", False),
        keep_articles=getattr(args, "keep_articles", False),
        hex_nums=getattr(args, "hex_nums", False),
        hex_prefix=not getattr(args, "hex_bare", False),
        protect_regexes=protect,
    )
    if getattr(args, "stats", False):
        print(json.dumps(m.density(text, out), ensure_ascii=False), file=sys.stderr)
    return out


def _run_final_zh_de(text: str, args: argparse.Namespace) -> str:
    """B final token pass — compounds/ZH densifiers + ES/FR tense + zh|de minify."""
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    bank = getattr(args, "translation_bank", None) or None
    if isinstance(bank, str) and not bank.strip():
        bank = None
    phrase = getattr(args, "zh_de_phrase_bank", None) or None
    if isinstance(phrase, str) and not str(phrase).strip():
        phrase = None
    tense = getattr(args, "es_fr_tense_bank", None) or None
    if isinstance(tense, str) and not str(tense).strip():
        tense = None
    te = getattr(args, "translate_engine", None) or "fixture"
    pn = bool(getattr(args, "preserve_newlines", False))
    return t.final_zh_de_token_pass(
        text,
        phrase_bank=phrase,
        tense_bank=tense,
        translation_bank=bank,
        preserve_newlines=pn,
        translate_engine=te,
    )


def transform_line(
    layer: str,
    text: str,
    args: argparse.Namespace,
    *,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    if layer in ("identity", "skip"):
        if trace is not None:
            trace.append(
                {
                    "step": len(trace),
                    "layer": "identity",
                    "chars_before": len(text),
                    "chars_after": len(text),
                    "sample_delta": "=",
                }
            )
        return text
    before = text
    if layer == "A":
        out = _run_a(text, args, decode=(getattr(args, "mode", None) == "decode"))
    elif layer == "B":
        out = _run_b(text, args)
    elif layer == "C":
        out = _run_c(text, args)
    elif layer == "E":
        out = _run_e(text, args)
    elif layer == FINAL_ZH_DE_STEP:
        out = _run_final_zh_de(text, args)
    else:
        raise SystemExit(f"unhandled layer: {layer}")
    if trace is not None:
        trace.append(
            {
                "step": len(trace),
                "layer": layer,
                "chars_before": len(before),
                "chars_after": len(out),
                "sample_delta": _sample_delta(before, out),
            }
        )
    return out


def with_final_zh_de(layers: list[str], args: argparse.Namespace) -> list[str]:
    """Append ``B-final-zh-de`` when ``--final-zh-de``/``--final-token`` (or auto) asks for it.

    ``--no-final-zh-de`` always suppresses. Explicit pipeline already containing
    the step is left unchanged. ``--auto`` enables via ``choose_auto_layers``.
    """
    out = list(layers)
    if getattr(args, "no_final_zh_de", False):
        return [x for x in out if x != FINAL_ZH_DE_STEP]
    want = bool(getattr(args, "final_zh_de", False)) or bool(getattr(args, "auto", False))
    if want and FINAL_ZH_DE_STEP not in out:
        out.append(FINAL_ZH_DE_STEP)
    return out


def run_pipeline(
    layers: list[str],
    text: str,
    args: argparse.Namespace,
    *,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Run layers in sequence on the same text. A without key errors clearly."""
    if "A" in layers:
        if not _resolve_zip_key(args) and not getattr(args, "rule_state", None):
            raise SystemExit(
                "pipeline includes A (Zipilogue) but no --rule-state and/or "
                "--key/--key-file/TALKCOMPRESS_ZIP_KEY"
            )
    out = text
    saved_mode = getattr(args, "mode", None)
    for layer in layers:
        if layer == "identity":
            out = transform_line(layer, out, args, trace=trace)
            continue
        if layer == "A":
            args.mode = "encode"
        else:
            args.mode = "compress"
        out = transform_line(layer, out, args, trace=trace)
    args.mode = saved_mode
    return out


def run_budget(
    text: str,
    args: argparse.Namespace,
    *,
    budget: int,
    layers: list[str] | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Keep applying pipeline until len(text) <= budget or no further shrink; return shortest."""
    pipe = layers or parse_pipeline(getattr(args, "pipeline", None) or "C,E")
    # If user only set --budget without --pipeline, default C,E
    if len(text) <= budget:
        if getattr(args, "stats", False):
            print(
                json.dumps(
                    {
                        "chars_before": len(text),
                        "chars_after": len(text),
                        "steps": 0,
                        "budget": budget,
                        "under_budget": True,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        return text

    current = text
    best = text
    steps = 0
    max_rounds = 8
    for _ in range(max_rounds):
        if len(current) <= budget:
            break
        nxt = run_pipeline(pipe, current, args, trace=trace)
        steps += 1
        if len(nxt) < len(best):
            best = nxt
        if len(nxt) >= len(current):
            # no further shrink
            break
        current = nxt
        if len(current) <= budget:
            break

    if getattr(args, "stats", False):
        print(
            json.dumps(
                {
                    "chars_before": len(text),
                    "chars_after": len(best),
                    "steps": steps,
                    "budget": budget,
                    "under_budget": len(best) <= budget,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
    return best


def choose_auto_layers(text: str, args: argparse.Namespace) -> list[str]:
    """Heuristic auto layer pick among B/C/E (+ optional A with --auto-machine)."""
    if not text.strip():
        return ["C"]

    n = len(text)
    ascii_letters = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]", text))
    scripts = 0
    if latin:
        scripts += 1
    if cjk:
        scripts += 1
    if re.search(r"[\u0400-\u04FF]", text):
        scripts += 1
    if re.search(r"[\uAC00-\uD7AF]", text):
        scripts += 1

    sentences = len(re.findall(r"[.!?。？！]", text)) + (1 if text.strip() else 0)
    slangish = bool(
        re.search(
            r"\b(lol|omg|idk|brb|asap|fyi|btw|imo|tbh|nvm|pls|thx|u|ur)\b",
            text,
            re.I,
        )
    ) or bool(re.search(r"(よろしく|ありがとう|すみません|了解)", text))

    cjk_density = cjk / max(n, 1)
    ascii_ratio = ascii_letters / max(n, 1)

    layers: list[str]
    if n <= 24 and cjk_density > 0.4:
        layers = ["E"]
    elif slangish and ascii_ratio > 0.5:
        layers = ["C", "E"]
    elif scripts >= 2 or (sentences >= 3 and scripts >= 1 and cjk > 0 and latin > 0):
        layers = ["B", "E"]
    elif cjk_density > 0.55:
        layers = ["E"]
    elif ascii_ratio > 0.7:
        layers = ["C", "E"]
    else:
        layers = ["C", "E"]

    if getattr(args, "auto_machine", False) and _resolve_zip_key(args):
        layers = layers + ["A"]
    # Default end of --auto: ZH/DE token densify (unless --no-final-zh-de)
    if not getattr(args, "no_final_zh_de", False):
        if FINAL_ZH_DE_STEP not in layers:
            layers = layers + [FINAL_ZH_DE_STEP]
    return layers


def compare_layers(text: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Run C, E (and optionally B compress) on the same input; return density rows."""
    rows: list[dict[str, Any]] = []
    before = len(text)

    c_out = _run_c(text, args)
    rows.append(
        {
            "layer": "C",
            "name": "ShorthandEdge",
            "chars_before": before,
            "chars_after": len(c_out),
            "ratio": round(len(c_out) / before, 4) if before else 0.0,
            "preview": c_out[:80],
        }
    )

    e_out = _run_e(text, args)
    rows.append(
        {
            "layer": "E",
            "name": "MorphoZip",
            "chars_before": before,
            "chars_after": len(e_out),
            "ratio": round(len(e_out) / before, 4) if before else 0.0,
            "preview": e_out[:80],
        }
    )

    b_out = _run_b(text, args)
    rows.append(
        {
            "layer": "B",
            "name": "TesseraTalk",
            "chars_before": before,
            "chars_after": len(b_out),
            "ratio": round(len(b_out) / before, 4) if before else 0.0,
            "preview": b_out[:80],
        }
    )

    pipe = run_pipeline(["C", "E"], text, args)
    rows.append(
        {
            "layer": "C,E",
            "name": "pipeline",
            "chars_before": before,
            "chars_after": len(pipe),
            "ratio": round(len(pipe) / before, 4) if before else 0.0,
            "preview": pipe[:80],
        }
    )
    return rows


def _apply_for_body(
    body: str,
    args: argparse.Namespace,
    *,
    role: str | None = None,
    role_map: dict[str, str | list[str]] | None = None,
    default_layers: list[str] | None = None,
    default_layer: str | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Choose transform for one body given role-layers / pipeline / layer."""
    if role_map and role is not None:
        key = role.lower()
        if key in role_map:
            spec = role_map[key]
            if isinstance(spec, list):
                return run_pipeline(spec, body, args, trace=trace)
            return transform_line(str(spec), body, args, trace=trace)
        # unknown role → fall back
    if default_layers:
        return run_pipeline(default_layers, body, args, trace=trace)
    if default_layer:
        return transform_line(default_layer, body, args, trace=trace)
    return transform_line("C", body, args, trace=trace)


def process_jsonl(
    raw: str,
    args: argparse.Namespace,
    *,
    role_map: dict[str, str | list[str]] | None = None,
    default_layers: list[str] | None = None,
    default_layer: str | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Each line: plain text, or JSON role/text. Optional window/budget after compress.

    Precedence: per-line compress first (layer/pipeline/role-layers/auto), then
    drop oldest via ``--window`` / ``--budget``. ``--keep-system`` retains system rows.
    """
    rows_in = _parse_jsonl_rows(raw)
    transformed_rows: list[dict[str, Any]] = []
    for row in rows_in:
        role = row.get("role")
        body = str(row.get("text") or "")
        transformed = _apply_for_body(
            body,
            args,
            role=str(role) if role is not None else None,
            role_map=role_map,
            default_layers=default_layers,
            default_layer=default_layer,
            trace=trace,
        )
        transformed_rows.append({"role": role, "text": transformed})

    window = getattr(args, "window", None)
    budget = getattr(args, "budget", None) if getattr(args, "jsonl", False) else None
    # When jsonl + budget: budget applies as sliding char budget (drop oldest), not
    # the iterative pipeline budget used for plain text.
    keep_system = getattr(args, "keep_system", False)
    if getattr(args, "hist_state", False) and window is not None:
        # G2: old rows become one state block (placed after system rows); the last
        # `window` rows stay verbatim. A budget, if set, still drops oldest afterwards.
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.hist_state import summarize_old

        transformed_rows, _, _ = summarize_old(transformed_rows, window)
        window = None
    if window is not None or (budget is not None and getattr(args, "jsonl", False)):
        transformed_rows = apply_window(
            transformed_rows,
            window=window,
            budget=budget,
            keep_system=keep_system,
        )

    outs: list[str] = []
    for row in transformed_rows:
        role = row.get("role")
        transformed = str(row.get("text") or "")
        if role is not None:
            outs.append(json.dumps({"role": role, "text": transformed}, ensure_ascii=False))
        else:
            outs.append(transformed)
    return "\n".join(outs)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="DensityZip: density façade + route TalkCompress layers A–E / 1–4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  uv run python DensityZip/density_zip.py --layer 3 --text "as soon as possible"
  uv run python DensityZip/density_zip.py --pipeline C,E --text "um thank you for your information"
  uv run python DensityZip/density_zip.py --budget 40 --text "um thank you for your information please"
  uv run python DensityZip/density_zip.py --auto --text "Hello. こんにちは。Thanks a lot."
  uv run python DensityZip/density_zip.py --compare --text "I have 3 animals and 2 people"
  uv run python DensityZip/density_zip.py --profile mcp-short --text "um thank you"
  uv run python DensityZip/density_zip.py --pipeline C,E --jsonl --window 3 --keep-system --file examples/window_chat.jsonl
""",
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument(
        "--layer",
        help="1–4, A–E, or names: zipilogue|tessera|shorthand|density|morpho",
    )
    g.add_argument(
        "--pipeline",
        help="comma-separated layers to run in sequence (e.g. C,E). A needs --key",
    )
    g.add_argument(
        "--compare",
        "--demo-compare",
        dest="compare",
        action="store_true",
        help="run C/E/B and C→E on the same input; print JSON lines of char ratios",
    )
    g.add_argument(
        "--auto",
        action="store_true",
        help="heuristic auto pick among B/C/E (and C,E pipeline when helpful)",
    )
    p.add_argument(
        "--budget",
        type=int,
        default=None,
        help="keep applying default/given pipeline until len<=N or no shrink; return shortest",
    )
    p.add_argument(
        "--role-layers",
        default=None,
        help="with --jsonl: per-role layer/pipeline, e.g. user=C,assistant=E,system=identity "
        "(use + for multi-step: user=C+E)",
    )
    p.add_argument(
        "--trace",
        action="store_true",
        help="emit JSON transform steps to stderr",
    )
    p.add_argument(
        "--auto-machine",
        action="store_true",
        help="with --auto: append A (Zipilogue) when a key is available",
    )
    p.add_argument("--text", help="input text; otherwise --file or stdin")
    p.add_argument("--file", help="read UTF-8 input from PATH")
    p.add_argument("--out", help="write result to PATH instead of stdout")
    p.add_argument("--jsonl", action="store_true", help="treat input as JSONL conversation")
    p.add_argument(
        "--mode",
        choices=("compress", "expand", "tag", "encode", "decode", "pack"),
        default=None,
        help="layer-specific mode (default: compress/encode)",
    )
    p.add_argument("--key", help="Zipilogue passphrase")
    p.add_argument("--key-file", help="Zipilogue passphrase file")
    p.add_argument(
        "--rule-state",
        dest="rule_state",
        help="Zipilogue RuleBook JSON path (shared-rule slang ledger; key optional)",
    )
    p.add_argument(
        "--aad",
        default="",
        help="Zipilogue associated context / channel label (folded into MAC)",
    )
    p.add_argument("--langs", help="TesseraTalk fallback langs (comma-separated)")
    p.add_argument("--no-rle", action="store_true", help="TesseraTalk: disable RLE mosaic")
    p.add_argument(
        "--preserve-newlines",
        action="store_true",
        help="TesseraTalk: keep blank-line paragraph breaks",
    )
    p.add_argument("--state", help="ShorthandEdge session JSON path")
    p.add_argument("--lexicon", help="ShorthandEdge extra lexicon JSON to merge")
    p.add_argument(
        "--export-lexicon",
        dest="export_lexicon",
        help="ShorthandEdge: dump effective lexicon JSON to PATH after compress",
    )
    p.add_argument("--stats", action="store_true", help="MorphoZip/TesseraTalk/budget stats on stderr")
    p.add_argument(
        "--strip",
        action="store_true",
        help="MorphoZip: opt-in filler strip (default off; C owns fillers)",
    )
    p.add_argument(
        "--no-strip",
        action="store_true",
        help="MorphoZip: force keep fillers (overrides --strip / profile)",
    )
    p.add_argument("--no-unique", action="store_true", help="MorphoZip: skip unique-reading")
    p.add_argument("--no-etymon", action="store_true", help="MorphoZip: skip etymon align")
    p.add_argument("--no-counters", action="store_true", help="MorphoZip: skip counter map")
    p.add_argument(
        "--keep-articles",
        action="store_true",
        help="MorphoZip: keep English articles the/a/an (default strips unquoted)",
    )
    p.add_argument(
        "--spelled-nums",
        action="store_true",
        help="MorphoZip opt-in: spelled number words → digits (default off; C owns this)",
    )
    p.add_argument(
        "--aggressive-fillers",
        action="store_true",
        help="MorphoZip: opt-in aggressive filler strip (implies strip)",
    )
    p.add_argument("--hex-nums", action="store_true", help="MorphoZip: integers → hex")
    p.add_argument("--hex-bare", action="store_true", help="MorphoZip: bare hex (no 0x)")
    p.add_argument(
        "--lex-policy",
        help="JSON path to override shared FILLERS/UNIQUE/ETYMON (process-local)",
    )
    p.add_argument(
        "--window",
        type=int,
        default=None,
        help="with --jsonl: keep only the last N messages after compress "
        "(then --budget drops oldest further). See docs for precedence.",
    )
    p.add_argument(
        "--keep-system",
        action="store_true",
        help="with --window/--budget on JSONL: never drop role=system lines",
    )
    p.add_argument(
        "--hist-state",
        action="store_true",
        help="with --jsonl and --window: replace the old rows with one state block "
        "(decisions / open / ids / next / cleared tool rows) instead of dropping them (G2)",
    )
    p.add_argument(
        "--profile",
        default=None,
        help="load profiles/<NAME>.json (CLI flags override profile values)",
    )
    p.add_argument(
        "--profile-file",
        default=None,
        help="load a profile JSON from PATH",
    )
    p.add_argument(
        "--pack",
        action="append",
        default=None,
        dest="pack",
        help="ShorthandEdge domain pack (repeatable: dev, mcp)",
    )
    p.add_argument(
        "--protect-regex",
        action="append",
        default=None,
        dest="protect_regex",
        help="MorphoZip: regex matches left unchanged (repeatable); also [[keep:...]]",
    )
    p.add_argument(
        "--prefer-ltr",
        action="store_true",
        help="TesseraTalk: bias Latin+CJK mixes toward en rather than zh",
    )
    p.add_argument(
        "--translate-min",
        action="store_true",
        help="TesseraTalk: adopt shorter bank translation per sentence when tokens drop (any in-scope lang)",
    )
    p.add_argument(
        "--translation-bank",
        default="",
        help="TesseraTalk: optional translation candidates JSON path",
    )
    p.add_argument(
        "--translate-engine",
        default="fixture",
        choices=("fixture", "argos", "deep"),
        help="TesseraTalk: fixture=bank only (default); argos/deep=opt-in live MT if installed",
    )
    p.add_argument(
        "--final-zh-de",
        "--final-token",
        dest="final_zh_de",
        action="store_true",
        help="append B-final-token / B-final-zh-de (phrase candidates + ES/FR tense + zh|de) as last step; on by default with --auto",
    )
    p.add_argument(
        "--no-final-zh-de",
        "--no-final-token",
        dest="no_final_zh_de",
        action="store_true",
        help="suppress the final token pass (overrides --final-zh-de/--final-token / --auto default)",
    )
    p.add_argument(
        "--zh-de-phrase-bank",
        default="",
        help="optional final-token phrase bank JSON (compounds/ZH/EN acronyms)",
    )
    p.add_argument(
        "--es-fr-tense-bank",
        default="",
        help="optional ES/FR tense bank JSON (default: TesseraTalk fixtures)",
    )

    p.add_argument(
        "--min-ratio",
        type=float,
        default=None,
        help="fail (exit 1) if chars_after/chars_before > R unless --allow-weak",
    )
    p.add_argument(
        "--allow-weak",
        action="store_true",
        help="with --min-ratio: warn (on --stats) instead of failing",
    )
    p.add_argument(
        "--max-loss-tokens",
        type=int,
        default=None,
        help="experimental: warn if stripping removed >K content-ish tokens",
    )
    p.add_argument(
        "--strict-loss",
        action="store_true",
        help="with --max-loss-tokens: exit 1 on excess token loss",
    )
    p.add_argument(
        "--fingerprint-key",
        action="store_true",
        help="print Zipilogue key fingerprint to stderr and exit 0 (needs key)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else None
    p = build_parser()
    args = p.parse_args(argv_list)

    # Track CLI-explicit dests so profile values do not clobber user flags.
    cli_explicit: set[str] = set()
    if argv_list is None:
        argv_list = sys.argv[1:]
    # Rough parse of option dests present on CLI
    opt_map = {
        "--layer": "layer",
        "--pipeline": "pipeline",
        "--compare": "compare",
        "--demo-compare": "compare",
        "--auto": "auto",
        "--budget": "budget",
        "--role-layers": "role_layers",
        "--trace": "trace",
        "--auto-machine": "auto_machine",
        "--aggressive-fillers": "aggressive_fillers",
        "--no-rle": "no_rle",
        "--preserve-newlines": "preserve_newlines",
        "--prefer-ltr": "prefer_ltr",
        "--translate-min": "translate_min",
        "--translation-bank": "translation_bank",
        "--translate-engine": "translate_engine",
        "--final-zh-de": "final_zh_de",
        "--final-token": "final_zh_de",
        "--no-final-zh-de": "no_final_zh_de",
        "--no-final-token": "no_final_zh_de",
        "--zh-de-phrase-bank": "zh_de_phrase_bank",
        "--es-fr-tense-bank": "es_fr_tense_bank",
        "--hex-nums": "hex_nums",
        "--hex-bare": "hex_bare",
        "--strip": "strip",
        "--no-strip": "no_strip",
        "--no-unique": "no_unique",
        "--no-etymon": "no_etymon",
        "--no-counters": "no_counters",
        "--keep-articles": "keep_articles",
        "--spelled-nums": "spelled_nums",
        "--langs": "langs",
        "--aad": "aad",
        "--lexicon": "lexicon",
        "--lex-policy": "lex_policy",
        "--pack": "pack",
        "--protect-regex": "protect_regex",
        "--min-ratio": "min_ratio",
        "--max-loss-tokens": "max_loss_tokens",
        "--allow-weak": "allow_weak",
        "--strict-loss": "strict_loss",
        "--stats": "stats",
        "--window": "window",
        "--keep-system": "keep_system",
        "--mode": "mode",
        "--jsonl": "jsonl",
        "--key": "key",
        "--key-file": "key_file",
    }
    i = 0
    while i < len(argv_list):
        tok = argv_list[i]
        if tok in opt_map:
            cli_explicit.add(opt_map[tok])
        elif "=" in tok and tok.startswith("--"):
            cli_explicit.add(opt_map.get(tok.split("=", 1)[0], tok.split("=", 1)[0].lstrip("-").replace("-", "_")))
        i += 1

    if getattr(args, "profile", None) or getattr(args, "profile_file", None):
        profile = load_profile(args.profile, args.profile_file)
        apply_profile(args, profile, cli_explicit=cli_explicit)

    # Ensure attrs exist even when profile not used
    for attr, default in (
        ("window", None),
        ("keep_system", False),
        ("pack", None),
        ("protect_regex", None),
        ("prefer_ltr", False),
        ("translate_min", False),
        ("translation_bank", ""),
        ("translate_engine", "fixture"),
        ("final_zh_de", False),
        ("no_final_zh_de", False),
        ("zh_de_phrase_bank", ""),
        ("es_fr_tense_bank", ""),
        ("min_ratio", None),
        ("allow_weak", False),
        ("max_loss_tokens", None),
        ("strict_loss", False),
        ("fingerprint_key", False),
        ("profile", None),
        ("profile_file", None),
        ("rule_state", None),
    ):
        if not hasattr(args, attr):
            setattr(args, attr, default)

    if getattr(args, "fingerprint_key", False):
        key = _resolve_zip_key(args)
        if not key:
            raise SystemExit("--fingerprint-key requires --key, --key-file, or TALKCOMPRESS_ZIP_KEY")
        z = _load("zipilogue", "Zipilogue/zipilogue.py")
        fp = z.key_fingerprint(key)
        print(fp, file=sys.stderr)
        return 0

    if not any(
        [
            args.layer,
            args.pipeline,
            args.compare,
            args.auto,
            args.budget is not None,
            args.role_layers,
            getattr(args, "window", None) is not None,
            getattr(args, "profile", None),
            getattr(args, "profile_file", None),
        ]
    ):
        p.error(
            "one of --layer / --pipeline / --compare / --auto / --budget / "
            "--role-layers / --window / --profile is required"
        )

    # machine profile without key/rule-state: fail clearly
    if args.layer and resolve_layer(str(args.layer)) == "A":
        if not _resolve_zip_key(args) and not getattr(args, "rule_state", None):
            if getattr(args, "mode", None) != "decode":
                raise SystemExit(
                    "profile/layer A (Zipilogue) requires --rule-state and/or "
                    "--key/--key-file/TALKCOMPRESS_ZIP_KEY"
                )

    if getattr(args, "lex_policy", None):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.lex_policy import load_policy

        load_policy(args.lex_policy)

    raw = _read_input(args)
    before_raw = raw
    trace: list[dict[str, Any]] | None = [] if args.trace else None
    role_map = parse_role_layers(args.role_layers) if args.role_layers else None

    if args.compare:
        args.mode = "compress"
        rows = compare_layers(raw, args)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return 0

    # Budget mode for plain text (JSONL budget is window-style drop-oldest)
    if args.budget is not None and not args.jsonl:
        layers: list[str] | None = None
        if args.pipeline:
            layers = with_final_zh_de(parse_pipeline(args.pipeline), args)
        elif args.auto:
            layers = choose_auto_layers(raw, args)
        elif args.layer:
            layers = with_final_zh_de([resolve_layer(args.layer)], args)
        out = run_budget(raw, args, budget=args.budget, layers=layers, trace=trace)
        if trace is not None:
            print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
        _write_output(out, args)
        return check_quality(before_raw, out, args)

    if args.auto and not args.jsonl:
        layers = choose_auto_layers(raw, args)
        out = run_pipeline(layers, raw, args, trace=trace)
        if getattr(args, "stats", False):
            print(
                json.dumps({"auto_layers": layers, "chars_after": len(out)}, ensure_ascii=False),
                file=sys.stderr,
            )
        if trace is not None:
            print(json.dumps({"trace": trace, "auto_layers": layers}, ensure_ascii=False), file=sys.stderr)
        _write_output(out, args)
        return check_quality(before_raw, out, args)

    default_layers: list[str] | None = None
    default_layer: str | None = None
    if args.pipeline:
        default_layers = with_final_zh_de(parse_pipeline(args.pipeline), args)
    elif args.auto:
        default_layers = choose_auto_layers(raw, args)
    elif args.layer:
        default_layer = resolve_layer(args.layer)
        if default_layer == "D":
            p.error("D (DensityZip) is this router; pick A–C or E / layers 1–4")
    elif role_map:
        default_layer = "C"
    elif getattr(args, "window", None) is not None:
        default_layer = "C"
    else:
        p.error("need --layer, --pipeline, --auto, --budget, --role-layers, or --window")

    if args.mode is None and default_layer == "A":
        args.mode = "encode"
    elif args.mode is None and default_layer:
        args.mode = "compress"
    if default_layer == "A" and args.mode == "compress":
        args.mode = "encode"
    if default_layer == "A" and args.mode == "expand":
        args.mode = "decode"

    if args.jsonl:
        out = process_jsonl(
            raw,
            args,
            role_map=role_map,
            default_layers=default_layers,
            default_layer=default_layer,
            trace=trace,
        )
        if trace is not None:
            print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
        _write_output(out, args)
        return check_quality(before_raw, out, args)

    # The final ZH/DE pass is compress-only; promoting to a pipeline would make
    # run_pipeline overwrite expand/tag/pack/decode with compress/encode.
    if (
        default_layers is None
        and default_layer is not None
        and args.mode in ("compress", "encode")
    ):
        maybe = with_final_zh_de([default_layer], args)
        if len(maybe) > 1 or (maybe and maybe[-1] == FINAL_ZH_DE_STEP and default_layer != FINAL_ZH_DE_STEP):
            default_layers = maybe
            default_layer = None
    if default_layers:
        out = run_pipeline(default_layers, raw, args, trace=trace)
    else:
        assert default_layer is not None
        out = transform_line(default_layer, raw, args, trace=trace)
    if trace is not None:
        print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
    _write_output(out, args)
    return check_quality(before_raw, out, args)




if __name__ == "__main__":
    raise SystemExit(main())
