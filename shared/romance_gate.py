"""Sentence-level gate: keep English-only rewrites out of es / pt / fr sentences.

Spanish/Portuguese ``a`` (preposition/article), French ``a`` (``avoir``), French
``four`` (oven) or ``vous`` are ordinary words there; the English article drop,
spelled-number pass and 3sg ``-s`` fold must not touch them.

The test is deliberately conservative in the *safe* direction: a sentence is
treated as Romance only when it has at least one unambiguous es/pt/fr function
word and more of them than English function words.  Misreading an English
sentence as Romance only keeps an article or a number word (harmless);
misreading Romance as English changes meaning.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

# Function words that are not also common English words (``a``, ``on``, ``no``,
# ``me``, ``in``, ``son``, ``fin`` … are left out on purpose).
_ROMANCE_CUES = frozenset(
    """
    el la los las lo una unos unas del al y que por para con es está están
    estoy son muy pero mi mis su sus yo él ella ellos nosotros usted voy vas
    va vamos van hay ser estar porque cuando donde también
    os um uma uns umas do da dos das em na nas nos é são não com você eu
    vou vai vão sim pelo pela muito mas também ao aos à às
    le les un une des du au aux et est sont je tu il elle ils elles nous vous
    ce cette ces avec pour dans pas ne mais très qui où être avoir ont
    suis sommes êtes été fait faut y
    """.split()
)
_ENGLISH_CUES = frozenset(
    """
    the an is are was were be been am have has had do does did will would
    can could should must shall may might of to and or but with for from
    this that these those it its he she they we you i his her their our my
    your not there here what which who when where why how
    """.split()
)
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?")
# Sentence chunks: up to and including . ! ? (plus closers) or a newline.
_SENT = re.compile(r"[^.!?\n]*(?:[.!?]+[\"'\u201d\u2019)\]]*|\n|$)")


def is_romance(sentence: str) -> bool:
    """True when *sentence* reads as es / pt / fr rather than English."""
    s = unicodedata.normalize("NFC", sentence)
    rom = eng = 0
    for w in _WORD.findall(s):
        lw = w.lower()
        if lw in _ROMANCE_CUES:
            rom += 1
        elif lw in _ENGLISH_CUES:
            eng += 1
        elif "'" in lw or "\u2019" in lw:
            # French elisions: l'eau, d'accord, c'est, j'ai, qu'il, n'est
            head = lw.replace("\u2019", "'").split("'", 1)[0]
            if head in {"l", "d", "c", "j", "qu", "n", "s", "m", "t"} and lw[len(head) + 1 :] not in {
                "s", "t", "re", "ve", "m", "ll", "d"
            }:
                rom += 1
    return rom > 0 and rom > eng


def apply_outside_romance(text: str, fn: Callable[[str], str]) -> str:
    """Apply *fn* to each sentence of *text* that is not es / pt / fr.

    Sentence boundaries and every character of Romance sentences are kept as is.
    """
    if not text:
        return fn(text)
    parts = [m.group(0) for m in _SENT.finditer(text) if m.group(0)]
    if not any(is_romance(p) for p in parts):
        return fn(text)
    return "".join(p if is_romance(p) else fn(p) for p in parts)
