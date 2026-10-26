#!/usr/bin/env python3
"""ConvoZip (D): cross-layer router / shared CLI for TalkCompress A–E.

Supports single ``--layer``, sequential ``--pipeline C,E``, file I/O,
and ``--compare`` density tables across layers.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
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
        if layer not in ("A", "B", "C", "E"):
            raise SystemExit(f"unknown pipeline layer: {layer}")
    return layers


def _read_input(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return pathlib.Path(args.file).read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _write_output(text: str, args: argparse.Namespace) -> None:
    out_path = getattr(args, "out", None)
    if out_path:
        pathlib.Path(out_path).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    else:
        print(text)


def _run_a(text: str, args: argparse.Namespace, *, decode: bool = False) -> str:
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = args.key
    if args.key_file:
        key = pathlib.Path(args.key_file).read_text(encoding="utf-8").rstrip("\r\n")
    if not key:
        raise SystemExit("layer 1 / Zipilogue requires --key or --key-file")
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
    if getattr(args, "stats", False) and mode != "expand":
        print(json.dumps(t.stats(text, langs), ensure_ascii=False), file=sys.stderr)
    if mode == "tag":
        return t.render(t.tag_sentences(text, langs))
    if mode == "expand":
        return t.expand(text)
    return t.compress(text, langs, rle=rle)


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
    return out


def _run_e(text: str, args: argparse.Namespace) -> str:
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
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


def transform_line(layer: str, text: str, args: argparse.Namespace) -> str:
    if layer == "A":
        return _run_a(text, args, decode=(getattr(args, "mode", None) == "decode"))
    if layer == "B":
        return _run_b(text, args)
    if layer == "C":
        return _run_c(text, args)
    if layer == "E":
        return _run_e(text, args)
    raise SystemExit(f"unhandled layer: {layer}")


def run_pipeline(layers: list[str], text: str, args: argparse.Namespace) -> str:
    """Run layers in sequence on the same text. A without key errors clearly."""
    if "A" in layers:
        key = args.key
        if args.key_file:
            key = key or pathlib.Path(args.key_file).read_text(encoding="utf-8").rstrip("\r\n")
        if not key:
            raise SystemExit(
                "pipeline includes A (Zipilogue) but no --key/--key-file was provided"
            )
    out = text
    # Pipeline always compresses/encodes each stage (expand would need reverse order)
    saved_mode = getattr(args, "mode", None)
    for layer in layers:
        if layer == "A":
            args.mode = "encode"
        else:
            args.mode = "compress"
        out = transform_line(layer, out, args)
    args.mode = saved_mode
    return out


def compare_layers(text: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Run C, E (and optionally B compress) on the same input; return density rows."""
    rows: list[dict[str, Any]] = []
    before = len(text)

    # C ShorthandLab
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

    # E MorphoZip
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

    # B TesseraTalk compress (optional mosaic length)
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

    # Pipeline C→E
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


def process_jsonl(layer: str, raw: str, args: argparse.Namespace) -> str:
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
        transformed = transform_line(layer, body, args)
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
  uv run python ConvoZip/convo_zip.py --compare --text "I have 3 animals and 2 people"
  uv run python ConvoZip/convo_zip.py --layer A --key secret --aad chat --file in.txt --out out.env
""",
    )
    g = p.add_mutually_exclusive_group(required=True)
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
    p.add_argument("--text", help="input text; otherwise --file or stdin")
    p.add_argument("--file", help="read UTF-8 input from PATH")
    p.add_argument("--out", help="write result to PATH instead of stdout")
    p.add_argument("--jsonl", action="store_true", help="treat input as JSONL conversation")
    p.add_argument(
        "--mode",
        choices=("compress", "expand", "tag", "encode", "decode"),
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
    p.add_argument("--state", help="ShorthandLab session JSON path")
    p.add_argument("--lexicon", help="ShorthandLab extra lexicon JSON to merge")
    p.add_argument("--stats", action="store_true", help="MorphoZip/TesseraTalk stats on stderr")
    p.add_argument("--no-strip", action="store_true", help="MorphoZip: keep fillers")
    p.add_argument("--no-unique", action="store_true", help="MorphoZip: skip unique-reading")
    p.add_argument("--no-etymon", action="store_true", help="MorphoZip: skip etymon align")
    p.add_argument("--no-counters", action="store_true", help="MorphoZip: skip counter map")
    p.add_argument("--aggressive-fillers", action="store_true", help="MorphoZip aggressive fillers")
    p.add_argument("--hex-nums", action="store_true", help="MorphoZip: integers → hex")
    p.add_argument("--hex-bare", action="store_true", help="MorphoZip: bare hex (no 0x)")
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)

    raw = _read_input(args)

    if args.compare:
        # Force compress mode for compare
        args.mode = "compress"
        rows = compare_layers(raw, args)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return 0

    if args.pipeline:
        layers = parse_pipeline(args.pipeline)
        if args.jsonl:
            # JSONL: apply pipeline per line body
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
                        body = str(
                            obj.get("text") or obj.get("content") or obj.get("message") or ""
                        )
                transformed = run_pipeline(layers, body, args)
                if role is not None:
                    outs.append(
                        json.dumps({"role": role, "text": transformed}, ensure_ascii=False)
                    )
                else:
                    outs.append(transformed)
            _write_output("\n".join(outs), args)
        else:
            _write_output(run_pipeline(layers, raw, args), args)
        return 0

    layer = resolve_layer(args.layer)
    if layer == "D":
        p.error("D is this router; pick A–C or E / layers 1–4")

    if args.mode is None:
        if layer == "A":
            args.mode = "encode"
        else:
            args.mode = "compress"
    if layer == "A" and args.mode == "compress":
        args.mode = "encode"
    if layer == "A" and args.mode == "expand":
        args.mode = "decode"

    if args.jsonl:
        _write_output(process_jsonl(layer, raw, args), args)
    else:
        _write_output(transform_line(layer, raw, args), args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
