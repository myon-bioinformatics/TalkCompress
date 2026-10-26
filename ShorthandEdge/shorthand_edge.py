#!/usr/bin/env python3
"""ShorthandEdge (C): slang / abbreviation / emoji / session conventions (layer 3).

Also owns filler stripping and UNIQUE_COMPACT (ascertain→ascrt etc.).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.lex_policy import apply_unique_readings, strip_fillers  # noqa: E402

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
    # expanded EN / MCP / chat
    "let me know": "lmk",
    "to be fair": "tbf",
    "in case you missed it": "ICYMI",
    "too long; didn't read": "TL;DR",
    "too long didnt read": "TL;DR",
    "too long didn't read": "TL;DR",
    "as far as i know": "AFAIK",
    "as far as i can tell": "AFAICT",
    "for the win": "FTW",
    "on my way": "omw",
    "got it": "gg",
    "good game": "gg",
    "pull request": "PR",
    "merge request": "MR",
    "continuous integration": "CI",
    "continuous deployment": "CD",
    "work in progress": "WIP",
    "not applicable": "N/A",
    "end of day": "EOD",
    "end of week": "EOW",
    "frequently asked questions": "FAQ",
    "point of view": "POV",
    "out of office": "OOO",
    "direct message": "DM",
    "call me back": "CMB",
    "sounds good": "sg",
    "looking forward to": "lft",
    "by the way": "BTW",
    "just so you know": "JSYK",
    "in other words": "IOW",
    "at the moment": "ATM",
    "away from keyboard": "AFK",
    "rolling on the floor laughing": "rofl",
    "shaking my head": "smh",
    "in my experience": "IME",
    "your mileage may vary": "YMMV",
    "fear of missing out": "FOMO",
    "fear of better options": "FOBO",
    "do it yourself": "DIY",
    "original poster": "OP",
    "thanks in advance": "TIA",
    "best regards": "BR",
    "kind regards": "KR",
    # JA 略語
    "よろしくお願いします": "よろ",
    "ありがとうございます": "あざす",
    "すみません": "すまん",
    "承知しました": "りょ",
    "了解です": "りょ",
    "了解しました": "りょ",
    "お疲れ様です": "おつ",
    "どうでもいい": "どうでも",
    "おはようございます": "おは",
    "おやすみなさい": "おや",
    "おめでとうございます": "おめ",
    "大丈夫です": "だいじょぶ",
    "問題ありません": "もんな",
    "確認します": "かくにん",
    "確認しました": "かくにん済",
    "よろしくお願いします": "よろ",
    "申し訳ございません": "めんご",
    "とんでもないです": "とんでも",
    "お疲れ様でした": "おつ",
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
    "rocket": "🚀",
    "eyes": "👀",
    "thinking face": "🤔",
    "party": "🎉",
    "clap": "👏",
    "wave": "👋",
    "skull": "💀",
    "hundred": "💯",
    "pin": "📌",
    "link": "🔗",
    "bug": "🐛",
    "wrench": "🔧",
    "hourglass": "⏳",
    "bell": "🔔",
}

_HEREAFTER_RE = re.compile(
    r"(?i)^\s*(?:hereafter|以降)\s+(.+?)\s*=\s*(.+?)\s*$"
)
_THEREFORE_RE = re.compile(
    r"^\s*∴\s*(.+?)\s*=\s*(.+?)\s*$"
)


def _norm_phrase(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())



_PACKS_DIR = Path(__file__).resolve().parent / "packs"


def list_packs() -> list[str]:
    """Built-in pack names (stem of JSON files under packs/)."""
    if not _PACKS_DIR.is_dir():
        return []
    return sorted(p.stem for p in _PACKS_DIR.glob("*.json"))


def load_pack(name: str) -> dict[str, str]:
    """Load a domain pack by name (``dev``, ``mcp``, ...) or absolute/relative path.

    Returns a flat long→short map.
    """
    candidate = Path(name)
    if candidate.suffix == ".json" and candidate.is_file():
        path = candidate
    else:
        path = _PACKS_DIR / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"unknown shorthand pack: {name} (looked in {_PACKS_DIR})")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "map" in data and isinstance(data["map"], dict):
        return {str(k): str(v) for k, v in data["map"].items()}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if k != "conventions"}
    raise ValueError(f"pack {name} must be a JSON object")


def merge_packs(names: list[str]) -> dict[str, str]:
    """Merge packs in order; later packs override earlier keys."""
    merged: dict[str, str] = {}
    for name in names:
        merged.update(load_pack(name))
    return merged


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

    def merge_lexicon(self, mapping: dict[str, str]) -> None:
        """Merge an extra lexicon into the session map (extra keys override defaults)."""
        for k, v in mapping.items():
            self.map[_norm_phrase(str(k))] = str(v)

    def load_lexicon(self, path: str | Path) -> None:
        """Load extra lexicon JSON: flat {long: short} or {\"map\": {...}}."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "map" in data and isinstance(data["map"], dict):
            self.merge_lexicon(data["map"])
        elif isinstance(data, dict):
            # ignore convention-only files that only have "conventions"
            payload = {k: v for k, v in data.items() if k != "conventions"}
            if payload:
                self.merge_lexicon(payload)

    def load_packs(self, names: list[str]) -> None:
        """Merge domain packs (``dev``, ``mcp``, ...) into the session map."""
        self.merge_lexicon(merge_packs(names))

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
                if k == "map":
                    continue
                self.conventions[_norm_phrase(str(k))] = str(v)

    def export_lexicon(self) -> dict:
        """Dump effective map (base + conventions) for serialization."""
        return {
            "map": dict(self.effective),
            "conventions": dict(self.conventions),
        }

    def export_lexicon_to(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.export_lexicon(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


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
        line_out = strip_fillers(_apply_map(line, sess.effective))
        # UNIQUE_READINGS + UNIQUE_COMPACT (C ownership): find out → ascrt
        line_out = apply_unique_readings(line_out, compact=True)
        kept.append(line_out)
    if len(lines) == 1 and "\n" not in text:
        return kept[0] if kept else ""
    return "\n".join(kept)


def _apply_map(text: str, m: dict[str, str]) -> str:
    items = sorted(m.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = text
    for long, short in items:
        if not long:
            continue
        if re.search(r"[^\x00-\x7f]", long) or not long.isascii():
            out = out.replace(long, short)
            continue
        pat = re.compile(re.escape(long), re.IGNORECASE)
        out = pat.sub(short, out)
    return out


def expand(text: str, mapping: dict[str, str] | None = None, session: Session | None = None) -> str:
    sess = session or Session()
    if mapping is not None:
        for k, v in mapping.items():
            sess.map[_norm_phrase(k)] = v
    m = sess.effective
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
            out = out.replace(short, long)
            if short.lower() != short:
                out = re.sub(re.escape(short), long, out, flags=re.IGNORECASE)
    return out



def suggest_hereafter(text: str, *, min_count: int = 2) -> list[dict[str, str | int]]:
    """Heuristic: detect repeated multi-word / CJK phrases and propose hereafter lines.

    Criteria: ≥ ``min_count`` occurrences; phrase is ≥2 whitespace-separated words
    OR a CJK run of length ≥4. Does not auto-apply.
    Returns list of {long, short, count, line} where line is ``hereafter LONG = SHORT``.
    """
    from collections import Counter

    # Multi-word Latin-ish ngrams (2–4 words)
    words = re.findall(r"[A-Za-z0-9']+|[぀-ヿ㐀-鿿]{2,}", text)
    # Also scan raw lowercased sliding windows of 2-3 space-separated tokens
    lowered = text.lower()
    latin_tokens = re.findall(r"[a-z0-9']+", lowered)
    candidates: Counter[str] = Counter()
    for n in (2, 3, 4):
        for i in range(len(latin_tokens) - n + 1):
            phrase = " ".join(latin_tokens[i : i + n])
            if len(phrase) < 5:
                continue
            candidates[phrase] += 1
    # CJK runs ≥4 chars appearing ≥min_count
    for m in re.finditer(r"[぀-ヿ㐀-鿿]{4,}", text):
        candidates[m.group(0)] += 1

    # Recount properly for CJK (finditer already counted once per occurrence — OK)
    # For latin ngrams, Counter above already tallied sliding windows.
    suggestions: list[dict[str, str | int]] = []
    used_shorts: set[str] = set()
    for phrase, count in candidates.most_common(40):
        if count < min_count:
            continue
        # Prefer true multi-word or long CJK
        is_cjk = bool(re.search(r"[぀-ヿ㐀-鿿]", phrase))
        if not is_cjk and len(phrase.split()) < 2:
            continue
        if is_cjk and len(phrase) < 4:
            continue
        # Build a short acronym-ish form
        if is_cjk:
            short = phrase[:2]
        else:
            parts = phrase.split()
            short = "".join(p[0] for p in parts if p).upper()
            if len(short) < 2:
                short = phrase[:3]
        base = short
        i = 2
        while short in used_shorts:
            short = f"{base}{i}"
            i += 1
        used_shorts.add(short)
        line = f"hereafter {phrase} = {short}"
        suggestions.append({"long": phrase, "short": short, "count": count, "line": line})
    return suggestions


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ShorthandEdge: layer-3 human shorthand")
    p.add_argument("mode", nargs="?", default="compress", choices=("compress", "expand", "suggest"))
    p.add_argument("--text", help="input; else stdin")
    p.add_argument("--state", help="JSON file for session conventions (read+write on compress)")
    p.add_argument("--lexicon", help="extra lexicon JSON to merge into session map")
    p.add_argument(
        "--pack",
        action="append",
        default=None,
        dest="pack",
        help="domain pack name under packs/ (repeatable: dev, mcp, ...)",
    )
    p.add_argument("--export-lexicon", dest="export_lexicon", help="write effective map JSON to PATH")
    p.add_argument(
        "--apply-suggestions",
        action="store_true",
        help="with suggest/compress: declare suggested hereafter conventions into session",
    )
    args = p.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    sess = Session()
    if args.pack:
        sess.load_packs(args.pack)
    if args.lexicon:
        sess.load_lexicon(args.lexicon)
    if args.state and Path(args.state).exists():
        sess.load(args.state)

    if args.mode == "suggest":
        suggestions = suggest_hereafter(text)
        if args.apply_suggestions:
            for s in suggestions:
                sess.declare(str(s["long"]), str(s["short"]))
            if args.state:
                sess.save(args.state)
        for s in suggestions:
            print(s["line"])
        if args.export_lexicon:
            sess.export_lexicon_to(args.export_lexicon)
        return 0

    if args.apply_suggestions:
        for s in suggest_hereafter(text):
            sess.declare(str(s["long"]), str(s["short"]))

    if args.mode == "compress":
        out = compress(text, session=sess)
        if args.state:
            sess.save(args.state)
        print(out)
    else:
        print(expand(text, session=sess))
    if args.export_lexicon:
        sess.export_lexicon_to(args.export_lexicon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
