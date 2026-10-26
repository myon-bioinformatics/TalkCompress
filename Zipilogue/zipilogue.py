#!/usr/bin/env python3
"""Zipilogue (A): machine-to-machine conversation encoding (layer 1)."""

from __future__ import annotations

import argparse
import sys


def encode(payload: bytes, *, key: bytes) -> bytes:
    """Encode for bot-to-bot transit. Placeholder XOR; replace with real crypto later."""
    if not key:
        raise ValueError("key must be non-empty")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))


def decode(payload: bytes, *, key: bytes) -> bytes:
    """Decode is symmetric for the placeholder cipher."""
    return encode(payload, key=key)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Zipilogue: layer-1 machine encoding")
    p.add_argument("mode", choices=("encode", "decode"))
    p.add_argument("--key", required=True, help="shared secret (do not commit real keys)")
    p.add_argument("--text", help="UTF-8 text input; otherwise read stdin as bytes")
    args = p.parse_args(argv)

    key = args.key.encode("utf-8")
    raw = args.text.encode("utf-8") if args.text is not None else sys.stdin.buffer.read()
    out = encode(raw, key=key) if args.mode == "encode" else decode(raw, key=key)
    if args.mode == "decode":
        sys.stdout.buffer.write(out)
    else:
        # encode: hex for safe pipe display
        sys.stdout.write(out.hex() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
