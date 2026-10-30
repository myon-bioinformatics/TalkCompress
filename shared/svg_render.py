"""SVG DSL v0 (L2): deterministic raster check. Uses Chromium via Playwright, no network.

Two checks, both on pixels (SHA-256 of the PNG bytes):

- determinism: the canonical text renders to the same PNG on every run here.
- equivalence: the original source and its canonical form render to the same PNG.

Provenance (Chromium, Playwright, the Noto Sans CJK JP font file and its
package version) is returned with each check, so a result says which
renderer produced it. A PNG hash only matches on the same renderer and fonts.

CLI::

    python shared/svg_render.py drawing.svg   # prints the L2 report as JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path

try:
    from shared.svg_dsl import canonicalize
except ImportError:
    from svg_dsl import canonicalize

FONT_FAMILY = "Noto Sans CJK JP"


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()


def font_provenance() -> dict[str, str]:
    path = _run(["fc-match", "-f", "%{file}", FONT_FAMILY])
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest() if path and Path(path).exists() else ""
    pkg = _run(["dpkg-query", "-W", "-f=${Version}", "fonts-noto-cjk"])
    return {"font_family": FONT_FAMILY, "font_file": path, "font_sha256": digest, "font_package": pkg}


def _html(svg: str, width: int, height: int) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        f"html,body{{margin:0;padding:0;background:#fff;width:{width}px;height:{height}px;overflow:hidden}}"
        f"svg{{display:block}}</style></head><body>{svg}</body></html>"
    )


def _size(svg: str) -> tuple[int, int]:
    root = ET.fromstring(svg)
    w, h = root.attrib.get("width", ""), root.attrib.get("height", "")
    if not (w.isdigit() and h.isdigit()):
        raise ValueError("svg has no integer width/height")
    return int(w), int(h)


class Renderer:
    """Holds one Chromium instance for several renders."""

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self.provenance = {
            "renderer": "chromium",
            "chromium": self._browser.version,
            "playwright": version("playwright"),
            **font_provenance(),
        }

    def png(self, svg: str, size: tuple[int, int]) -> bytes:
        width, height = size
        page = self._browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        try:
            page.set_content(_html(svg, width, height))
            page.wait_for_load_state("load")
            return page.screenshot(full_page=False, clip={"x": 0, "y": 0, "width": width, "height": height})
        finally:
            page.close()

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def l2_check(source: str, renderer: Renderer | None = None) -> dict:
    """Report whether the source and its canonical form render identically, and whether rendering is stable."""
    own = renderer is None
    r = renderer or Renderer()
    try:
        canonical = canonicalize(source)
        size = _size(canonical)
        first = r.png(canonical, size)
        second = r.png(canonical, size)
        from_source = r.png(_strip_declaration(source), size)
        report = {
            "ok": first == second and first == from_source,
            "deterministic": first == second,
            "source_matches_canonical": first == from_source,
            "png_sha256": _sha(first),
            "canonical_size": list(_size(canonical)),
            "provenance": r.provenance,
        }
        return report
    finally:
        if own:
            r.close()


def _strip_declaration(source: str) -> str:
    """Drop the XML declaration so the markup can sit inside an HTML body."""
    return re.sub(r"^\s*<\?xml[^>]*\?>", "", source, count=1).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    report = l2_check(args.file.read_text(encoding="utf-8"))
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
