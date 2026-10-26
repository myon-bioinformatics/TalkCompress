#!/usr/bin/env python3
"""TesseraTalk (B): sentence-level language-switch mosaic (layer 2).

Heuristic LID by Unicode script / light cues (not ML). Compress emits a compact
tagged mosaic `lang:sentence|lang:sentence`; expand restores plain text.
"""

from __future__ import annotations

import argparse
import re
import unicodedata

# Split after terminator, keep terminator on the left sentence. LTR + CJK punct.
_SENT_SPLIT = re.compile(
    r"(?<=[.!?。？！…])"  # after terminator
    r"(?:\s+|(?=[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7afA-Za-z0-9\"'(\[]))"
)

_LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]")
_HIRAGANA = re.compile(r"[\u3040-\u309F]")
_KATAKANA = re.compile(r"[\u30A0-\u30FF]")
_CJK = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF]")
_HANGUL = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_ARABIC = re.compile(r"[\u0600-\u06FF]")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# Light lexical cues (lowercase). Used only as tie-breakers.
_CUES: dict[str, tuple[str, ...]] = {
    "en": ("the", "and", "is", "are", "you", "this", "that", "with", "for", "not"),
    "es": ("el", "la", "los", "las", "que", "y", "de", "en", "un", "una", "por", "con"),
    "fr": ("le", "la", "les", "des", "une", "est", "que", "dans", "pour", "avec"),
    "de": ("der", "die", "das", "und", "ist", "nicht", "ein", "eine", "mit", "auf"),
    "pt": ("o", "a", "os", "as", "que", "de", "em", "um", "uma", "não", "para"),
    "ja": ("は", "を", "が", "に", "です", "ます", "した", "する", "こと"),
}


def segment(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.strip())
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


def _script_scores(s: str) -> dict[str, int]:
    return {
        "latin": len(_LATIN.findall(s)),
        "hira": len(_HIRAGANA.findall(s)),
        "kata": len(_KATAKANA.findall(s)),
        "cjk": len(_CJK.findall(s)),
        "hangul": len(_HANGUL.findall(s)),
        "cyrillic": len(_CYRILLIC.findall(s)),
        "arabic": len(_ARABIC.findall(s)),
        "deva": len(_DEVANAGARI.findall(s)),
    }


def _cue_hits(s: str, lang: str) -> int:
    low = s.lower()
    words = re.findall(r"[a-zà-ÿ']+", low)
    cues = _CUES.get(lang, ())
    # For JA cues, search substrings
    if lang == "ja":
        return sum(1 for c in cues if c in s)
    return sum(1 for w in words if w in cues)


def detect_lang(sentence: str) -> str:
    """Heuristic language tag for one sentence."""
    sc = _script_scores(sentence)
    total_script = sum(sc.values()) or 1

    if sc["hira"] + sc["kata"] > 0:
        return "ja"
    if sc["hangul"] / total_script > 0.3:
        return "ko"
    if sc["cyrillic"] / total_script > 0.3:
        return "ru"
    if sc["arabic"] / total_script > 0.3:
        return "ar"
    if sc["deva"] / total_script > 0.3:
        return "hi"
    if sc["cjk"] > 0 and sc["hira"] + sc["kata"] == 0 and sc["latin"] == 0:
        return "zh"
    if sc["latin"] / total_script > 0.2 or sc["latin"] > 0:
        # Tie-break among Romance / Germanic via cues
        scores = {
            "en": _cue_hits(sentence, "en"),
            "es": _cue_hits(sentence, "es"),
            "fr": _cue_hits(sentence, "fr"),
            "de": _cue_hits(sentence, "de"),
            "pt": _cue_hits(sentence, "pt"),
        }
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        return "en"
    if sc["cjk"] > 0:
        return "zh"
    return "und"


def tag_sentences(text: str, langs: list[str] | None = None) -> list[tuple[str, str]]:
    """Tag each sentence. If langs is given and non-empty, use as fallback cycle
    only when detector returns 'und'; otherwise prefer heuristic LID."""
    sents = segment(text)
    fallback = langs if langs else ["und"]
    tagged: list[tuple[str, str]] = []
    for i, s in enumerate(sents):
        lang = detect_lang(s)
        if lang == "und" and fallback:
            lang = fallback[i % len(fallback)]
        tagged.append((lang, s))
    return tagged


def render(tagged: list[tuple[str, str]]) -> str:
    return "\n".join(f"[{lang}] {sent}" for lang, sent in tagged)


def compress(text: str, langs: list[str] | None = None) -> str:
    """Compact mosaic: lang:sentence|lang:sentence (pipe-separated)."""
    tagged = tag_sentences(text, langs)
    parts: list[str] = []
    for lang, sent in tagged:
        # Escape bare pipes inside sentence
        safe = sent.replace("|", r"\|")
        parts.append(f"{lang}:{safe}")
    return "|".join(parts)


def expand(mosaic: str) -> str:
    """Expand mosaic back to plain text (sentences joined by space)."""
    if not mosaic.strip():
        return ""
    # Split on unescaped |
    parts = re.split(r"(?<!\\)\|", mosaic.strip())
    sentences: list[str] = []
    for part in parts:
        part = part.replace(r"\|", "|")
        if ":" in part:
            _, body = part.split(":", 1)
        else:
            body = part
        body = body.strip()
        if body:
            sentences.append(body)
    # Join: CJK-ending → no space before next CJK; else space
    out: list[str] = []
    for i, s in enumerate(sentences):
        if i == 0:
            out.append(s)
            continue
        prev = out[-1]
        if re.search(r"[。？！]$", prev) or re.match(r"^[\u3040-\u30ff\u3400-\u9fff]", s):
            out.append(s)
        else:
            out.append(" " + s)
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TesseraTalk: layer-2 sentence mosaic")
    p.add_argument(
        "mode",
        nargs="?",
        default="tag",
        choices=("tag", "compress", "expand"),
        help="tag (pretty), compress (mosaic), expand (plain)",
    )
    p.add_argument("--text", help="input text; else stdin")
    p.add_argument(
        "--langs",
        default="",
        help="optional comma-separated fallback codes when LID is und",
    )
    args = p.parse_args(argv)
    text = args.text if args.text is not None else __import__("sys").stdin.read()
    langs = [x.strip() for x in args.langs.split(",") if x.strip()] or None

    if args.mode == "tag":
        print(render(tag_sentences(text, langs)))
    elif args.mode == "compress":
        print(compress(text, langs))
    else:
        print(expand(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
