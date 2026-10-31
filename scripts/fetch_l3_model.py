#!/usr/bin/env python3
"""Pinned weights for the SVG L3 workflow. Stdlib only.

``--list`` prints the model keys as a GitHub Actions matrix.
``MODEL DEST`` downloads the pinned file if DEST is missing, then verifies size and
SHA-256 (also for cache hits) and writes ``DEST.provenance.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

CATALOG = Path("shared/l3_models.json")


def load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def fetch(url: str, dest: Path) -> None:
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, part.open("wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    part.replace(dest)


def prepare(key: str, dest: Path) -> dict:
    model = load()[key]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        fetch(model["url"], dest)
    with dest.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != model["sha256"] or dest.stat().st_size != model["bytes"]:
        raise SystemExit(f"{key}: size or SHA-256 mismatch (including cached bytes)")
    template = model["template"]
    receipt = {
        **model,
        "model_id": key,
        "sha256_verified": True,
        "template_sha256": hashlib.sha256(Path(template).read_bytes()).hexdigest() if template else None,
        "reasoning": "off",
    }
    dest.with_name(dest.name + ".provenance.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", nargs="?", help="model key from shared/l3_models.json")
    parser.add_argument("dest", nargs="?", type=Path)
    parser.add_argument("--list", action="store_true", help="print the matrix for all models")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    if args.list:
        choice = args.model or "all"
        if choice != "all" and choice not in load():
            parser.error(f"unknown model {choice!r}; choose all or one of {', '.join(load())}")
        keys = list(load()) if choice == "all" else [choice]
        matrix = json.dumps({"model": keys}, separators=(",", ":"))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as stream:
                stream.write(f"matrix={matrix}\n")
        print(matrix)
        return 0
    if not (args.model and args.dest):
        parser.error("MODEL and DEST are required unless --list is given")
    receipt = prepare(args.model, args.dest)
    print(json.dumps({"model_id": receipt["model_id"], "bytes": receipt["bytes"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
