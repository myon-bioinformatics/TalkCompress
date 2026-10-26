#!/usr/bin/env python3
"""ShorthandLab (C): slang / abbreviation / emoji / session conventions (layer 3)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.lex_policy import strip_fillers  # noqa: E402

# phrase (lowercase) → short form. Longer keys win via sorted replace.
DEFAULT_MAP: dict[str, str] = {
    # EN common
    "as soon as possible": "ASAP",
    "for your information": "FYI",
    "by the way": "BTW",
    "in my opinion": "IMO",
    "in my humble opinion": "IMHO",
    "for what it's worth": "FWIW",
    "to be honest": "TBH",
    "laughing out loud": "lol",
    "oh my god": "omg",
    "I don't know": "idk",
    "i don't know": "idk",
    "thank you": "ty",
    "thanks": "thx",
    "you are welcome": "yw",
    "you're welcome": "yw",
    "see you": "cu",
    "be right back": "brb",
    "talk to you later": "ttyl",
    "in real life": "IRL",
    "do not disturb": "DND",
    "please": "pls",
    "people": "ppl",
    "because": "bc",
    "before": "b4",
    "great": "gr8",
    "never mind": "nvm",
    "no problem": "np",
    "right now": "rn",
    "what the hell": "wth",
    "what the fuck": "wtf",
    # JA 略語
    "よろしくお願いします": "よろ",
    "ありがとうございます": "あざす",
    "すみません": "すまん",
    "承知しました": "りょ",
    "了解です": "りょ",
    "お疲れ様です": "おつ",
    "どうでもいい": "どうでも",
    # emoji / signal
    "thumbs up": "👍",
    "thumbs down": "👎",
    "fire": "🔥",
    "check": "✅",
    "warning": "⚠️",
    "idea": "💡",
    "laugh": "😂",
    "sad": "😢",
    "heart": "❤️",
    "ok hand": "👌",
}

_HEREAFTER_RE = re.compile(
    r"(?i)^\s*(?:hereafter|以降)\s+(.+?)\s*=\s*(.+?)\s*$"
)
_THEREFORE_RE = re.compile(
    r"^\s*∴\s*(.+?)\s*=\s*(.+?)\s*$"
)


def _norm_phrase(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


class Session:
    """Mutable session conventions + lexicon."""

    def __init__(self, base: dict[str, str] | None = None) -> None:
        self.map: dict[str, str] = dict(base or DEFAULT_MAP)
        self.conventions: dict[str, str] = {}  # long → short declared this session

    @property
    def effective(self) -> dict[str, str]:
        m = dict(self.map)
        m.update(self.conventions)
        return m

    def declare(self, long_form: str, short_form: str) -> None:
        self.conventions[_norm_phrase(long_form)] = short_form.strip()

    def ingest_line(self, line: str) -> bool:
        """If line is a hereafter / ∴ declaration, record and return True."""
        for pat in (_HEREAFTER_RE, _THEREFORE_RE):
            m = pat.match(line)
            if m:
                self.declare(m.group(1), m.group(2))
                return True
        return False

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"conventions": self.conventions}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        conv = data.get("conventions") or data
        if isinstance(conv, dict):
            for k, v in conv.items():
                self.conventions[_norm_phrase(str(k))] = str(v)


def compress(text: str, mapping: dict[str, str] | None = None, session: Session | None = None) -> str:
    """Apply conventions then lexicon; longest-match first. Declaration lines are consumed."""
    if session is not None:
        sess = session
        if mapping is not None:
            sess.map.update({_norm_phrase(k): v for k, v in mapping.items()})
    elif mapping is not None:
        sess = Session(mapping)
    else:
        sess = Session()

    lines = text.splitlines() or [text]
    kept: list[str] = []
    for line in lines:
        if sess.ingest_line(line):
            continue
        kept.append(strip_fillers(_apply_map(line, sess.effective)))
    # Preserve single-line vs multi
    if len(lines) == 1 and "\n" not in text:
        return kept[0] if kept else ""
    return "\n".join(kept)


def _apply_map(text: str, m: dict[str, str]) -> str:
    # Work on a copy; replace case-insensitively for latin phrases via regex.
    items = sorted(m.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = text
    for long, short in items:
        if not long:
            continue
        # CJK / emoji phrases: plain replace (also title/upper variants for ascii)
        if re.search(r"[^\x00-\x7f]", long) or not long.isascii():
            out = out.replace(long, short)
            continue
        # Word-ish boundary for ASCII phrases
        pat = re.compile(re.escape(long), re.IGNORECASE)
        out = pat.sub(short, out)
    return out


def expand(text: str, mapping: dict[str, str] | None = None, session: Session | None = None) -> str:
    sess = session or Session()
    if mapping is not None:
        for k, v in mapping.items():
            sess.map[_norm_phrase(k)] = v
    m = sess.effective
    # Invert: short → longest long (if collisions, prefer longest long)
    inv: dict[str, str] = {}
    for long, short in sorted(m.items(), key=lambda kv: len(kv[0])):
        inv[short] = long
    out = text
    for short, long in sorted(inv.items(), key=lambda kv: len(kv[0]), reverse=True):
        if not short:
            continue
        if re.search(r"[^\x00-\x7f]", short) or not short.isascii():
            out = out.replace(short, long)
        else:
            # Case-sensitive short forms (ASAP, FYI) — exact
            out = out.replace(short, long)
            if short.lower() != short:
                out = re.sub(re.escape(short), long, out, flags=re.IGNORECASE)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ShorthandLab: layer-3 human shorthand")
    p.add_argument("mode", choices=("compress", "expand"))
    p.add_argument("--text", help="input; else stdin")
    p.add_argument("--state", help="JSON file for session conventions (read+write on compress)")
    args = p.parse_args(argv)
    text = args.text if args.text is not None else __import__("sys").stdin.read()
    sess = Session()
    if args.state and Path(args.state).exists():
        sess.load(args.state)
    if args.mode == "compress":
        out = compress(text, session=sess)
        if args.state:
            sess.save(args.state)
        print(out)
    else:
        print(expand(text, session=sess))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
