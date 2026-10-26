#!/usr/bin/env python3
"""ConvoZip (D): cross-layer router / shared CLI for TalkCompress A–E."""

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


def _read_input(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _run_a(text: str, args: argparse.Namespace, *, decode: bool = False) -> str:
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    key = args.key
    if args.key_file:
        key = pathlib.Path(args.key_file).read_text(encoding="utf-8").rstrip("\r\n")
    if not key:
        raise SystemExit("layer 1 / Zipilogue requires --key or --key-file")
    if decode:
        return z.decode(text.strip().encode("ascii"), key=key).decode("utf-8", errors="replace")
    return z.encode(text.encode("utf-8"), key=key).decode("ascii")


def _run_b(text: str, args: argparse.Namespace) -> str:
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    mode = getattr(args, "mode", None) or "compress"
    langs = None
    if args.langs:
        langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    if mode == "tag":
        return t.render(t.tag_sentences(text, langs))
    if mode == "expand":
        return t.expand(text)
    return t.compress(text, langs)


def _run_c(text: str, args: argparse.Namespace) -> str:
    s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
    sess = s.Session()
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
    out = m.compress(text)
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="ConvoZip: route TalkCompress layers A–E / 1–4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  uv run python ConvoZip/convo_zip.py --layer 3 --text "as soon as possible"
  uv run python ConvoZip/convo_zip.py --layer A --key secret --text "hi" 
  printf '{"role":"user","text":"thank you"}\\n' | uv run python ConvoZip/convo_zip.py --layer C --jsonl
""",
    )
    p.add_argument(
        "--layer",
        required=True,
        help="1–4, A–E, or names: zipilogue|tessera|shorthand|morpho",
    )
    p.add_argument("--text", help="input text; otherwise stdin")
    p.add_argument("--jsonl", action="store_true", help="treat input as JSONL conversation")
    p.add_argument(
        "--mode",
        choices=("compress", "expand", "tag", "encode", "decode"),
        default=None,
        help="layer-specific mode (default: compress/encode)",
    )
    p.add_argument("--key", help="Zipilogue passphrase")
    p.add_argument("--key-file", help="Zipilogue passphrase file")
    p.add_argument("--langs", help="TesseraTalk fallback langs (comma-separated)")
    p.add_argument("--state", help="ShorthandLab session JSON path")
    p.add_argument("--stats", action="store_true", help="MorphoZip density on stderr")
    args = p.parse_args(argv)

    layer = resolve_layer(args.layer)
    if layer == "D":
        p.error("D is this router; pick A–C or E / layers 1–4")

    # Normalize mode defaults
    if args.mode is None:
        if layer == "A":
            args.mode = "encode"
        else:
            args.mode = "compress"
    if layer == "A" and args.mode == "compress":
        args.mode = "encode"
    if layer == "A" and args.mode == "expand":
        args.mode = "decode"

    raw = _read_input(args)
    if args.jsonl:
        print(process_jsonl(layer, raw, args))
    else:
        print(transform_line(layer, raw, args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
