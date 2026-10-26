"""Lexeme policy: fillers, unique-reading preference, light etymon alignment.

Used primarily by MorphoZip (E); filler stripping is also safe for ShorthandLab (C).
"""

from __future__ import annotations

import re

# Light fillers / interjections to drop while compressing (case-insensitive for Latin).
# Keep content words; only strip discourse grease.
FILLERS_EN: tuple[str, ...] = (
    "um",
    "uh",
    "erm",
    "er",
    "ah",
    "oh",
    "well",
    "like",  # discourse "like", applied with word-boundary; may over-strip — see note in MorphoZip
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "basically",
    "actually",  # often empty intensifier in chat
    "literally",  # when used as filler intensifier
    "just",  # hedge; aggressive — applied carefully
)

FILLERS_JA: tuple[str, ...] = (
    "えーと",
    "えっと",
    "あのー",
    "あの",
    "そのー",
    "まあ",
    "まぁ",
    "なんか",
    "とりあえず",
    "とりあえずね",
    "ですねー",
    "ですよね",
)

# Rank-1 / unique-reading substitutions: prefer jargon or specialized verbs
# that admit fewer senses than basic verbs (paper-ish / procedural tone).
# long → short unique form
UNIQUE_READINGS: dict[str, str] = {
    # basic → tighter
    "get": "obtain",  # will be shortened further in morpho if needed
    "make": "construct",
    "do": "perform",
    "put": "place",
    "take": "acquire",
    "give": "provide",
    "look at": "inspect",
    "think about": "consider",
    "talk about": "discuss",
    "find out": "ascertain",
    "figure out": "resolve",
    "set up": "configure",
    "clean up": "sanitize",
    "bring up": "raise",
    "come up with": "devise",
    "go ahead": "proceed",
    "check out": "examine",
}

# Compact unique forms preferred after (or instead of) long jargon —
# keep prediction candidates small while staying monosemous-ish in tech chat.
UNIQUE_COMPACT: dict[str, str] = {
    "obtain": "obt",
    "construct": "ctor",
    "perform": "exec",
    "place": "pos",
    "acquire": "acq",
    "provide": "prov",
    "inspect": "insp",
    "consider": "consid",
    "discuss": "disc",
    "ascertain": "ascrt",
    "resolve": "rsv",
    "configure": "cfg",
    "sanitize": "sanit",
    "raise": "raise",  # already short / clear in tech
    "devise": "devise",
    "proceed": "proc",
    "examine": "exam",
}

# Etymon alignment: prefer a spelling/form that surfaces shared Latin/French roots
# (or a shared short etymon token) so related LTR languages converge.
# Map surface variants → shared etymon tag or common orthography.
ETYMON_ALIGN: dict[str, str] = {
    # information family
    "information": "info",  # shared clipping across EN/FR/ES/DE tech
    "información": "info",
    "informationen": "info",
    "informazione": "info",
    # communication
    "communication": "comm",
    "comunicación": "comm",
    "kommunikation": "comm",
    "comunicazione": "comm",
    # configuration / configurer
    "configuration": "cfg",
    "configuración": "cfg",
    "configurazione": "cfg",
    # document / documento
    "document": "doc",
    "documento": "doc",
    "dokument": "doc",
    # problem / problème / problema
    "problem": "prob",
    "problème": "prob",
    "problema": "prob",
    # function / función
    "function": "fn",
    "función": "fn",
    "funktion": "fn",
    "funzione": "fn",
    # example / ejemplo / exemple
    "example": "ex",
    "ejemplo": "ex",
    "exemple": "ex",
    "beispiel": "ex",
    # number / número / nombre (FR false friend — skip FR nombre)
    "number": "num",
    "número": "num",
    "nummer": "num",
    # answer / respuesta → resp (shared resp- root) / réponse
    "answer": "resp",
    "respuesta": "resp",
    "réponse": "resp",
    "antwort": "resp",
}


def strip_fillers(text: str, *, aggressive: bool = False) -> str:
    """Remove light fillers / interjections. ``aggressive`` enables hedge words like just/like."""
    out = text
    ja = sorted(FILLERS_JA, key=len, reverse=True)
    for f in ja:
        out = out.replace(f, "")

    en = list(FILLERS_EN)
    if not aggressive:
        en = [f for f in en if f not in ("like", "just", "actually", "literally")]
    en.sort(key=len, reverse=True)
    for f in en:
        if " " in f:
            out = re.sub(rf"(?i)\b{re.escape(f)}\b", "", out)
        else:
            out = re.sub(rf"(?i)\b{re.escape(f)}\b", "", out)

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return out.strip()


def apply_unique_readings(text: str, *, compact: bool = True) -> str:
    """Replace polysemous basics with tighter verbs, optionally compact."""
    out = text
    items = sorted(UNIQUE_READINGS.items(), key=lambda kv: len(kv[0]), reverse=True)
    for long, tight in items:
        out = re.sub(rf"(?i)\b{re.escape(long)}\b", tight, out)
    if compact:
        for long, short in sorted(UNIQUE_COMPACT.items(), key=lambda kv: len(kv[0]), reverse=True):
            if long == short:
                continue
            out = re.sub(rf"(?i)\b{re.escape(long)}\b", short, out)
    return out


def apply_etymon_align(text: str) -> str:
    """Collapse related-language surface forms toward a shared short etymon."""
    out = text
    for surface, etymon in sorted(ETYMON_ALIGN.items(), key=lambda kv: len(kv[0]), reverse=True):
        # Case-sensitive for non-ascii; ignore-case for ascii
        if surface.isascii():
            out = re.sub(rf"(?i)\b{re.escape(surface)}\b", etymon, out)
        else:
            out = out.replace(surface, etymon)
            # title-ish
            out = out.replace(surface[:1].upper() + surface[1:], etymon)
    return out
