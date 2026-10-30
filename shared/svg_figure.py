"""Minimal figure builder: a JSON-like spec in, SVG DSL v0 text out. Stdlib only.

Written for the slide-style conventions in Ironmate (pptx_spec.py):
- an arrow is a straight line plus a separate filled triangle, never a marker
  or built-in connector;
- ``edge`` mode joins box edges, ``center`` mode joins centers.

Output uses only rect, line, path, text, g, and svg (DSL v0), so every figure
passes svg_dsl.canonicalize without a converter. No transform is used: the
arrowhead is computed as a triangle path.

Spec (all coordinates in px; canvas defaults to 640 x 480, a multiple of 8)::

    {"canvas": {"width": 640, "height": 480},
     "items": [
       {"type": "box", "id": "a", "x": 40, "y": 40, "w": 160, "h": 64, "label": "Start"},
       {"type": "edge", "from": "a", "to": "b", "mode": "edge", "color": "#363636", "width": 2},
       {"type": "polyline", "points": [[0, 0], [10, 5]], "color": "#1f4e79", "width": 2},
       {"type": "text", "x": 320, "y": 40, "text": "title", "size": 16, "anchor": "middle"},
       {"type": "chart", "box": [80, 40, 600, 400],
        "x": {"min": 0, "max": 10},
        "y": {"min": 0, "max": 1},
        "series": [{"points": [[0, 0], [5, 0.7], [10, 0.4]], "color": "#1f4e79", "label": "実測"}],
        "labels": {"x": "time", "y": "value"}}
     ]}

CLI::

    python shared/svg_figure.py spec.json > figure.svg
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

INK = "#363636"
ACCENT = "#1f4e79"
FONT = "Noto Sans CJK JP"
ARROW_LEN = 12
ARROW_HALF = 6
_TICK = 6


def _num(v: float) -> str:
    return str(round(v, 2)).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


class Figure:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.lines: list[str] = []
        self.boxes: dict[str, dict] = {}

    # --- primitives -------------------------------------------------------
    def _add(self, text: str) -> None:
        self.lines.append(text)

    def rect(self, x, y, w, h, stroke=INK, fill="none", width=1.5) -> None:
        self._add(f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" '
                  f'fill="{fill}" stroke="{stroke}" stroke-width="{_num(width)}"/>')

    def line(self, x1, y1, x2, y2, color=INK, width=1.5) -> None:
        self._add(f'<line x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" y2="{_num(y2)}" '
                  f'stroke="{color}" stroke-width="{_num(width)}"/>')

    def polyline(self, points, color=INK, width=1.5) -> None:
        d = "M " + " L ".join(f"{_num(x)} {_num(y)}" for x, y in points)
        self._add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{_num(width)}"/>')

    def triangle(self, tip, base_center, half, color=INK) -> None:
        (tx, ty), (bx, by) = tip, base_center
        length = math.hypot(tx - bx, ty - by) or 1.0
        nx, ny = -(ty - by) / length, (tx - bx) / length
        p1 = (bx + nx * half, by + ny * half)
        p2 = (bx - nx * half, by - ny * half)
        d = f"M {_num(tx)} {_num(ty)} L {_num(p1[0])} {_num(p1[1])} L {_num(p2[0])} {_num(p2[1])} Z"
        self._add(f'<path d="{d}" fill="{color}" stroke="{color}" stroke-width="1"/>')

    def text(self, x, y, value, size=16, anchor="start", color=INK) -> None:
        self._add(f'<text x="{_num(x)}" y="{_num(y)}" font-family="{FONT}" font-size="{_num(size)}" '
                  f'text-anchor="{anchor}" fill="{color}">{escape(value)}</text>')

    # --- items ------------------------------------------------------------
    def box(self, item: dict) -> None:
        x, y, w, h = item["x"], item["y"], item["w"], item["h"]
        self.boxes[item["id"]] = {"x": x, "y": y, "w": w, "h": h}
        self.rect(x, y, w, h, stroke=item.get("color", INK), fill=item.get("fill", "none"))
        if item.get("label"):
            self.text(x + w / 2, y + h / 2 + 6, item["label"], size=item.get("size", 16), anchor="middle")

    def edge(self, item: dict) -> None:
        a, b = self.boxes[item["from"]], self.boxes[item["to"]]
        mode = item.get("mode", "edge")
        color, width = item.get("color", INK), item.get("width", 1.5)
        ca, cb = _center(a), _center(b)
        if mode == "center":
            p1, p2 = ca, cb
        elif mode == "edge":
            p1, p2 = _boundary(a, cb), _boundary(b, ca)
        else:
            raise ValueError(f"edge mode must be edge or center, got {mode!r}")
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length == 0:
            raise ValueError("edge length must be positive")
        ux, uy = (p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length
        base = (p2[0] - ux * ARROW_LEN, p2[1] - uy * ARROW_LEN)
        self.line(p1[0], p1[1], base[0], base[1], color=color, width=width)
        self.triangle(p2, base, ARROW_HALF, color=color)

    def polyline_item(self, item: dict) -> None:
        self.polyline(item["points"], color=item.get("color", INK), width=item.get("width", 1.5))

    def text_item(self, item: dict) -> None:
        self.text(item["x"], item["y"], item["text"], size=item.get("size", 16),
                  anchor=item.get("anchor", "start"), color=item.get("color", INK))

    def chart(self, item: dict) -> None:
        x0, y0, x1, y1 = item["box"]
        xs, ys = item["x"], item["y"]
        xmin, xmax, ymin, ymax = xs["min"], xs["max"], ys["min"], ys["max"]
        if xmax <= xmin or ymax <= ymin:
            raise ValueError("chart axis max must be greater than min")

        def px(v): return x0 + (v - xmin) / (xmax - xmin) * (x1 - x0)
        def py(v): return y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)

        self.line(x0, y1, x1, y1)  # x axis
        self.line(x0, y0, x0, y1)  # y axis
        for t in xs.get("ticks") or nice_ticks(xmin, xmax):
            self.line(px(t), y1, px(t), y1 + _TICK)
            self.text(px(t), y1 + _TICK + 18, _fmt_tick(t), size=14, anchor="middle")
        for t in ys.get("ticks") or nice_ticks(ymin, ymax):
            self.line(x0 - _TICK, py(t), x0, py(t))
            self.text(x0 - _TICK - 6, py(t) + 5, _fmt_tick(t), size=14, anchor="end")
        named = []
        for s in item.get("series", []):
            color = s.get("color", ACCENT)
            self.polyline([(px(a), py(b)) for a, b in s["points"]], color=color, width=s.get("width", 2))
            if s.get("label"):
                named.append((s["label"], color))
        for i, (label, color) in enumerate(named):
            ly = y0 + 24 + i * 24
            self.line(x1 - 120, ly, x1 - 96, ly, color=color, width=2)
            self.text(x1 - 88, ly + 5, label, size=14)
        labels = item.get("labels", {})
        if labels.get("x"):
            self.text((x0 + x1) / 2, y1 + 48, labels["x"], size=16, anchor="middle")
        if labels.get("y"):
            self.text(x0 - 48, (y0 + y1) / 2, labels["y"], size=16, anchor="middle")

    def svg(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
                f'viewBox="0 0 {self.width} {self.height}">')
        body = [f'<rect x="0" y="0" width="{self.width}" height="{self.height}" fill="#ffffff"/>']
        return head + "\n" + "\n".join(body + self.lines) + "\n</svg>\n"


def _center(box: dict) -> tuple[float, float]:
    return box["x"] + box["w"] / 2, box["y"] + box["h"] / 2


def _boundary(box: dict, toward: tuple[float, float]) -> tuple[float, float]:
    """Point where the ray from the box center toward ``toward`` leaves the box."""
    cx, cy = _center(box)
    dx, dy = toward[0] - cx, toward[1] - cy
    ts = []
    if dx:
        ts.append((box["w"] / 2) / abs(dx))
    if dy:
        ts.append((box["h"] / 2) / abs(dy))
    t = min(ts) if ts else 0.0
    return cx + dx * t, cy + dy * t


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """About ``target`` round tick values (steps of 1, 2 or 5 times a power of ten) inside [lo, hi]."""
    if hi <= lo:
        raise ValueError("tick range must be increasing")
    raw = (hi - lo) / target
    magnitude = 10 ** math.floor(math.log10(raw))
    step = min((m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw), default=10 * magnitude)
    first = math.ceil(lo / step - 1e-9) * step
    ticks, k = [], 0
    while first + k * step <= hi + 1e-9:
        ticks.append(round(first + k * step, 10))
        k += 1
    return ticks


def _fmt_tick(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else _num(float(v))


def build(spec: dict) -> str:
    canvas = spec.get("canvas", {})
    fig = Figure(int(canvas.get("width", 640)), int(canvas.get("height", 480)))
    for item in spec.get("items", []):
        kind = item.get("type")
        if kind == "box":
            fig.box(item)
        elif kind == "edge":
            fig.edge(item)
        elif kind == "polyline":
            fig.polyline_item(item)
        elif kind == "text":
            fig.text_item(item)
        elif kind == "chart":
            fig.chart(item)
        else:
            raise ValueError(f"unknown item type {kind!r}")
    return fig.svg()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    sys.stdout.write(build(json.loads(args.spec.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
