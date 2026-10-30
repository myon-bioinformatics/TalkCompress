"""SVG DSL v0 (L1): canonical text form for line drawings. Stdlib only.

A drawing is written as a small SVG subset. ``canonicalize`` turns any accepted
source into one fixed text form, so the same drawing always gives the same
string. This is the L1 check: canonical(canonical(x)) == canonical(x).

Accepted elements: svg (root), g, rect, circle, line, path, text.
Accepted attributes: only the ones listed in ATTRS. Anything else is an error.

Canonical rules:
- Root: xmlns is the SVG namespace (a missing xmlns is accepted and added);
  width and height are positive integers; viewBox must be exactly "0 0 WIDTH HEIGHT".
- Numbers: rounded to 2 decimals (half-even), trailing zeros removed, no
  "-0", integers without a decimal point.
- Colors: "none" or "#rrggbb" (lowercase; #rgb is expanded).
- Path: commands M L H V C S Q T Z and their lowercase forms only (no arcs).
  Tokens are joined with single spaces; numbers use the number rule.
- Text: the only child is character data. Whitespace runs collapse to one
  space; text is Unicode NFC. font-family must be one of FONT_STACKS.
- Attributes are sorted by name. Elements keep document order, one per line,
  indented two spaces. Comments and whitespace between elements are dropped.

Rejected: DOCTYPE, processing instructions, script, style, foreignObject,
image, use, transform, any namespace other than SVG, and any element or
attribute not listed above.

Warning only (not an error): width or height not a multiple of 8. This is the
recommended default, not a requirement.

CLI::

    python shared/svg_dsl.py drawing.svg          # print canonical form
    python shared/svg_dsl.py drawing.svg --check  # exit 1 on any error
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from xml.sax.saxutils import escape

VERSION = "0"
SVG_NS = "http://www.w3.org/2000/svg"
ELEMENTS = {"svg", "g", "rect", "circle", "line", "path", "text"}
ATTRS: dict[str, set[str]] = {
    "svg": {"width", "height", "viewBox", "xmlns"},
    "g": {"fill", "stroke", "stroke-width"},
    "rect": {"x", "y", "width", "height", "fill", "stroke", "stroke-width"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width"},
    "path": {"d", "fill", "stroke", "stroke-width"},
    "text": {"x", "y", "font-family", "font-size", "fill", "text-anchor"},
}
NUMBER_ATTRS = {"width", "height", "x", "y", "cx", "cy", "r", "x1", "y1", "x2", "y2", "stroke-width", "font-size"}
COLOR_ATTRS = {"fill", "stroke"}
TEXT_ANCHORS = {"start", "middle", "end"}
# Font stacks allowed for text. Pending confirmation of the default font.
FONT_STACKS = {"Noto Sans JP": "Noto Sans JP", "Noto Sans JP, sans-serif": "Noto Sans JP, sans-serif"}
DECIMALS = Decimal("0.01")
RECOMMENDED_MULTIPLE = 8

_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
_PATH_TOKEN = re.compile(r"[\s,]*(?P<t>[MmLlHhVvCcSsQqTtZz]|" + _NUM + r")")
_PATH_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "Z": 0}
_HEX = re.compile(r"#(?P<h>[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


class SvgDslError(ValueError):
    """Raised by canonicalize when the source breaks a v0 rule."""


@dataclass
class Result:
    canonical: str | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _local(tag: str) -> str:
    if not tag.startswith("{"):
        return tag
    ns, _, name = tag[1:].partition("}")
    return name if ns == SVG_NS else "!" + tag


def fmt_num(raw: str) -> str:
    """Round to two decimals, drop trailing zeros and any '-0'."""
    try:
        d = Decimal(raw)
    except InvalidOperation as exc:
        raise SvgDslError(f"bad number {raw!r}") from exc
    if not d.is_finite():
        raise SvgDslError(f"non-finite number {raw!r}")
    q = d.quantize(DECIMALS, rounding=ROUND_HALF_EVEN)
    if q == 0:
        return "0"
    if q == q.to_integral_value():
        return str(int(q))
    return format(q, "f").rstrip("0").rstrip(".")


def _color(raw: str) -> str:
    if raw == "none":
        return raw
    m = _HEX.fullmatch(raw.strip())
    if not m:
        raise SvgDslError(f"color must be none or #rgb/#rrggbb, got {raw!r}")
    h = m.group("h").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def _path(raw: str) -> str:
    tokens: list[str] = []
    pos = 0
    text = raw.strip()
    while pos < len(text):
        m = _PATH_TOKEN.match(text, pos)
        if not m:
            raise SvgDslError(f"bad path data near {text[pos:pos + 12]!r}")
        tokens.append(m.group("t"))
        pos = m.end()
    if not tokens or tokens[0] not in ("M", "m"):
        raise SvgDslError("path must start with M or m")
    out: list[str] = []
    cmd = None
    args: list[str] = []
    for t in tokens:
        if t.upper() in _PATH_ARGS:
            if cmd is not None and args:
                raise SvgDslError(f"command {cmd} has wrong argument count")
            cmd = t
            out.append(t)
            args = []
            if _PATH_ARGS[t.upper()] == 0:
                cmd = None
            continue
        if cmd is None:
            raise SvgDslError("number before any path command")
        args.append(fmt_num(t))
        out.append(fmt_num(t))
        if len(args) == _PATH_ARGS[cmd.upper()]:
            args = []
            if cmd.upper() == "M":
                cmd = "L" if cmd == "M" else "l"
    if cmd is not None and args:
        raise SvgDslError("path ends in an incomplete command")
    return " ".join(out)


def _text_value(raw: str) -> str:
    return " ".join(unicodedata.normalize("NFC", raw).split())


def _attr(el_name: str, key: str, raw: str) -> str:
    if key in NUMBER_ATTRS:
        return fmt_num(raw.strip())
    if key in COLOR_ATTRS:
        return _color(raw.strip())
    if key == "d":
        return _path(raw)
    if key == "text-anchor":
        if raw.strip() not in TEXT_ANCHORS:
            raise SvgDslError(f"text-anchor must be start, middle or end, got {raw!r}")
        return raw.strip()
    if key == "font-family":
        norm = ", ".join(p.strip().strip("'\"") for p in raw.split(","))
        if norm not in FONT_STACKS:
            raise SvgDslError(f"font-family not allowed: {norm!r}")
        return FONT_STACKS[norm]
    if key == "viewBox":
        return " ".join(fmt_num(p) for p in raw.split())
    if key == "xmlns":
        return SVG_NS
    raise SvgDslError(f"unhandled attribute {key}")


def _check_element(el: ET.Element, errors: list[str]) -> None:
    name = _local(el.tag)
    if name not in ELEMENTS:
        errors.append(f"element not allowed: {name}")
        return
    allowed = ATTRS[name]
    for key in el.attrib:
        local_key = key if not key.startswith("{") else "!" + key
        if local_key not in allowed:
            errors.append(f"attribute not allowed on {name}: {local_key}")
    if name == "text":
        if len(el):
            errors.append("text may not contain elements")
    else:
        if el.text and el.text.strip():
            errors.append(f"{name} may not contain text")
    for child in el:
        _check_element(child, errors)


def _attrs_out(name: str, el: ET.Element, errors: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if name == "svg":
        # The parser moves xmlns into the tag name, so the canonical form adds it back.
        out.append(("xmlns", SVG_NS))
    for key, raw in el.attrib.items():
        if key.startswith("{") or key not in ATTRS[name]:
            continue
        try:
            out.append((key, _attr(name, key, raw)))
        except SvgDslError as exc:
            errors.append(f"{name}.{key}: {exc}")
    return sorted(out)


def _write(el: ET.Element, depth: int, lines: list[str], errors: list[str]) -> None:
    name = _local(el.tag)
    pad = "  " * depth
    attrs = _attrs_out(name, el, errors)
    attr_text = "".join(f' {k}="{escape(v, {chr(34): "&quot;"})}"' for k, v in attrs)
    if name == "text":
        content = escape(_text_value(el.text or ""))
        lines.append(f"{pad}<text{attr_text}>{content}</text>")
        return
    children = list(el)
    if not children:
        lines.append(f"{pad}<{name}{attr_text}/>")
        return
    lines.append(f"{pad}<{name}{attr_text}>")
    for child in children:
        _write(child, depth + 1, lines, errors)
    lines.append(f"{pad}</{name}>")


def _root_checks(root: ET.Element, errors: list[str], warnings: list[str]) -> None:
    if _local(root.tag) != "svg":
        errors.append("root element must be svg")
        return
    for key in ("width", "height", "viewBox"):
        if key not in root.attrib:
            errors.append(f"svg root needs {key}")
    dims: list[int] = []
    for key in ("width", "height"):
        try:
            d = Decimal(root.attrib.get(key, "x").strip())
        except InvalidOperation:
            errors.append(f"{key} must be a positive integer")
            return
        if not d.is_finite() or d <= 0 or d != d.to_integral_value():
            errors.append(f"{key} must be a positive integer")
            return
        dims.append(int(d))
    w, h = dims
    if "viewBox" in root.attrib:
        try:
            vb = " ".join(fmt_num(p) for p in root.attrib["viewBox"].split())
        except SvgDslError as exc:
            errors.append(f"viewBox: {exc}")
            return
        if vb != f"0 0 {w} {h}":
            errors.append(f"viewBox must be '0 0 {w} {h}', got {vb!r}")
    if w % RECOMMENDED_MULTIPLE or h % RECOMMENDED_MULTIPLE:
        warnings.append(f"size {w}x{h} is not a multiple of {RECOMMENDED_MULTIPLE} (recommended)")


def analyze(source: str) -> Result:
    """Check a source against v0 and return the canonical form if it passes."""
    errors: list[str] = []
    warnings: list[str] = []
    body = re.sub(r"^\s*<\?xml[^>]*\?>", "", source, count=1)
    if re.search(r"<!DOCTYPE", body, re.I) or "<?" in body:
        return Result(None, ["DOCTYPE and processing instructions are not allowed"])
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        return Result(None, [f"XML parse error: {exc}"])
    _root_checks(root, errors, warnings)
    _check_element(root, errors)
    if errors:
        return Result(None, errors, warnings)
    lines: list[str] = []
    _write(root, 0, lines, errors)
    if errors:
        return Result(None, errors, warnings)
    canonical = "\n".join(lines) + "\n"
    return Result(canonical, errors, warnings)


def canonicalize(source: str) -> str:
    """Return the canonical v0 text, or raise SvgDslError listing every problem."""
    result = analyze(source)
    if not result.ok:
        raise SvgDslError("; ".join(result.errors))
    assert result.canonical is not None
    return result.canonical


def is_idempotent(source: str) -> bool:
    """L1 property: canonical text canonicalizes to itself."""
    first = canonicalize(source)
    return canonicalize(first) == first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = analyze(args.file.read_text(encoding="utf-8"))
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not result.ok:
        for e in result.errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    if not args.check:
        sys.stdout.write(result.canonical or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
