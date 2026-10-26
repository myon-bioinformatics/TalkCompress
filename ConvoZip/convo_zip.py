#!/usr/bin/env python3
"""ConvoZip (D): cross-layer router / shared CLI for TalkCompress A–E.

Supports single ``--layer``, sequential ``--pipeline C,E``, ``--budget``,
``--role-layers``, ``--auto``, ``--trace``, file I/O, and ``--compare``.
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
    "shorthand_lab": "C",
    "convo": "D",
    "convo_zip": "D",
    "morpho": "E",
    "morpho_zip": "E",
    "identity": "identity",
    "skip": "identity",
}


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
    return _LAYER_ALIASES.get(key, _LAYER_ALIASES.get(key.lower(), key.upper()))


def parse_pipeline(raw: str) -> list[str]:
    """Parse comma-separated layer aliases into canonical A/B/C/E codes."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise SystemExit("--pipeline needs at least one layer (e.g. C,E)")
    layers = [resolve_layer(p) for p in parts]
    for layer in layers:
        if layer == "D":
            raise SystemExit("D is this router; omit from --pipeline")
        if layer == "identity":
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
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = _resolve_zip_key(args)
    if not key:
        raise SystemExit("layer 1 / Zipilogue requires --key, --key-file, or TALKCOMPRESS_ZIP_KEY")
    aad = getattr(args, "aad", None) or ""
    if decode:
        return z.decode(text.strip().encode("ascii"), key=key, aad=aad).decode(
            "utf-8", errors="replace"
        )
    return z.encode(text.encode("utf-8"), key=key, aad=aad).decode("ascii")


def _run_b(text: str, args: argparse.Namespace) -> str:
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    mode = getattr(args, "mode", None) or "compress"
    langs = None
    if args.langs:
        langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    rle = not getattr(args, "no_rle", False)
    pn = getattr(args, "preserve_newlines", False)
    if getattr(args, "stats", False) and mode != "expand":
        print(json.dumps(t.stats(text, langs), ensure_ascii=False), file=sys.stderr)
    if mode == "tag":
        return t.render(t.tag_sentences(text, langs, preserve_newlines=pn))
    if mode == "expand":
        return t.expand(text, preserve_newlines=pn)
    return t.compress(text, langs, rle=rle, preserve_newlines=pn)


def _run_c(text: str, args: argparse.Namespace) -> str:
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    sess = s.Session()
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
    out = m.compress(
        text,
        strip=not getattr(args, "no_strip", False),
        unique=not getattr(args, "no_unique", False),
        etymon=not getattr(args, "no_etymon", False),
        aggressive_fillers=getattr(args, "aggressive_fillers", False),
        counters=not getattr(args, "no_counters", False),
        hex_nums=getattr(args, "hex_nums", False),
        hex_prefix=not getattr(args, "hex_bare", False),
    )
    if getattr(args, "stats", False):
        print(json.dumps(m.density(text, out), ensure_ascii=False), file=sys.stderr)
    return out


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


def run_pipeline(
    layers: list[str],
    text: str,
    args: argparse.Namespace,
    *,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Run layers in sequence on the same text. A without key errors clearly."""
    if "A" in layers:
        if not _resolve_zip_key(args):
            raise SystemExit(
                "pipeline includes A (Zipilogue) but no --key/--key-file/TALKCOMPRESS_ZIP_KEY"
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
    latin = len(re.findall(r"[A-Za-z]", text))
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
    return layers


def compare_layers(text: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Run C, E (and optionally B compress) on the same input; return density rows."""
    rows: list[dict[str, Any]] = []
    before = len(text)

    c_out = _run_c(text, args)
    rows.append(
        {
            "layer": "C",
            "name": "ShorthandLab",
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
    """Each line: plain text, or JSON {\"role\": \"...\", \"text\": \"...\"} / {\"content\": \"...\"}."""
    outs: list[str] = []
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
        transformed = _apply_for_body(
            body,
            args,
            role=str(role) if role is not None else None,
            role_map=role_map,
            default_layers=default_layers,
            default_layer=default_layer,
            trace=trace,
        )
        if role is not None:
            outs.append(json.dumps({"role": role, "text": transformed}, ensure_ascii=False))
        else:
            outs.append(transformed)
    return "\n".join(outs)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ConvoZip: route TalkCompress layers A–E / 1–4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  uv run python ConvoZip/convo_zip.py --layer 3 --text "as soon as possible"
  uv run python ConvoZip/convo_zip.py --pipeline C,E --text "um thank you for your information"
  uv run python ConvoZip/convo_zip.py --budget 40 --text "um thank you for your information please"
  uv run python ConvoZip/convo_zip.py --auto --text "Hello. こんにちは。Thanks a lot."
  uv run python ConvoZip/convo_zip.py --compare --text "I have 3 animals and 2 people"
""",
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument(
        "--layer",
        help="1–4, A–E, or names: zipilogue|tessera|shorthand|morpho",
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
    p.add_argument("--state", help="ShorthandLab session JSON path")
    p.add_argument("--lexicon", help="ShorthandLab extra lexicon JSON to merge")
    p.add_argument(
        "--export-lexicon",
        dest="export_lexicon",
        help="ShorthandLab: dump effective lexicon JSON to PATH after compress",
    )
    p.add_argument("--stats", action="store_true", help="MorphoZip/TesseraTalk/budget stats on stderr")
    p.add_argument("--no-strip", action="store_true", help="MorphoZip: keep fillers")
    p.add_argument("--no-unique", action="store_true", help="MorphoZip: skip unique-reading")
    p.add_argument("--no-etymon", action="store_true", help="MorphoZip: skip etymon align")
    p.add_argument("--no-counters", action="store_true", help="MorphoZip: skip counter map")
    p.add_argument("--aggressive-fillers", action="store_true", help="MorphoZip aggressive fillers")
    p.add_argument("--hex-nums", action="store_true", help="MorphoZip: integers → hex")
    p.add_argument("--hex-bare", action="store_true", help="MorphoZip: bare hex (no 0x)")
    p.add_argument(
        "--lex-policy",
        help="JSON path to override shared FILLERS/UNIQUE/ETYMON (process-local)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)

    if not any(
        [
            args.layer,
            args.pipeline,
            args.compare,
            args.auto,
            args.budget is not None,
            args.role_layers,
        ]
    ):
        p.error("one of --layer / --pipeline / --compare / --auto / --budget / --role-layers is required")

    if getattr(args, "lex_policy", None):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.lex_policy import load_policy

        load_policy(args.lex_policy)

    raw = _read_input(args)
    trace: list[dict[str, Any]] | None = [] if args.trace else None
    role_map = parse_role_layers(args.role_layers) if args.role_layers else None

    if args.compare:
        args.mode = "compress"
        rows = compare_layers(raw, args)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return 0

    # Budget mode (may compose with pipeline / auto / role-layers for jsonl)
    if args.budget is not None and not args.jsonl:
        layers: list[str] | None = None
        if args.pipeline:
            layers = parse_pipeline(args.pipeline)
        elif args.auto:
            layers = choose_auto_layers(raw, args)
        elif args.layer:
            layers = [resolve_layer(args.layer)]
        out = run_budget(raw, args, budget=args.budget, layers=layers, trace=trace)
        if trace is not None:
            print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
        _write_output(out, args)
        return 0

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
        return 0

    default_layers: list[str] | None = None
    default_layer: str | None = None
    if args.pipeline:
        default_layers = parse_pipeline(args.pipeline)
    elif args.auto:
        # for jsonl without per-line auto, use a single auto choice on whole raw as fallback
        default_layers = choose_auto_layers(raw, args)
    elif args.layer:
        default_layer = resolve_layer(args.layer)
        if default_layer == "D":
            p.error("D is this router; pick A–C or E / layers 1–4")
    elif role_map:
        default_layer = "C"
    else:
        p.error("need --layer, --pipeline, --auto, --budget, or --role-layers")

    if args.mode is None and default_layer == "A":
        args.mode = "encode"
    elif args.mode is None and default_layer:
        args.mode = "compress"
    if default_layer == "A" and args.mode == "compress":
        args.mode = "encode"
    if default_layer == "A" and args.mode == "expand":
        args.mode = "decode"

    if args.jsonl:
        # role-layers wins per line when set; else pipeline/layer
        out = process_jsonl(
            raw,
            args,
            role_map=role_map,
            default_layers=default_layers,
            default_layer=default_layer,
            trace=trace,
        )
        if args.budget is not None:
            # post-budget on the joined text is ambiguous; apply per-line already done.
            # Optionally shrink further each line already transformed — skip.
            pass
        if trace is not None:
            print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
        _write_output(out, args)
        return 0

    if default_layers:
        out = run_pipeline(default_layers, raw, args, trace=trace)
    else:
        assert default_layer is not None
        out = transform_line(default_layer, raw, args, trace=trace)
    if trace is not None:
        print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
    _write_output(out, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
