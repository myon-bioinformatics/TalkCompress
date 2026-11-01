#!/usr/bin/env python3
"""TesseraTalk (B): sentence-level language-switch mosaic (layer 2).

Heuristic LID by Unicode script / light cues (not ML). Compress emits a compact
tagged mosaic. With ``rle=True`` (default), consecutive same-lang sentences omit
repeating the lang tag after the first in a run:

  en:Hello.|World.|ja:こんにちは。

Expand accepts both the full ``lang:sent|lang:sent`` form and the RLE form
(missing lang inherits the previous tag).

Translation token-min (opt-in ``translate_min=True`` / ``--translate-min``):
per sentence, pick a shorter bank candidate when ``estimate_tokens`` drops.
EN+ZH+JA was the *starting* mix, not a hard ceiling — Romance (es/fr/pt/it),
Germanic (de/nl/en), Greek (el), and ja/zh are in-scope. Default bank filter
accepts any language present in the fixtures. Live MT is opt-in via
``--translate-engine`` (fixtures stay the pytest-deterministic default): deep/argos
fan out to target langs **in parallel**, then rank by shortness + low 揺らぎ
(ambiguity). Unlike ShorthandEdge (C), B does **not** apply the agreed ledger.

Final token pass (``final_zh_de_token_pass`` / ``--final-zh-de``): last-stage
cheapest-token candidates — compounds (incl. adj+noun), ZH densifiers, short tense
conjugations (live Romance es/fr/pt + nl/el via ``FINAL_TENSE_LANGS``; going-to
guard on progressive *going), then sentence minify restricted to ``zh|de``. Aims
to **reduce** ``estimate_tokens``. Wired by DensityZip as the pipeline end after
A–E (``B-final-zh-de``). Prefer both token+utf8 shrink; token-only wins must be
dictionary-clear and documented. 複合名詞 etc. are labels for candidate forms, not
a noun-only policy. Sibling banks ``pt_el_latin_phrases.json`` /
``pt_el_latin_tense.json`` add living PT/EL/IT and scholarly Latin shorts without
rewriting ``zh_de_phrases`` / ``es_fr_tense``. Surviving Latin-derived abbrevs
(e.g./i.e./etc./vs) stay C.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
import json
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

# Split after terminator, keep terminator on the left sentence. LTR + CJK punct.
_SENT_SPLIT = re.compile(
    r"(?<=[.!?。？！…])"  # after terminator
    r"(?:\s+|(?=[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7afA-Za-z0-9\"'(\[]))"
    # ASCII . ! ? glued to an ASCII letter/digit is not a sentence end
    # (1.2.3, $3.50, example.com, ?q=); expand would rejoin it with a space.
    r"(?<![.!?](?=[A-Za-z0-9]))"
)

_LATIN = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]")
_HIRAGANA = re.compile(r"[\u3040-\u309F]")
_KATAKANA = re.compile(r"[\u30A0-\u30FF]")
_CJK = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF]")
_HANGUL = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_ARABIC = re.compile(r"[\u0600-\u06FF]")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_GREEK = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")

# In-scope language families for B token-min / LID (starting mix was en/zh/ja only).
SCOPE_LANGS: frozenset[str] = frozenset(
    {
        # starting mix
        "en",
        "zh",
        "ja",
        # Romance
        "es",
        "fr",
        "pt",
        "it",
        # Germanic (en already listed)
        "de",
        "nl",
        # Greek
        "el",
    }
)
ROMANCE_LANGS: frozenset[str] = frozenset({"es", "fr", "pt", "it"})
GERMANIC_LANGS: frozenset[str] = frozenset({"en", "de", "nl"})
GREEK_LANGS: frozenset[str] = frozenset({"el"})
FINAL_TOKEN_LANGS: frozenset[str] = frozenset({"zh", "de"})
"""Langs for final-pass *sentence* minify (zh|de). Phrase bank may pick EN acronyms + JA densifiers."""

FINAL_PHRASE_LANGS: frozenset[str] = frozenset({"zh", "de", "en", "ja", "nl", "pt", "el", "it", "la"})
"""Phrase densifier bank: ZH/DE/nl compounds + EN acronyms + pt/el/it/living-la shorts via cheapest."""

FINAL_PT_EL_LATIN_PHRASE_LANGS: frozenset[str] = frozenset({"pt", "el", "it", "la"})
"""Sibling phrase bank langs (pt_el_latin_phrases.json): living PT/EL/IT + scholarly Latin."""

FINAL_TENSE_LANGS: frozenset[str] = frozenset({"es", "fr", "pt", "nl", "de", "el"})
# Person × tense matrix bank (scripts/tense_matrix.py) also allows live it.
FINAL_TENSE_MATRIX_LANGS: frozenset[str] = frozenset({"es", "fr", "pt", "nl", "de", "el", "it", "cs", "pl"})
"""Tense densifier bank langs: live Romance + Dutch + German + Greek (classical Latin conjugations skipped)."""

# de-over-nl tie rule: when a German and a Dutch candidate tie on
# (estimate_tokens, utf8 bytes), German wins; Dutch is kept only where it is
# strictly cheaper. Against other languages the plain token → utf8 → len → form
# order applies unchanged.
# Wider-readership tie rule: on an exact (tokens, utf8) tie es/fr/pt beat
# it/cs/pl (more speakers / readers; meaning carries further).
_ROMANCE_MAJOR: tuple[str, ...] = ("es", "fr", "pt")
_TIE_PREFER: dict[str, tuple[str, ...]] = {
    "nl": ("de",),
    "it": _ROMANCE_MAJOR,
    "cs": _ROMANCE_MAJOR,
    "pl": _ROMANCE_MAJOR,
}


def prefer_on_tie(best: tuple[str, str], cands: list[tuple[str, str]], metric) -> tuple[str, str]:
    """Return a preferred-lang candidate that ties ``best`` on ``metric``, else ``best``."""
    want = _TIE_PREFER.get(best[1])
    if not want:
        return best
    m = metric(best[0])
    ties = [c for c in cands if c[1] in want and metric(c[0]) == m]
    if not ties:
        return best
    return min(ties, key=lambda c: (len(c[0]), c[0]))

_CUES: dict[str, tuple[str, ...]] = {
    "en": (
        "the", "and", "is", "are", "you", "this", "that", "with", "for", "not", "of", "to",
        "hello", "thanks", "please", "friend", "friends",
    ),
    "es": (
        "el", "la", "los", "las", "que", "y", "de", "en", "un", "una", "por", "con",
        "está", "estan", "estás", "para", "como", "más", "pero", "sí", "también",
        "hola", "gracias", "buenos", "buenas", "amigos", "amigo", "usted", "dónde",
        "cómo", "días", "noches",
    ),
    "fr": (
        "le", "la", "les", "des", "une", "est", "que", "dans", "pour", "avec",
        "pas", "plus", "tout", "nous", "vous", "être", "cette",
        "bonjour", "merci", "comment", "allez", "aujourd", "salut", "bonne",
    ),
    "de": (
        "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "mit", "auf",
        "den", "dem", "des", "ich", "sie", "wir", "auch", "aber", "werden",
        "guten", "tag", "morgen", "wie", "geht", "ihnen", "bitte", "danke",
        "nicht", "oder", "sehr", "gut", "herr", "frau",
    ),
    "pt": (
        "o", "a", "os", "as", "que", "de", "em", "um", "uma", "não", "para",
        "com", "por", "mais", "como", "está", "também",
        "olá", "obrigado", "obrigada", "você", "não", "escola", "hoje", "posso",
    ),
    "it": (
        "il", "lo", "la", "gli", "le", "che", "di", "per", "con", "una", "sono", "non",
        "dei", "della", "questo", "anche", "come", "più",
        "ciao", "grazie", "stai", "sono", "buongiorno", "prego", "sicuro",
    ),
    "nl": (
        "de", "het", "een", "van", "en", "is", "niet", "met", "voor", "op", "zijn",
        "ik", "hij", "zij", "ook", "maar", "naar", "dat", "dit",
        "voorbeeld", "nederlands", "goedemorgen", "alsjeblieft", "dank",
    ),
    "el": (
        "και", "το", "η", "του", "την", "να", "με", "για", "από", "είναι",
        "δεν", "που", "στο", "της", "των", "γεια", "σου", "τι", "κάνεις", "καλημέρα",
    ),
    "id": ("yang", "dan", "dengan", "untuk", "tidak", "ini", "itu", "ada", "dari", "pada"),
    "sv": ("och", "att", "det", "är", "en", "ett", "som", "för", "med", "inte", "på"),
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
        "greek": len(_GREEK.findall(s)),
    }


def _cue_hits(s: str, lang: str) -> int:
    cues = _CUES.get(lang, ())
    if lang == "ja":
        return sum(1 for c in cues if c in s)
    if lang == "el":
        words = re.findall(r"[\u0370-\u03FFa-zà-ÿ']+", s.lower())
        return sum(1 for w in words if w in cues)
    low = s.lower()
    words = re.findall(r"[a-zà-ÿ']+", low)
    return sum(1 for w in words if w in cues)


def script_mix(text: str) -> dict[str, int | float]:
    """Public diagnostics: per-script char counts and simple ratios."""
    sc = _script_scores(text)
    total = sum(sc.values()) or 1
    ratios = {f"{k}_ratio": round(v / total, 4) for k, v in sc.items()}
    return {**sc, "total_script_chars": total, **ratios}


def detect_lang(sentence: str, *, prefer_ltr: bool = False) -> str:
    """Heuristic language tag for one sentence.

    With ``prefer_ltr=True``, Latin+CJK mixes that lack hiragana/katakana bias
    toward ``en`` (or cue-winning LTR) rather than ``zh``. Pure CJK without kana
    still returns ``zh``.
    """
    sentence = unicodedata.normalize("NFC", sentence)
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
    if sc["greek"] / total_script > 0.3:
        return "el"

    # Latin present: prefer LTR tagging (especially under prefer_ltr with CJK mix)
    latinish = sc["latin"] / total_script > 0.2 or sc["latin"] > 0
    cjk_no_kana = sc["cjk"] > 0 and sc["hira"] + sc["kata"] == 0

    if latinish:
        scores = {
            "en": _cue_hits(sentence, "en"),
            "es": _cue_hits(sentence, "es"),
            "fr": _cue_hits(sentence, "fr"),
            "de": _cue_hits(sentence, "de"),
            "pt": _cue_hits(sentence, "pt"),
            "it": _cue_hits(sentence, "it"),
            "nl": _cue_hits(sentence, "nl"),
            "id": _cue_hits(sentence, "id"),
            "sv": _cue_hits(sentence, "sv"),
        }
        # Distinctive orthography / greeting boosts
        low = sentence.lower()
        if re.search(r"[äöüß]", low):
            scores["de"] = scores.get("de", 0) + 2
        if re.search(r"\b(guten|tag|morgen|danke|bitte|ihnen)\b", low):
            scores["de"] = scores.get("de", 0) + 2
        if "ñ" in low or "¿" in sentence or "¡" in sentence:
            scores["es"] = scores.get("es", 0) + 2
        if re.search(r"\b(hola|gracias|amigos|buenos|buenas)\b", low):
            scores["es"] = scores.get("es", 0) + 2
        if re.search(r"[ãõ]", low) or "não" in low or "olá" in low:
            scores["pt"] = scores.get("pt", 0) + 2
        if re.search(r"\b(bonjour|merci|allez-vous|aujourd)\b", low):
            scores["fr"] = scores.get("fr", 0) + 2
        if re.search(r"[àâæçéèêëôœùûü]", low) and ("ç" in low or "œ" in low):
            scores["fr"] = scores.get("fr", 0) + 1
        if re.search(r"\b(gli|della|dei|sono|ciao|grazie)\b", low):
            scores["it"] = scores.get("it", 0) + 2
        if re.search(r"\b(het|niet|zijn|voor|nederlands|voorbeeld)\b", low):
            scores["nl"] = scores.get("nl", 0) + 2
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        # Mixed Latin+CJK without kana: avoid zh when prefer_ltr (or always for mix)
        if cjk_no_kana and (prefer_ltr or sc["latin"] >= sc["cjk"]):
            return "en"
        if cjk_no_kana and prefer_ltr:
            return "en"
        return "en"

    if sc["cjk"] > 0 and sc["hira"] + sc["kata"] == 0 and sc["latin"] == 0:
        return "zh"
    if sc["cjk"] > 0:
        return "zh"
    return "und"


def tag_sentences(
    text: str,
    langs: list[str] | None = None,
    *,
    preserve_newlines: bool = False,
    prefer_ltr: bool = False,
) -> list[tuple[str, str]]:
    """Tag each sentence. If langs is given and non-empty, use as fallback cycle
    only when detector returns 'und'; otherwise prefer heuristic LID.

    With ``preserve_newlines=True``, blank-line paragraph breaks become a synthetic
    ``¶`` sentence so mosaic expand can restore paragraph structure.
    ``prefer_ltr`` biases Latin+CJK mixes (no kana) toward en rather than zh.
    """
    if preserve_newlines and "\n" in text:
        blocks = re.split(r"(\n\s*\n+)", text.strip())
        sents: list[str] = []
        for block in blocks:
            if re.fullmatch(r"\n\s*\n+", block or ""):
                sents.append("¶")
                continue
            sents.extend(segment(block))
    else:
        sents = segment(text)
    fallback = langs if langs else ["und"]
    tagged: list[tuple[str, str]] = []
    for i, s in enumerate(sents):
        if s == "¶":
            tagged.append(("¶", "¶"))
            continue
        lang = detect_lang(s, prefer_ltr=prefer_ltr)
        if lang == "und" and fallback:
            lang = fallback[i % len(fallback)]
        tagged.append((lang, s))
    return tagged


def render(tagged: list[tuple[str, str]]) -> str:
    return "\n".join(f"[{lang}] {sent}" for lang, sent in tagged)


def compress(
    text: str,
    langs: list[str] | None = None,
    *,
    rle: bool = True,
    preserve_newlines: bool = False,
    prefer_ltr: bool = False,
    translate_min: bool = False,
    translation_bank: str | Path | None = None,
    translate_engine: str = "fixture",
) -> str:
    """Compact mosaic. With ``rle=True`` (default), omit repeating lang tags in a run:

    ``en:Hello.|World.|ja:こんにちは。``

    With ``rle=False``: full ``lang:sent|lang:sent`` (legacy-compatible).
    ``preserve_newlines`` keeps paragraph breaks as ``¶:¶`` tiles.
    With ``translate_min=True``, first rewrite each sentence to a shorter bank
    (or opt-in live) translation when tokens drop — not C ledger.
    """
    if translate_min:
        text = minify_by_translation(
            text,
            bank_path=translation_bank,
            preserve_newlines=preserve_newlines,
            translate_engine=translate_engine,
        )
    tagged = tag_sentences(
        text, langs, preserve_newlines=preserve_newlines, prefer_ltr=prefer_ltr
    )
    parts: list[str] = []
    prev_lang: str | None = None
    for lang, sent in tagged:
        if lang == "¶":
            parts.append("¶:¶")
            prev_lang = None
            continue
        safe = sent.replace("|", r"\|")
        if rle and prev_lang is not None and lang == prev_lang:
            parts.append(safe)
        else:
            parts.append(f"{lang}:{safe}")
        prev_lang = lang
    return "|".join(parts)


def expand(mosaic: str, *, preserve_newlines: bool = False) -> str:
    """Expand mosaic back to plain text. Accepts full tags and RLE (inherit lang).

    With ``preserve_newlines=True``, ``¶:¶`` / ``¶`` tiles become blank-line breaks.
    """
    if not mosaic.strip():
        return ""
    parts = re.split(r"(?<!\\)\|", mosaic.strip())
    sentences: list[str] = []
    cur_lang: str | None = None
    for part in parts:
        part = part.replace(r"\|", "|")
        if part in ("¶:¶", "¶") or part.startswith("¶:"):
            sentences.append("¶")
            continue
        m = re.match(r"^([a-zA-Z]{2,8}(?:-[a-zA-Z0-9]+)?):(.*)$", part, re.DOTALL)
        if m:
            cur_lang = m.group(1)
            body = m.group(2)
        else:
            body = part
        body = body.strip()
        if body:
            sentences.append(body)
        _ = cur_lang
    out: list[str] = []
    for i, s in enumerate(sentences):
        if s == "¶":
            if preserve_newlines:
                out.append("\n\n")
            continue
        if not out:
            out.append(s)
            continue
        prev = out[-1]
        if prev.endswith("\n\n"):
            out.append(s)
        elif re.search(r"[。？！]$", prev) or re.match(r"^[\u3040-\u30ff\u3400-\u9fff]", s):
            out.append(s)
        else:
            out.append(" " + s)
    return "".join(out)


def stats(
    text: str,
    langs: list[str] | None = None,
    *,
    prefer_ltr: bool = False,
) -> dict:
    """Sentence count, language histogram, and script_mix for tagged input text."""
    tagged = tag_sentences(text, langs, prefer_ltr=prefer_ltr)
    hist = Counter(lang for lang, _ in tagged)
    return {
        "sentences": len(tagged),
        "langs": dict(sorted(hist.items())),
        "script_mix": script_mix(text),
    }


# --- translation token-min (deterministic bank; live MT opt-in) ---

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_TRANSLATION_BANK = _FIXTURES_DIR / "translations.json"
DEFAULT_ZH_DE_PHRASE_BANK = _FIXTURES_DIR / "zh_de_phrases.json"
DEFAULT_ES_FR_TENSE_BANK = _FIXTURES_DIR / "es_fr_tense.json"
DEFAULT_PT_EL_LATIN_PHRASE_BANK = _FIXTURES_DIR / "pt_el_latin_phrases.json"
DEFAULT_PT_EL_LATIN_TENSE_BANK = _FIXTURES_DIR / "pt_el_latin_tense.json"
DEFAULT_EN_WORDLIST = _FIXTURES_DIR / "en_wordlist.txt"
DEFAULT_TENSE_MATRIX_BANK = Path(__file__).resolve().parent / "fixtures" / "tense_matrix.json"
TRANSLATE_ENGINES = ("fixture", "argos", "deep")

_CJK_CHAR = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]")
_LATIN_WORD = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u1E00-\u1EFF']+")
# Latin Extended Additional (Vietnamese stacked diacritics: ạ ế ộ …): BPE vocabularies
# rarely merge these, so each such char costs ≈ 1 extra token on top of the subword rule.
_LATIN_EXT_ADD = re.compile(r"[\u1E00-\u1EFF]")
# Thai (U+0E00–U+0E7F): unspaced script, ≈ 1 token per character in GPT-style BPE.
_THAI_CHAR = re.compile(r"[\u0E00-\u0E7F]")
# Cyrillic / Arabic / Devanagari / Greek letter-runs
_OTHER_WORD = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0370-\u03FF\u1F00-\u1FFF]+"
)


DEFAULT_O200K_CALIB = _FIXTURES_DIR / "o200k_calib.json"
# o200k-style pre-tokens: a Latin letter-run (+ optional English contraction
# suffix, which o200k keeps in the same pre-token: ``we've`` = 1), digit groups
# of <= 3, one CJK/kana/Hangul/Thai char, an other-script run, a punctuation run.
_PRETOKEN = re.compile(
    # Combining marks that survive NFC (x + U+0301, i + U+0307) stay inside the word.
    r"(?P<w>[A-Za-z\u00C0-\u024F\u1E00-\u1EFF][A-Za-z\u00C0-\u024F\u1E00-\u1EFF\u0300-\u036F]*"
    r"(?:['\u2019](?:s|t|re|ve|m|ll|d)(?![A-Za-z]))?)"
    r"|(?P<d>\d{1,3})"
    r"|(?P<k>[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]+)"
    r"|(?P<c>[\u0E00-\u0E7F]+)"
    # Non-BMP chars outside o200k's vocabulary (CJK Ext B–H, Supplementary PUA-A/B):
    # o200k falls back to raw UTF-8 bytes, so each costs ≈ its 4 bytes.
    r"|(?P<b>[\U00020000-\U000323AF\U000F0000-\U0010FFFF])"
    # Emoji runs (skin-tone modifiers, ZWJ sequences, VS16): costed from a measured table.
    r"|(?P<e>[\u2190-\u2BFF\u200d\ufe0f\U0001F000-\U0001FAFF\U000E0020-\U000E007F]*"
    r"[\u200d\U0001F000-\U0001FAFF][\u2190-\u2BFF\u200d\ufe0f\U0001F000-\U0001FAFF\U000E0020-\U000E007F]*)"
    r"|(?P<o>[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0370-\u03FF\u1F00-\u1FFF]+)"
    # Letters of any other script (Hebrew, Armenian, Georgian, …) must not cost 0.
    # Indic / SE-Asian blocks keep the main-branch path: ceil(len/4) split at every vowel
    # sign drifts further from o200k there. Fixed ranges, not unicodedata, so the result
    # does not depend on the Python version.
    r"|(?P<x>(?:(?![\u0900-\u109F\u1780-\u17FF\U00020000-\U000323AF])[^\W\d_])+)"
    r"|(?P<p>[^\w\s]+)",
    re.IGNORECASE,
)
_GREEK = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
# Historical name: this range covers Latin Extended-A AND Extended-B, not a
# Polish/Czech language detector. Other languages and transliterations can match.
_LATIN_EXT_A = re.compile(r"[\u0100-\u024F]")
# Author-reported #108 exceptions (Turkish ı ğ ş İ, Vietnamese đ): no +1 in
# the class-s heuristic. These are not a general accuracy guarantee; see README.
_O200K_MERGED_EXT = "\u0131\u0130\u011f\u011e\u015f\u015e\u0111\u0110"
_LATIN_EXT_SPLIT = re.compile(r"[^\W\d_" + _O200K_MERGED_EXT + r"]")
# Vietnamese syllable: tone letters U+1EA0–U+1EF9 only (not transliteration ḥ ṣ ẓ / ā ī),
# plus ASCII and the Vietnamese-only Latin letters đ ă ơ ư ĩ ũ and Latin-1 accents.
_VI_SYLLABLE = re.compile(r"[a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169]*[\u1EA0-\u1EF9][a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169\u1EA0-\u1EF9]*", re.IGNORECASE)
_VI_LETTER = re.compile(r"[\u1EA0-\u1EF9]")
_VI_RARE = re.compile("[\u1EB4\u1EB5\u1EB2\u1EB3\u1EAA\u1EAB\u1EBC\u1EBD\u1EF8\u1EF9\u1EF6\u1EF7\u1EF4\u1EF5]")  # ẵ ẳ ẫ ẽ ỹ ỷ ỵ
_COMBINING_RE = re.compile(r"[\u0300-\u036F]")
# A word spelled only with Vietnamese letters (ASCII + Latin-1 accents + đ ă ơ ư ĩ ũ + tone letters).
_VI_WORD = re.compile(r"[a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169\u1EA0-\u1EF9]+", re.IGNORECASE)
_CALIB: dict | None = None


def _pretokens(s: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group()) for m in _PRETOKEN.finditer(s)]


def _wclass(w: str) -> str:
    """Character-range class, not language ID: ``v`` Latin Extended Additional
    (U+1E00–U+1EFF, takes priority), ``s`` Latin Extended-A/B (U+0100–U+024F),
    ``x`` other accents, ``a`` ASCII. The cost rules are approximate."""
    if _GREEK.search(w):
        return "g"
    if _OTHER_WORD.search(w):
        return "o"
    if _LATIN_EXT_ADD.search(w):
        return "v"
    if _LATIN_EXT_A.search(w):
        return "s"
    return "a" if w.isascii() else "x"


def _fallback_cost(w: str, len_table: dict, suffixes: dict | None = None, floor: dict | None = None) -> int:
    """Cost of a word in no table: calibrated per (class, length) plus a suffix delta
    (e.g. Romance futures ``-rei``/``-ré`` split off), else the legacy ceil(len/4) rule."""
    k = f"{_wclass(w)}{len(w)}"
    if k[0] == "v" and _VI_SYLLABLE.fullmatch(w):
        # Vietnamese syllables (tones in U+1E00–U+1EFF) are mostly a single o200k token
        # (" tiếng" " Việt" " người" = 1): the old per-char +1 overestimated them.
        # tone letters that are rare in o200k's training data split off (" Nẵng" = 3, " Huế" = 2)
        return max(1, (len(w) + 5) // 6) + (1 if _VI_RARE.search(w) else 0)
    if k in len_table:
        if len(w) < 5:
            return len_table[k]
        fl, sx = floor or {}, suffixes or {}
        f = fl.get(w[-3:], fl.get(w[-2:]))
        if f is not None:  # documented floor rule wins over learned deltas
            return max(f, len_table[k])
        return max(1, len_table[k] + sx.get(w[-3:], sx.get(w[-2:], 0)))
    if k[0] == "g":  # Greek: o200k merges it poorly, ≈ ceil(len/2) beyond 3 letters
        return 1 if len(w) <= 3 else (len(w) + 1) // 2
    if k[0] == "s":  # Broad Latin Extended-A/B heuristic, excluding the #108 exceptions.
        return max(1, (len(w) + 3) // 4) + sum(
            1 for c in _LATIN_EXT_A.findall(w) if _LATIN_EXT_SPLIT.match(c)
        )
    return max(1, (len(w) + 3) // 4) + len(_LATIN_EXT_ADD.findall(w))


def _load_calib() -> dict:
    """Lazy-load the committed o200k calibration table (missing file -> legacy heuristic)."""
    global _CALIB
    if _CALIB is None:
        c: dict = {"en": {}, "len_table": {}, "contractions": {}, "exceptions": {}, "suffixes": {}, "suffix_floor": {}, "cjk": frozenset()}
        if DEFAULT_O200K_CALIB.exists():
            import base64

            d = json.loads(DEFAULT_O200K_CALIB.read_text(encoding="utf-8"))
            words = sorted(load_en_wordlist())
            packed = base64.b64decode(d["en_costs"])
            if len(packed) == (len(words) + 3) // 4:
                c["en"] = {w: ((packed[i >> 2] >> ((i & 3) * 2)) & 3) + 1 for i, w in enumerate(words)}
            c["len_table"] = d.get("len_table", {})
            c["contractions"] = d.get("contractions", {})
            c["exceptions"] = d.get("exceptions", {})
            c["suffixes"] = d.get("suffixes", {})
            c["suffix_floor"] = d.get("suffix_floor", {})
            c["cased"] = d.get("exceptions_cased", {})
            c["cjk_sp"] = frozenset(d.get("cjk_space_vocab", "").split())
            c["sym"] = frozenset(d.get("symbol_vocab", ""))
            c["cjk"] = frozenset(d.get("cjk_vocab", "").split())
            c["th"] = frozenset(d.get("thai_vocab", "").split())
            c["th_sp"] = frozenset(d.get("thai_space_vocab", "").split())
            c["vi_sp"] = frozenset(d.get("vi_space_vocab", "").split())
            c["emoji"] = _unpack_emoji(d.get("emoji_costs", {}))
        _CALIB = c
    return _CALIB


def _word_cost(w: str, cal: dict) -> int:
    if w in cal.get("cased", ()):
        return cal["cased"][w]
    lw = w.lower().replace("\u2019", "'")
    for t in ("exceptions", "contractions", "en"):
        if lw in cal[t]:
            return cal[t][lw]
    if "'" in lw:  # unknown contraction: stem + suffix
        stem, _, _ = lw.partition("'")
        return _word_cost(stem, cal) + 1
    return _fallback_cost(lw, cal["len_table"], cal["suffixes"], cal["suffix_floor"])


def _unpack_emoji(d: dict) -> dict:
    """``{"ranges": [[start, "digits"], ...], "vs16": "chars"}`` -> {str: o200k cost}."""
    out: dict = {}
    for start, digits in d.get("ranges", []):
        for i, ch in enumerate(digits):
            out[chr(start + i)] = int(ch)
    for ch in d.get("vs16", ""):
        out[ch + "\ufe0f"] = 1  # e.g. "❤️" (U+2764 U+FE0F) is a single o200k token
    return out


def _emoji_cost(run: str, table: dict) -> int:
    """Sum of per-codepoint o200k costs (measured: a ZWJ / skin-tone sequence costs the sum
    of its parts, 👨‍👩‍👧‍👦 = 2+1+2+1+2+1+2 = 11); a base + VS16 pair can merge to 1."""
    n = i = 0
    while i < len(run):
        if run[i:i + 2] in table:
            n += table[run[i:i + 2]]
            i += 2
            continue
        n += table.get(run[i], len(run[i].encode("utf-8")))
        i += 1
    return n


def _thai_cost(run: str, vocab: frozenset, space: bool, sp_vocab: frozenset) -> int:
    """Greedy longest match against o200k's Thai tokens (≤ 17 chars); else 1 per char.
    After a space, a leading word o200k merges with the space is one token; otherwise
    the bare space costs its own token."""
    n = 0
    i = 0
    if space:
        for L in range(min(17, len(run)), 0, -1):
            if run[:L] in sp_vocab:
                n, i = 1, L
                break
        else:
            n = 1
    while i < len(run):
        for L in range(min(17, len(run) - i), 1, -1):
            if run[i:i + L] in vocab:
                i += L
                break
        else:
            i += 1
        n += 1
    return n


def _cjk_cost(run: str, vocab: frozenset) -> int:
    """Greedy longest match (4..2 chars) against o200k's CJK multi-char tokens; else 1 per char."""
    n = i = 0
    while i < len(run):
        for L in (4, 3, 2):
            if run[i:i + L] in vocab:
                i += L
                break
        else:
            i += 1
        n += 1
    return n


def estimate_tokens(text: str) -> int:
    """Stdlib-only token estimate calibrated toward o200k_base (no tiktoken at runtime).

    Splits like o200k's pre-tokenizer, then costs each piece:
    - Latin word (+ English contraction suffix): committed o200k table lookup
      (``fixtures/o200k_calib.json``: English wordlist costs, contractions,
      training-split exceptions), else a calibrated per-(class, length) fallback,
      else ``max(1, ceil(len/4))`` plus the character-range heuristic: class-s
      Latin Extended-A/B letters excluding the #108 exceptions, or U+1E00–U+1EFF
      characters for the other Latin fallback. This is not an exact token count.
    - CJK / kana / Hangul runs: greedy longest match against the committed o200k
      multi-char token list (``cjk_vocab``), else 1 per character
    - Thai runs: greedy longest match against o200k's Thai tokens (``thai_vocab``)
    - Vietnamese words after a space: 1 if o200k has " word" (``vi_space_vocab``), else >= 2
    - emoji runs (skin tone, ZWJ, VS16): sum of measured per-code-point costs (``emoji_costs``)
    - CJK Ext B–H / Supplementary PUA chars (no vocab token): UTF-8 bytes (4 each)
    - other-script runs (Greek, Cyrillic, Arabic, Devanagari) go through the same
      tables (own classes in the fallback)
    - digit groups of <= 3 = 1; each punctuation run = 1
    Whitespace is free. Regenerate the table with ``scripts/calibrate_estimate.py --write``.
    """
    if not text or not text.strip():
        return 0
    s = unicodedata.normalize("NFC", text)
    cal = _load_calib()
    vi_text = _VI_LETTER.search(s) is not None
    n = 0
    for m in _PRETOKEN.finditer(s):
        kind, p = m.lastgroup, m.group()
        if kind in ("w", "o"):
            # a combining mark left after NFC is its own byte-level token in o200k
            spaced = m.start() > 0 and s[m.start() - 1] == " "
            if spaced and not p.isascii() and (vi_text or _VI_SYLLABLE.fullmatch(p)) and _VI_WORD.fullmatch(p):
                # Vietnamese: o200k has many syllables as one " syllable" token (case-sensitive,
                # " tiếng" = 1 but " Tiếng" = 2); one it lacks splits into >= 2 (" phê" " Huế" = 2).
                # Unspaced words keep the #120 rule below (word cost + 1).
                n += 1 if p in cal.get("vi_sp", ()) else max(2, _word_cost(p, cal))
            else:
                n += _word_cost(p, cal) + len(_COMBINING_RE.findall(p))
            if (m.start() == 0 or s[m.start() - 1] != " ") and (
                _VI_SYLLABLE.fullmatch(p) or (vi_text and not p.isascii())
            ):
                # without a leading space o200k splits a Vietnamese syllable ("biết" = 2,
                # " biết" = 1); in Vietnamese text this also holds for "Hà" / "Đà" (2 vs " Hà" = 1)
                n += 1
        elif kind == "k":
            if m.start() == 0 or s[m.start() - 1] == " ":
                # o200k merges the preceding space only into some CJK tokens
                # (" 开" yes, " 绿" no: the bare space then costs its own token)
                for L in (4, 3, 2, 1):
                    if p[:L] in cal["cjk_sp"]:
                        n += 1 + (_cjk_cost(p[L:], cal["cjk"]) if p[L:] else 0)
                        break
                else:
                    n += 1 + _cjk_cost(p, cal["cjk"])
            else:
                n += _cjk_cost(p, cal["cjk"])
        elif kind == "c":
            n += _thai_cost(p, cal.get("th", frozenset()), m.start() > 0 and s[m.start() - 1] == " ",
                            cal.get("th_sp", frozenset()))
        elif kind == "b":  # no vocabulary token: raw UTF-8 bytes
            n += len(p.encode("utf-8"))
        elif kind == "e":
            n += _emoji_cost(p, cal.get("emoji", {}))
        elif kind == "x":  # uncalibrated script: legacy ceil(len/4)
            n += (len(p) + 3) // 4  # len >= 1, so always >= 1
        elif kind == "p":
            # a punctuation run is one token; non-ASCII symbols outside o200k's
            # single-token set (e.g. "∴") cost one extra byte-level token each
            n += 1 + sum(1 for ch in p if ord(ch) > 127 and ch not in cal["sym"])
        else:
            n += 1
    if s != text:
        n += _nfd_extra(text, cal)
    return n


def _nfd_extra(text: str, cal: dict) -> int:
    """o200k sees the raw (non-NFC) bytes: a decomposed accent is its own token and splits
    the word at the mark. For each raw Latin word that NFC would change, add the gap between
    the split cost (pieces + 1 per mark) and the NFC-word cost already counted."""
    extra = 0
    for m in _PRETOKEN.finditer(text):
        w = m.group()
        if m.lastgroup != "w" or not _COMBINING_RE.search(w):
            continue
        c = unicodedata.normalize("NFC", w)
        if c == w:
            continue
        split = sum(_word_cost(q, cal) for q in _COMBINING_RE.split(w) if q) + len(_COMBINING_RE.findall(w))
        extra += max(0, split - (_word_cost(c, cal) + len(_COMBINING_RE.findall(c))))
    return extra


# zh stative verbs: 在 + V is the progressive marker, but statives (have / know /
# want / be / like / need …) cannot take it (``我在有`` is ill-formed).
ZH_STATIVE_VERBS = frozenset("有知要是像爱喜需认懂会能想属值")
# lookbehind skips lexical 在-words (现在 now, 存在 exist, 实在, 所在, 自在, 好在).
_ZH_PROG_STATIVE = re.compile(r"(?<![现存实所自好])在(" + "|".join(sorted(ZH_STATIVE_VERBS)) + r")")


def zh_stative_progressive(form: str) -> list[str]:
    """Return stative verbs that wrongly carry progressive 在 in a zh form.

    Only flags 在 directly followed by a stative verb character; locative 在
    (``猫在桌下``) is untouched because 桌 is not stative. Known stative
    compounds that start with 在 are not special-cased (none in the banks).
    """
    return [m.group(1) for m in _ZH_PROG_STATIVE.finditer(unicodedata.normalize("NFC", form))]


def _norm_lookup_key(s: str) -> str:
    s = unicodedata.normalize("NFC", s.strip())
    # Strip trailing sentence punct for lookup flexibility
    s = re.sub(r"[.!?。？！…]+$", "", s).strip()
    # Latin-heavy → lowercase; pure CJK stays
    if _LATIN.findall(s) and not _CJK.findall(s) and not _HIRAGANA.findall(s):
        return s.lower()
    if _LATIN.findall(s):
        return s.lower()
    return s


@lru_cache(maxsize=4)
def load_translation_bank(path: str | None = None) -> dict[str, Any]:
    """Load deterministic translation candidate bank (JSON)."""
    p = Path(path) if path is not None else DEFAULT_TRANSLATION_BANK
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"translation bank missing entries: {p}")
    return data


def translation_index(
    path: str | Path | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Map normalized source → list of (lang, candidate_text).

    ``candidates`` may map lang → str **or** lang → list[str] (EN paraphrases).
    Multiple EN forms are kept so ``pick_shortest_translation`` can EN-first
    ``select_cheapest`` (token→utf8) before cross-lang.
    """
    data = load_translation_bank(str(path) if path is not None else None)
    idx: dict[str, list[tuple[str, str]]] = {}
    for entry in data.get("entries") or []:
        cands = entry.get("candidates") or {}
        pairs: list[tuple[str, str]] = []
        for lang, text in cands.items():
            if text is None or text == "":
                continue
            if isinstance(text, list):
                for t in text:
                    t = str(t).strip()
                    if t:
                        pairs.append((str(lang), t))
            else:
                pairs.append((str(lang), str(text)))
        for src in entry.get("from") or []:
            key = _norm_lookup_key(str(src))
            if not key:
                continue
            idx.setdefault(key, [])
            # merge unique
            seen = {(a, b) for a, b in idx[key]}
            for pair in pairs:
                if pair not in seen:
                    idx[key].append(pair)
                    seen.add(pair)
    return idx


def ambiguity_penalty(text: str) -> int:
    """Token-equivalent 揺らぎ (ambiguity) penalty. Higher → worse for ranking.

    Intentional natural short forms (ASAP, FYI, Ciao, CJK densifiers) stay at 0.
    Very short polysemous Latin tokens (set/run/table/bank/…) get a heavy penalty
    so a wavy short can lose to a slightly longer clearer candidate or to original.
    """
    s = unicodedata.normalize("NFC", (text or "").strip())
    if not s:
        return 99
    # Intentional abbrevs / greetings — do not punish
    intentional = {
        "asap", "fyi", "imo", "imho", "btw", "tba", "tbd", "eta", "faq",
        "ciao", "hola", "merci", "gracias", "danke", "obrigado", "obrigada",
        "ok", "okay", "yes", "oui", "sí", "si", "ja", "nein", "non", "não",
    }
    # strip trailing punct for lookup
    bare = re.sub(r"[.!?。？！…,，、]+$", "", s).strip()
    low = bare.lower()
    if low in intentional:
        return 0
    # Pure CJK / kana / Hangul / Greek densifiers: low 揺らぎ for B ranking
    if _CJK_CHAR.fullmatch(bare) or _GREEK.fullmatch(bare):
        return 0
    if not _LATIN.search(bare) and (_CJK.search(bare) or _GREEK.search(bare)):
        return 0

    wavy = {
        "set", "run", "get", "put", "make", "take", "go", "do", "it", "a", "an",
        "the", "to", "of", "in", "on", "at", "by", "for", "or", "and", "as",
        "table", "bank", "light", "right", "left", "just", "cool", "fine",
        "well", "fair", "mean", "line", "type", "form", "case", "point",
        "check", "call", "draw", "play", "watch", "match", "order", "charge",
        "current", "plain", "note", "book", "file", "key", "code", "base",
        "stock", "share", "interest", "party", "state", "power", "force",
        "class", "subject", "object", "figure", "number", "scale", "range",
        "term", "period", "date", "time", "space", "field", "area", "volume",
        "da", "se", "le", "la", "el", "un", "une", "de", "en", "para",
    }
    words = re.findall(r"[A-Za-z\u00C0-\u024F']+", low)
    if not words:
        return 0
    # Single-token wavy Latin short form — heavy enough that it usually loses
    # to original alone, and always loses near-ties to a clearer candidate.
    if len(words) == 1 and words[0] in wavy:
        return 12
    if len(words) == 1 and len(words[0]) <= 3:
        # ultra-short Latin singleton without intentional whitelist
        return 8
    # Multi-word but dominated by wavy content words
    content = [w for w in words if w not in {"the", "a", "an", "to", "of", "in", "on", "at", "by", "for", "or", "and", "as"}]
    if content and all(w in wavy for w in content) and len(content) <= 2:
        return 6
    # Collision cue: candidate equals a known wavy lemma exactly
    if low in wavy:
        return 12
    return 0


def score_translation_candidate(
    candidate: str,
    *,
    src_tokens: int,
) -> tuple[int, int, int] | None:
    """Rank key for a candidate. Lower tuple wins. ``None`` → discard.

    Primary: ``estimate_tokens`` + ``ambiguity_penalty`` (揺らぎ). Empty / error
    strings discarded. Must beat ``src_tokens`` on the composite score to win.
    """
    cand = unicodedata.normalize("NFC", (candidate or "").strip())
    if not cand:
        return None
    n = estimate_tokens(cand)
    if n <= 0:
        return None
    pen = ambiguity_penalty(cand)
    effective = n + pen
    # Must improve on original's token count via effective score
    if effective >= src_tokens:
        return None
    return (effective, pen, n)  # near-ties: lower 揺らぎ before raw shortness


def pick_shortest_translation(
    sentence: str,
    candidates: list[tuple[str, str]] | dict[str, str] | None = None,
    *,
    bank_path: str | Path | None = None,
    allow_langs: set[str] | None = None,
    prefer_low_ambiguity: bool = True,
) -> tuple[str, str, int]:
    """Pick original or a shorter translation candidate by ``estimate_tokens``.

    Returns ``(chosen_text, lang_or_'src', token_count)``.
    Keeps the original when nothing is strictly shorter (ties → original).
    With ``prefer_low_ambiguity=True`` (default), also applies 揺らぎ penalty so
    a wavy short can lose to a slightly longer clearer candidate or to original.

    **EN-first:** when multiple ``en`` paraphrase candidates beat the source,
    collapse them with token → utf8 → len (same as ``select_cheapest_form`` /
    ``_cheapest_repl``) to **one** EN, then compete that EN against cross-lang.
    Does not force EN over a cheaper ZH/JA densifier.

    ``allow_langs=None`` (default) accepts **any** bank language — EN+ZH+JA is
    not a hard ceiling. Pass a set to restrict (e.g. Romance-only).
    Does **not** consult the C ShorthandEdge ledger.
    """
    src = unicodedata.normalize("NFC", sentence.strip())
    if not src:
        return "", "src", 0
    src_n = estimate_tokens(src)

    pairs: list[tuple[str, str]] = []
    if candidates is None:
        idx = translation_index(bank_path)
        pairs = list(idx.get(_norm_lookup_key(src), []))
    elif isinstance(candidates, dict):
        # lang → str | list[str]
        for k, v in candidates.items():
            if isinstance(v, list):
                for t in v:
                    if t:
                        pairs.append((str(k), str(t)))
            elif v:
                pairs.append((str(k), str(v)))
    else:
        pairs = list(candidates)

    # None → no filter (all bank langs). Empty set → keep original only.
    allowed = allow_langs

    def _eligible(lang: str, cand: str) -> tuple[str, str, int, tuple] | None:
        if allowed is not None and lang not in allowed:
            return None
        cand_n = unicodedata.normalize("NFC", cand.strip())
        if not cand_n:
            return None
        n = estimate_tokens(cand_n)
        if prefer_low_ambiguity:
            key = score_translation_candidate(cand_n, src_tokens=src_n)
            if key is None:
                return None
            # utf8 for cheapest tie-break. Do *not* use char-len — CJK
            # fewer codepoints would beat equal-utf8 EN (ASAP≻尽快).
            # Do *not* put cand text in the key (lexicographic "Aide"<"Ayú"
            # would steal ties). Remaining ties → earlier pool (EN-first).
            full = (*key, _utf8_len(cand_n))
            return cand_n, lang, n, full
        if n >= src_n:
            return None
        full = (n, 0, n, _utf8_len(cand_n))
        return cand_n, lang, n, full

    # EN-first: collapse multiple EN paraphrases to one cheapest EN, then let
    # that single EN compete with cross-lang (token→utf8). Does not force EN
    # over a cheaper ZH/JA densifier.
    en_best: tuple[str, str, int, tuple] | None = None
    others: list[tuple[str, str, int, tuple]] = []
    for lang, cand in pairs:
        got = _eligible(lang, cand)
        if got is None:
            continue
        if lang == "en":
            if en_best is None or got[3] < en_best[3]:
                en_best = got
        else:
            others.append(got)

    # Compete collapsed EN vs cross-lang. Strict < so ties keep earlier
    # candidate (EN first → ASAP beats equal-token ZH densifier).
    pool: list[tuple[str, str, int, tuple]] = []
    if en_best is not None:
        pool.append(en_best)
    pool.extend(others)
    if not pool:
        return src, "src", src_n
    winner = pool[0]
    for got in pool[1:]:
        if got[3] < winner[3]:
            winner = got
    return winner[0], winner[1], winner[2]


def _google_target_code(lang: str) -> str:
    if lang == "zh":
        return "zh-CN"
    return lang


def _translate_one_deep(src: str, lang: str) -> tuple[str, str] | None:
    try:
        from deep_translator import GoogleTranslator  # type: ignore
    except Exception:
        return None
    google_code = _google_target_code(lang)
    try:
        translated = GoogleTranslator(source="auto", target=google_code).translate(src)
    except Exception:
        return None
    if translated and translated.strip() and translated.strip() != src:
        return (lang, translated.strip())
    return None


def _translate_one_argos(src: str, lang: str) -> tuple[str, str] | None:
    try:
        import argostranslate.translate  # type: ignore
    except Exception:
        return None
    try:
        translated = argostranslate.translate.translate(src, "en", lang)
    except Exception:
        try:
            translated = argostranslate.translate.translate(src, detect_lang(src), lang)
        except Exception:
            return None
    if translated and translated.strip() and translated.strip() != src:
        return (lang, translated.strip())
    return None


def live_translation_candidates(
    sentence: str,
    *,
    engine: str,
    target_langs: set[str] | None = None,
    translate_fn: Any | None = None,
    max_workers: int = 8,
) -> list[tuple[str, str]]:
    """Opt-in live MT candidates. Default/tests never call this (fixture engine).

    ``engine``:
      - ``fixture``: empty (bank-only path)
      - ``argos``: ``argostranslate`` if installed (offline packs; heavy optional)
      - ``deep``: ``deep_translator`` if installed (network at call time)

    Target langs are translated **concurrently** (ThreadPoolExecutor). Pass
    ``translate_fn(src, lang) -> str | None`` to inject a fake engine for tests
    (no network). Missing optional deps → empty list. Errors swallowed per-lang.
    """
    eng = (engine or "fixture").lower().strip()
    if eng in ("", "fixture", "bank", "none") and translate_fn is None:
        return []
    targets = target_langs if target_langs is not None else set(SCOPE_LANGS)
    # Prefer translating out of source lang when detectable; still try others
    src = sentence.strip()
    if not src:
        return []
    # Drop empty / nonsense targets
    targets = {t for t in targets if t}

    def _one(lang: str) -> tuple[str, str] | None:
        if translate_fn is not None:
            try:
                got = translate_fn(src, lang)
            except Exception:
                return None
            if got is None:
                return None
            text = str(got).strip()
            if not text or text == src:
                return None
            return (lang, text)
        if eng == "deep":
            return _translate_one_deep(src, lang)
        if eng == "argos":
            return _translate_one_argos(src, lang)
        return None

    if eng not in ("", "fixture", "bank", "none", "deep", "argos") and translate_fn is None:
        raise ValueError(f"unknown translate engine: {engine!r}; choose from {TRANSLATE_ENGINES}")

    out: list[tuple[str, str]] = []
    ordered = sorted(targets)
    workers = max(1, min(max_workers, len(ordered) or 1))
    if not ordered:
        return []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_one, lang): lang for lang in ordered}
        for fut in as_completed(futs):
            try:
                pair = fut.result()
            except Exception:
                continue
            if pair:
                out.append(pair)
    # Stable order by lang for determinism in tests
    out.sort(key=lambda p: p[0])
    return out


def minify_by_translation(
    text: str,
    *,
    bank_path: str | Path | None = None,
    allow_langs: set[str] | None = None,
    preserve_newlines: bool = False,
    translate_engine: str = "fixture",
    translate_fn: Any | None = None,
    prefer_low_ambiguity: bool = True,
) -> str:
    """Per-sentence: replace with a shorter bank (or live) translation when tokens drop.

    Segmentation matches ``tag_sentences``. Empty / paragraph markers unchanged.
    ``translate_engine='fixture'`` (default) uses only ``translations.json`` so
    pytest stays offline-deterministic. ``argos`` / ``deep`` fan out to target
    langs in parallel, then pick by shortness + low 揺らぎ. ``translate_fn`` injects
    a fake engine for offline tests.
    """
    tagged = tag_sentences(text, preserve_newlines=preserve_newlines)
    if not tagged:
        return ""
    eng = (translate_engine or "fixture").lower().strip()
    out_parts: list[str] = []
    for lang, sent in tagged:
        if lang == "¶" or sent == "¶":
            out_parts.append("¶")
            continue
        # Live engines: parallel multi-lang. Fixture: bank only (deterministic).
        use_live = eng in ("deep", "argos") or translate_fn is not None
        idx_pairs = translation_index(bank_path).get(_norm_lookup_key(sent), [])
        live: list[tuple[str, str]] = []
        if use_live:
            live = live_translation_candidates(
                sent,
                engine=eng if eng in ("deep", "argos") else "deep",
                target_langs=allow_langs if allow_langs is not None else set(SCOPE_LANGS),
                translate_fn=translate_fn,
            )
        # Merge bank + live; bank first. Empty merged → pick keeps original.
        merged: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for pair in list(idx_pairs) + list(live):
            if pair not in seen:
                merged.append(pair)
                seen.add(pair)
        chosen, _, _ = pick_shortest_translation(
            sent,
            candidates=merged,
            allow_langs=allow_langs,
            prefer_low_ambiguity=prefer_low_ambiguity,
        )
        out_parts.append(chosen)
    # Rejoin similar to expand
    flat: list[str] = []
    for i, s in enumerate(out_parts):
        if s == "¶":
            if preserve_newlines:
                flat.append("\n\n")
            continue
        if not flat:
            flat.append(s)
            continue
        prev = flat[-1]
        if prev.endswith("\n\n"):
            flat.append(s)
        elif re.search(r"[。？！]$", prev) or re.match(
            r"^[\u3040-\u30ff\u3400-\u9fff]", s
        ) or re.match(r"^[\"'\u201d\u2019)\]]+(?:\s|$)", s):
            # closing quote/bracket split off after a terminator (``?"`` -> ``?`` + ``"``):
            # re-attach without a space (a space would cost an extra o200k token)
            flat.append(s)
        else:
            flat.append(" " + s)
    return "".join(flat)



# --- final token pass (pipeline end; reduce estimate_tokens) ---
# ZH densifiers / DE compounds / ES/FR short tense — candidate classes only
# (複合名詞 etc. are labels for forms, not a noun-only policy).


@lru_cache(maxsize=4)
def load_zh_de_phrase_bank(path: str | None = None) -> dict[str, Any]:
    """Load final-token phrase bank (ZH/DE compounds, EN acronyms, densifiers)."""
    p = Path(path) if path is not None else DEFAULT_ZH_DE_PHRASE_BANK
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"zh/de phrase bank missing entries: {p}")
    return data


@lru_cache(maxsize=4)
def load_es_fr_tense_bank(path: str | None = None) -> dict[str, Any]:
    """Load curated short conjugations for tense token control (es/fr/pt/nl/el)."""
    p = Path(path) if path is not None else DEFAULT_ES_FR_TENSE_BANK
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"es/fr tense bank missing entries: {p}")
    return data


@lru_cache(maxsize=4)
def load_pt_el_latin_phrase_bank(path: str | None = None) -> dict[str, Any]:
    """Load sibling phrase bank: pt/el/it/living-la shorts (additive to zh_de_phrases)."""
    p = Path(path) if path is not None else DEFAULT_PT_EL_LATIN_PHRASE_BANK
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"pt/el/latin phrase bank missing entries: {p}")
    return data


@lru_cache(maxsize=4)
def load_pt_el_latin_tense_bank(path: str | None = None) -> dict[str, Any]:
    """Load sibling tense bank: pt/el gaps not already in es_fr_tense.json."""
    p = Path(path) if path is not None else DEFAULT_PT_EL_LATIN_TENSE_BANK
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"pt/el/latin tense bank missing entries: {p}")
    return data


def load_tense_matrix_bank(path: str | None = None) -> dict[str, Any]:
    """Load generated person × tense matrix bank (scripts/tense_matrix.py)."""
    p = Path(path) if path is not None else DEFAULT_TENSE_MATRIX_BANK
    if not p.exists():
        return {"entries": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"tense matrix bank missing entries: {p}")
    return data


def tense_matrix_pairs(path: str | Path | None = None) -> list[tuple[str, str, str]]:
    """Return pairs from the generated person × tense matrix bank (cached)."""
    langs = frozenset(FINAL_TENSE_MATRIX_LANGS)
    return list(_tense_matrix_pairs_cached(str(path) if path is not None else "", langs))


@functools.lru_cache(maxsize=8)
def _tense_matrix_pairs_cached(path: str, langs: frozenset[str]) -> tuple[tuple[str, str, str], ...]:
    data = load_tense_matrix_bank(path or None)
    return tuple(_bank_phrase_pairs(data, allow_langs=set(langs)))


@lru_cache(maxsize=4)
def load_en_wordlist(path: str | None = None) -> frozenset[str]:
    """Lowercase English words for the homograph guard (``#`` lines = header)."""
    p = Path(path) if path is not None else DEFAULT_EN_WORDLIST
    if not p.exists():
        return frozenset()
    return frozenset(
        w.strip()
        for w in p.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    )


_WORD_SPLIT_RE = re.compile(r"[^\w]+")


def en_homograph_tokens(form: str, *, keep_head: str = "") -> list[str]:
    """Tokens of a non-EN candidate spelled exactly like an English word.

    ``he visto`` → ``["he"]``, ``fora`` → ``["fora"]``, ``vou`` → ``[]``.
    ``keep_head`` (the matched EN subject, e.g. ``this`` / ``who``) is skipped
    when the candidate keeps it as its first word. Case-insensitive; accented
    tokens never match the ASCII list.
    """
    words = load_en_wordlist()
    toks = [w for w in _WORD_SPLIT_RE.split(form.lower()) if w]
    if keep_head and toks and toks[0] == keep_head.lower():
        toks = toks[1:]
    return [w for w in toks if w in words]


def _entry_candidate_forms(
    entry: dict[str, Any],
    *,
    allow_langs: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Collect (form, lang) from ``candidates`` and/or ``to`` for a bank entry.

    Schema (general token candidate bank):
      candidates: [{form|to, lang, class?}, ...]
      to / lang: preferred or sole form when candidates omitted.
    Lang filter applies per candidate; EN acronyms are allowed when
    ``en`` is in ``allow_langs`` so they can beat ZH densifiers via cheapest.
    """
    forms: list[tuple[str, str]] = []
    seen: set[str] = set()
    for c in entry.get("candidates") or []:
        if not isinstance(c, dict):
            continue
        form = str(c.get("form") or c.get("to") or "").strip()
        lang = str(c.get("lang") or entry.get("lang") or "und").strip() or "und"
        if not form:
            continue
        if allow_langs is not None and lang not in allow_langs:
            continue
        if form not in seen:
            forms.append((form, lang))
            seen.add(form)
    to = str(entry.get("to") or "").strip()
    lang = str(entry.get("lang") or "").strip() or "und"
    if to and to not in seen and (allow_langs is None or lang in allow_langs):
        forms.insert(0, (to, lang))
    return forms


_SUBJ_AUX_CONTRACTIONS: tuple[tuple[str, str], ...] = (
    ("I will", "I'll"), ("I would", "I'd"), ("I have", "I've"), ("I am", "I'm"),
    ("we will", "we'll"), ("we would", "we'd"), ("we have", "we've"), ("we are", "we're"),
    ("you will", "you'll"), ("you would", "you'd"), ("you have", "you've"), ("you are", "you're"),
    ("he will", "he'll"), ("she will", "she'll"), ("he is", "he's"), ("she is", "she's"),
    ("they will", "they'll"), ("they would", "they'd"), ("they have", "they've"), ("they are", "they're"),
)


# Typed ambiguous contractions: ``'s`` = is|has, ``'d`` = would|had. The full
# form is only twinned to the short form when the right context proves the type
# (``'s``/``'d`` + irregular past participle → has/had; ``'s`` + -ing → is;
# ``'d`` + bare verb / like / rather → would). Regular ``-ed`` after ``'s`` is
# ambiguous (it's finished = is|has) and stays EN, as do transitive irregular
# PPs (it's done / it's said = passive is); possessive ``noun's`` is never
# a subject here (only pronoun/relative heads below).
_S_SUBJECTS = ("he", "she", "it", "who")
_S_HAS_ONLY_PP = frozenset({"been", "gone", "had", "become"})
_D_SUBJECTS = ("I", "you", "he", "she", "it", "we", "they", "who")


def _contraction_type(aux: str, rest: str) -> bool:
    """True when ``rest`` (words after the aux) proves ``aux`` for its 's/'d."""
    first = rest.split(" ", 1)[0].lower().strip(".,!?;:")
    if not first:
        return False
    if aux in ("has", "had"):
        # Irregular PPs only for 's (regular -ed is is/has-ambiguous); 'd + -ed
        # is unambiguous (would + -ed is ungrammatical) so allow it for had.
        if aux == "has":
            # Transitive PPs after 's read as passive/adjectival is just as
            # often (it's done / it's seen / it's said) → only non-passivizable.
            return first in _S_HAS_ONLY_PP
        if first in _EN_IRREGULAR_PP and first not in _EN_BARE_VERBS:
            return True
        return aux == "had" and first.endswith("ed")
    if aux == "is":
        return first.endswith("ing")
    if aux == "would":
        return first in _EN_BARE_VERBS or first in ("like", "rather")
    return False


def _subject_aux_variants(src: str) -> list[str]:
    """``src`` plus its leading subject+aux full↔contracted twin (I will X ↔ I'll X).

    Ambiguous ``'s``/``'d`` twins are type-checked by right context
    (``_contraction_type``); unprovable cases keep only the full form.
    """
    out = [src]
    low = src.lower()
    for full, short in _SUBJ_AUX_CONTRACTIONS:
        if short.endswith(("'s", "'d")):
            continue
        for a, b in ((full, short), (short, full)):
            if low.startswith(a.lower() + " "):
                out.append(b + src[len(a):])
    parts = src.split(" ", 2)
    if len(parts) == 3:
        subj, aux, rest = parts
        sl, al = subj.lower(), aux.lower()
        typed = (
            (al in ("is", "has") and sl in _S_SUBJECTS and "'s")
            or (al in ("would", "had") and sl in {x.lower() for x in _D_SUBJECTS} and "'d")
        )
        if typed and _contraction_type(al, rest):
            out.append(f"{subj}{typed} {rest}")
    return out


# (source.lower(), replacement) pairs decided at build time with o200k_base.
_PRESCORED: set[tuple[str, str]] = set()


def collision_blocked(bank: str) -> frozenset[tuple[str, str]]:
    """(entry id, form) pairs of ``bank`` rejected by the cross-language collision
    guard (generated by scripts/tense_matrix.py into the matrix bank as
    ``collision_blocked``). Applied at conversion time by the bank pair loaders."""
    return _collision_blocked_cached(bank)


@functools.lru_cache(maxsize=8)
def _collision_blocked_cached(bank: str) -> frozenset[tuple[str, str]]:
    rows = load_tense_matrix_bank().get("collision_blocked") or []
    return frozenset((str(r["id"]), str(r["form"])) for r in rows if r.get("bank") == bank)


def _bank_phrase_pairs(
    data: dict[str, Any],
    *,
    allow_langs: set[str] | None = None,
    blocked: frozenset[tuple[str, str]] = frozenset(),
) -> list[tuple[str, str, str]]:
    """(source, replacement, lang) from a bank; longest source first.

    Entries may list multiple ``candidates``; ``_apply_phrase_pairs`` then picks
    via ``_cheapest_repl`` (token → utf8 → len), same metric as C registration.
    ``blocked`` (entry id, form) candidates are skipped (collision guard), so the
    next-cheapest candidate of the entry wins, else EN stays.
    """
    pairs: list[tuple[str, str, str]] = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        forms = _entry_candidate_forms(entry, allow_langs=allow_langs)
        eid = str(entry.get("id") or "")
        forms = [(f, lg) for f, lg in forms if (eid, f) not in blocked]
        if not forms:
            continue
        srcs: list[str] = []
        for src in entry.get("from") or []:
            for v in _subject_aux_variants(str(src).strip()):
                if v and v not in srcs:
                    srcs.append(v)
        # Build-time pre-scored entries (scripts/tense_matrix.py, real o200k_base):
        # the generator already proved the single winner beats EN's cheapest form,
        # so the stdlib estimate must not re-judge it (runtime never imports tiktoken).
        prescored = entry.get("scored_by") == "o200k_base"
        for s in srcs:
            src_n = estimate_tokens(s)
            for form, lang in forms:
                if prescored:
                    _PRESCORED.add((s.lower(), form))
                    pairs.append((s, form, lang))
                    continue
                # Only keep candidates that strictly cut tokens for this source
                # (losing densifiers stay in JSON for documentation / competition).
                if estimate_tokens(form) < src_n:
                    pairs.append((s, form, lang))
    pairs.sort(key=lambda t: (-len(t[0]), t[0].lower(), t[1]))
    return pairs


def zh_de_phrase_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return (source_phrase, replacement, lang) for final-token phrase bank."""
    data = load_zh_de_phrase_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_PHRASE_LANGS), blocked=collision_blocked("zh_de_phrases"))


def es_fr_tense_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return (source_phrase, replacement, lang) for short-tense densifier bank.

    Bank file keeps the historical ``es_fr_tense.json`` name; allowed langs are
    ``FINAL_TENSE_LANGS`` (es/fr/pt/nl/el). Classical Latin conjugations are not
    registered — prefer live modern Romance / surviving Latin-derived abbrevs (C).
    """
    data = load_es_fr_tense_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_TENSE_LANGS), blocked=collision_blocked("es_fr_tense"))


def pt_el_latin_phrase_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return pairs from sibling pt/el/it/living-la phrase bank."""
    data = load_pt_el_latin_phrase_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(
        data, allow_langs=set(FINAL_PT_EL_LATIN_PHRASE_LANGS), blocked=collision_blocked("pt_el_latin_phrases")
    )


def pt_el_latin_tense_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return pairs from sibling pt/el tense bank (new sources only)."""
    data = load_pt_el_latin_tense_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(
        data,
        allow_langs=set(FINAL_TENSE_LANGS) | set(FINAL_PT_EL_LATIN_PHRASE_LANGS),
        blocked=collision_blocked("pt_el_latin_tense"),
    )


def _merge_phrase_pair_banks(
    *banks: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Concatenate bank pair lists and re-sort longest-source-first."""
    pairs: list[tuple[str, str, str]] = []
    for bank in banks:
        pairs.extend(bank)
    pairs.sort(key=lambda t: (-len(t[0]), t[0].lower(), t[1]))
    return pairs


def _phrase_token_wins(src: str, dst: str) -> bool:
    """True iff replacement strictly reduces estimate_tokens."""
    return estimate_tokens(dst) < estimate_tokens(src)


def _utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def _cheapest_repl(src: str, cands: list[tuple[str, str]]) -> str | None:
    """Pick replacement with lowest estimate_tokens, then utf8 bytes, then len.

    ``cands`` is ``(replacement, lang)``. Returns None if nothing beats ``src``.
    """
    best: tuple[int, int, int, str, str] | None = None
    src_n = estimate_tokens(src)
    ok: list[tuple[str, str]] = []
    if len(cands) == 1 and (src.lower(), cands[0][0]) in _PRESCORED:
        return cands[0][0]
    for repl, _lang in cands:
        n = estimate_tokens(repl)
        if n >= src_n:
            continue
        ok.append((repl, _lang))
        key = (n, _utf8_len(repl), len(repl), repl, _lang)
        if best is None or key < best:
            best = key
    if best is None:
        return None
    return prefer_on_tie(
        (best[3], best[4]), ok, lambda r: (estimate_tokens(r), _utf8_len(r))
    )[0]


# Common irregular English past participles (regular ones match ``-ed``).
_EN_IRREGULAR_PP = frozenset(
    """been gone done seen taken found had thought said known given come become
    made got gotten left felt kept brought bought caught taught told sold held
    stood understood heard meant met paid put read run set sent spent built lost
    won sat slept spoken written driven ridden eaten fallen forgotten chosen
    broken woken frozen stolen shown grown thrown drawn flown worn torn begun
    drunk sung swum rung known hidden bitten beaten let cut hit hurt shut
    struck led fed fought sought""".split()
)
# Phrase-final have-auxiliaries: when followed by a past participle the row is
# an auxiliary use (pluperfect/perfect), not possession — never fire then.
_HAVE_AUX_TAIL_RE = re.compile(r"(?:\bhad|\bhave|\bhas|'d|'ve|'s)$", re.IGNORECASE)
_PP_ALT = (
    r"(?:(?:" + "|".join(sorted(_EN_IRREGULAR_PP)) + r")|[A-Za-z]+ed)(?![A-Za-z0-9'])"
)
_PP_LOOKAHEAD = rf"(?!\s+{_PP_ALT})"
_HAVE_PP_LOOKAHEAD = rf"(?!\s+have\s+{_PP_ALT})"
# Phrase-final modals (I must / I could / I'll …): the modal governs the next
# verb, so a modal-only row must not fire before a following word (I must go →
# not "debo go"; I could not go → not "pude not go"). Longer full-phrase rows
# (I'll go → vou, I would like → gostaria) match first; otherwise EN stays.
_MODAL_TAIL_RE = re.compile(
    r"(?:\b(?:must|can|could|should|would|will|may|might|shall|cannot|can't|won't|"
    r"wouldn't|couldn't|shouldn't|mustn't|mightn't|shan't)|'ll|'d)$",
    re.IGNORECASE,
)
# Latin letters incl. accented and combining marks (NFD) for word edges.
_LATIN_CH = "A-Za-z0-9\u00C0-\u024F\u1E00-\u1EFF\u0300-\u036F"
_NEXT_WORD_LOOKAHEAD = r"(?!\s+[A-Za-z])"
# Common English bare verbs. A have-ending possession row (I had → tive) must
# not fire before "to <verb>" (obligation: I had to go) nor before a bare verb
# (I had go); it fires only before a noun phrase / determiner / end / punct.
# Full obligation rows (I have to go → …) still win via cheapest selection.
_EN_BARE_VERBS = frozenset(
    """go do see eat come make take be have say get know think want like buy live
    work give find tell ask use try leave call keep let begin seem help talk turn
    start show hear play run move pay meet bring write sit stand lose read learn
    change lead understand watch follow stop speak spend grow open walk win offer
    remember love consider appear wait serve die send expect build stay fall cut
    reach kill remain need feel put look drink sleep drive fly sing swim""".split()
)
_HAVE_OBLIG_LOOKAHEAD = (
    r"(?!\s+to\b)(?!\s+(?:" + "|".join(sorted(_EN_BARE_VERBS)) + r")(?![A-Za-z0-9']))"
)


# Pro-drop (subject-dropping) rows are valid only at a clause start where the
# subject is the main subject of that clause: text start or after sentence
# punctuation / newline. Inside an embedded clause (I think that he…, I know he…,
# … because we …) or after any preceding word, dropping the subject loses the
# clause's person → EN stays. Subject-kept rows (this/these/who …) are unaffected.
_SUBJ_PRONOUNS = frozenset("i you he she it we they".split())
_CLAUSE_START_RE = re.compile(r"(?:^|[.!?;\n])[\s\"'“‘(\[]*$")


def _is_pro_drop(span: str, chosen: str) -> bool:
    head = span.split(" ", 1)[0]
    subj = re.split(r"['’]", head, maxsplit=1)[0].lower()
    if subj not in _SUBJ_PRONOUNS:
        return False
    return chosen.split(" ", 1)[0].lower() != head.lower()


# Parenthetical / discourse adverbs set off by commas (However, …, therefore, …)
# pass through unchanged; a sentence-initial "However, " still leaves the next
# word at the main-clause start. Commas are never removed or rewritten.
DISCOURSE_ADVERBS = frozenset(
    """however therefore moreover furthermore nevertheless nonetheless meanwhile
    consequently thus hence besides indeed instead otherwise still also anyway
    finally firstly secondly lastly actually basically honestly frankly
    unfortunately fortunately surprisingly naturally obviously clearly
    apparently admittedly incidentally additionally similarly likewise
    accordingly subsequently""".split()
)
_DISCOURSE_PREFIX_RE = re.compile(
    r"(?:(?:" + "|".join(sorted(DISCOURSE_ADVERBS)) + r"|of course|in fact|after all"
    r"|by the way|for example|for instance|in addition|on the other hand"
    r"|as a result|in other words)\s*,\s*)+$",
    re.IGNORECASE,
)


def _at_clause_start(text: str, start: int) -> bool:
    head = text[:start]
    if _CLAUSE_START_RE.search(head):
        return True
    m = _DISCOURSE_PREFIX_RE.search(head)
    return bool(m and _CLAUSE_START_RE.search(head[: m.start()]))


def _apply_phrase_pairs(
    text: str,
    pairs: list[tuple[str, str, str]],
    *,
    require_token_drop: bool = True,
    homograph_guard: bool = False,
) -> str:
    """Apply phrase pairs with longest-first match; cheapest wins on collisions.

    ``homograph_guard``: drop non-EN candidates with any token spelled like an
    English word (``he visto``, ``fora``, ``van``) before cheapest selection, so
    the next-cheapest unique form wins — or the EN span stays when none is left.
    """
    src = unicodedata.normalize("NFC", text or "")
    if not src.strip() or not pairs:
        return src
    # Group by lowercase source for collision handling
    by_src: dict[str, list[tuple[str, str]]] = {}
    order: list[str] = []
    for phrase, repl, lang in pairs:
        key = phrase.lower()
        if key not in by_src:
            by_src[key] = []
            order.append(phrase)  # preserve longest-first original casing sample
        by_src[key].append((repl, lang))

    out = src
    out_low = out.lower()
    for phrase in order:
        key = phrase.lower()
        # Cheap substring prefilter (case-insensitive) before any regex work.
        if key not in out_low:
            continue
        cands = by_src[key]
        if homograph_guard:
            head = phrase.split(" ", 1)[0]
            cands = [
                (r, lg) for r, lg in cands if lg == "en" or not en_homograph_tokens(r, keep_head=head)
            ]
            if not cands:
                continue
        # Latin / ASCII phrase → word-boundary, case-insensitive.
        # Generic going-to guard: phrases ending in "going" must not fire when
        # followed by " to …" (EN future/intention); use longer bank entries
        # like "I'm going to go" → iré/vou for those futures instead.
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9' -]*", phrase):
            going_guard = r"(?!\s+to\b)" if phrase.lower().endswith("going") else ""
            # Generic aux guard: "I had" (possession) must not fire on
            # "I had gone" — longer matrix rows or EN handle the full phrase.
            aux_guard = (
                _PP_LOOKAHEAD + _HAVE_OBLIG_LOOKAHEAD
                if _HAVE_AUX_TAIL_RE.search(phrase)
                else ""
            )
            # Modal/any row before "have <pp>" (I could have gone → not "pude have
            # gone"): the perfect auxiliary belongs to the following participle.
            aux_guard += _HAVE_PP_LOOKAHEAD
            if _MODAL_TAIL_RE.search(phrase):
                aux_guard += _NEXT_WORD_LOOKAHEAD
            pat = re.compile(
                rf"(?<![{_LATIN_CH}]){re.escape(phrase)}(?![{_LATIN_CH}]){going_guard}{aux_guard}",
                re.IGNORECASE,
            )

            def _sub(
                m: re.Match[str],
                *,
                _cands: list[tuple[str, str]] = cands,
                _phrase: str = phrase,
            ) -> str:
                span = m.group(0)
                chosen = _cheapest_repl(span if require_token_drop else _phrase, _cands)
                if chosen is None and not require_token_drop:
                    chosen = _cands[0][0]
                if chosen is None:
                    return span
                if _is_pro_drop(span, chosen) and not _at_clause_start(
                    m.string, m.start()
                ):
                    return span
                # Subject-kept rows (this/who …): keep the matched subject's casing.
                head = span.split(" ", 1)[0]
                if chosen.split(" ", 1)[0].lower() == head.lower() and " " in chosen:
                    chosen = head + chosen[len(head):]
                return chosen

            out = pat.sub(_sub, out)
            out_low = out.lower()
        else:
            if phrase in out:
                chosen = _cheapest_repl(phrase, cands)
                if chosen is not None:
                    out = out.replace(phrase, chosen)
                    out_low = out.lower()
    return out


def apply_zh_de_phrases(
    text: str,
    *,
    bank_path: str | Path | None = None,
    sibling_bank_path: str | Path | None = None,
    require_token_drop: bool = True,
) -> str:
    """Replace curated phrases with cheapest token candidates when tokens drop.

    Candidate classes: ZH densifiers, DE compounds (incl. adj+noun), EN acronyms
    (ASAP/FYI/…), plus additive sibling pt/el/it/living-la shorts
    (``pt_el_latin_phrases.json``). Same cheapest metric as C.
    """
    pairs = _merge_phrase_pair_banks(
        zh_de_phrase_pairs(bank_path),
        pt_el_latin_phrase_pairs(sibling_bank_path),
    )
    return _apply_phrase_pairs(
        text,
        pairs,
        require_token_drop=require_token_drop,
    )


# Relative pronoun → number/animacy-neutral ``que`` (es/fr/pt). Only in an
# unambiguous relative slot: <noun> who|which|that <word>. Bare ``that`` also
# needs a determiner before the noun (the man that …) so demonstrative /
# complementizer / determiner ``that`` (I think that he…, that book) stays EN.
_REL_PRON_RE = re.compile(r"(?<![A-Za-z0-9'])(who|which|that)(?=\s+[A-Za-z])", re.IGNORECASE)
_REL_DET = frozenset(
    "the a an this these those my your his her its our their every each some any no all many few several".split()
)
_REL_CLOSED = frozenset(
    """i you he she it we they me him us them this that these those who which what whom whose
    and or but so if as than then because though although when where while whether
    is are was were be been being am do does did have has had will would can could shall should
    may might must not no yes to of in on at by for with from about into over after before
    think thought know knew say said believe hope see saw feel felt mean meant guess sure such
    now just also only even very said tell told show showed ask asked realize realized
    the a an my your his her its our their""".split()
)
# Connectives never mark animacy/gender: single neutral form only (no quien/qui/
# lequel/il quale/cuyo).
_REL_SUBJ_DET = _REL_DET | frozenset(
    "i you he she it we they this that these those there both either neither".split()
)
REL_QUE_FORMS: tuple[tuple[str, str], ...] = (("que", "es"),)


# --- Explicit role classifier for ``that`` --------------------------------
# Deterministic, left/right-context only. Roles:
#   relative       NOUN + that + (subject-less) VERB       the book that is…
#                  DET NOUN + that + SUBJ + VERB            the book that I read
#   complementizer VERB/ADJ/fact-NOUN + that + SUBJ|DET …  I think that he…,
#                                                           the fact that…, proposition that all…
#   determiner     that + NOUN                              that book
#   demonstrative  that + VERB / that at clause end          that is…, I like that.
#   unknown        anything else → EN
# Per-role rules: relative → neutral ``que``; every other role → EN.
THAT_ROLES = ("relative", "complementizer", "determiner", "demonstrative", "unknown")
_COMP_VERBS = frozenset(
    """think thinks thought know knows knew known say says said believe believes believed
    hope hopes hoped feel feels felt mean means meant guess guessed realize realizes realized
    realise realised tell tells told show shows showed shown ask asked claim claims claimed
    suggest suggests suggested agree agrees agreed doubt doubted notice noticed hear heard
    see sees saw seen find finds found learn learned learnt understand understood fear feared
    ensure ensured assume assumed suppose supposed expect expected promise promised
    report reported state stated argue argued insist insisted admit admitted deny denied
    wish wished decide decided prove proved proven note noted dedicated conceived
    remember remembered forget forgot discover discovered recognize recognized confirm confirmed
    explain explained imagine imagined pretend pretended predict predicted""".split()
)
_COMP_ADJ = frozenset(
    """sure certain glad happy sad afraid aware clear true obvious possible likely
    unlikely sorry surprised confident convinced evident important necessary
    proud worried amazed lucky strange odd fine good bad""".split()
)
_FACT_NOUNS = frozenset(
    """fact idea belief hope notion claim proposition news truth possibility chance
    assumption feeling sense evidence proof thought view opinion statement rumor rumour
    reason sign suggestion conclusion promise argument point realization knowledge
    impression theory principle condition understanding certainty doubt fear""".split()
)
_EN_AUX_VERBS = frozenset(
    "is are was were be been being am do does did have has had will would can could "
    "shall should may might must 's 're 've 'll 'd".split()
)
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[^\sA-Za-z]")


def _is_word(t: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]+(?:['’][A-Za-z]+)?", t))


def _looks_verb(w: str) -> bool:
    lw = w.lower()
    return (
        lw in _EN_AUX_VERBS
        or lw in _EN_BARE_VERBS
        or lw in _COMP_VERBS
        or bool(re.fullmatch(r"[a-z]+ed", lw))
        or lw.split("'", 1)[0] in _EN_AUX_VERBS
    )


def classify_that_role(text: str, start: int, word: str = "that") -> str:
    """Return the grammatical role of ``that`` at ``text[start:]`` (see ``THAT_ROLES``)."""
    prev = _TOKEN_RE.findall(text[:start])
    nxt_m = re.match(r"\s*(\S+)", text[start + len(word):])
    nxt_raw = nxt_m.group(1) if nxt_m else ""
    nxt = re.match(r"[A-Za-z]+(?:['’][A-Za-z]+)?", nxt_raw)
    n1 = nxt.group(0).lower() if nxt else ""
    # "that." / "that," — the word itself is followed by punctuation.
    after_punct = not nxt or not nxt_raw[:1].isalpha()
    p1 = prev[-1].lower() if prev and _is_word(prev[-1]) else ""
    p2 = prev[-2].lower() if len(prev) >= 2 and _is_word(prev[-2]) else ""
    # that + end / punctuation → pronoun (I like that. / that, …)
    if not n1:
        return "demonstrative"
    # Left anchor decides complementizer first (verb / adj / fact-noun + that).
    if p1 and (p1 in _COMP_VERBS or p1 in _COMP_ADJ or p1 in _FACT_NOUNS or p1 == "so"):
        if p1 in _FACT_NOUNS and n1 not in _REL_SUBJ_DET and _looks_verb(n1):
            return "relative" if p2 in _REL_DET else "unknown"  # the idea that is…
        return "complementizer"
    subj_next = n1 in _REL_SUBJ_DET or "'" in n1 or "’" in n1
    # NOUN + that (left word is open-class, preceded by a determiner)
    noun_left = bool(p1) and p1 not in _REL_CLOSED and "'" not in p1
    if noun_left and p2 in _REL_DET:
        if not subj_next and _looks_verb(n1):
            return "relative"
        if n1 in _SUBJ_PRONOUNS or n1 in {"we", "they"}:
            return "relative"  # the book that I read (object relative)
        return "unknown"
    # Clause start / after a closed-class word: pronoun or determiner.
    if not p1 or p1 in _REL_CLOSED:
        if after_punct:
            return "demonstrative"
        if _looks_verb(n1) or n1 in {"was", "is"}:
            return "demonstrative"
        if n1 in _REL_CLOSED:
            return "unknown"
        return "determiner"
    # VERB + that + NOUN (I want that car): object determiner.
    if not after_punct and n1 not in _REL_CLOSED and not _looks_verb(n1):
        return "determiner"
    return "unknown"


def _rel_slot(text: str, start: int, word: str) -> bool:
    prev = re.findall(r"[A-Za-z']+|[^\sA-Za-z']", text[:start])
    if not prev or not re.fullmatch(r"[A-Za-z']+", prev[-1]):
        return False  # sentence start / after punctuation: interrogative or ambiguous
    w1 = prev[-1].lower()
    if w1 in _REL_CLOSED or "'" in w1:
        return False
    if word.lower() == "that":
        role = classify_that_role(text, start, word)
        if role != "relative":
            return False
        # Subject-relative only for que-rewrite parity with #20 (object relatives stay EN).
        nxt = re.match(r"\s+([A-Za-z']+)", text[start + len(word):])
        return bool(nxt) and nxt.group(1).lower() not in _REL_SUBJ_DET and "'" not in nxt.group(1)
    return True


def apply_relative_que(text: str) -> str:
    """who/which/that (relative slot only) → cheapest of EN vs ``que`` (token→utf8).

    Number is left to the following EN verb (is/was/has → sg, are/were/have → pl);
    matrix ``que …`` rows convert it, number-neutral verbs (went, will go) stay EN.
    """
    def _sub(m: re.Match[str]) -> str:
        w = m.group(1)
        if not _rel_slot(m.string, m.start(), w):
            return w
        best = w
        key = (estimate_tokens(w), len(w.encode()))
        for form, _lg in REL_QUE_FORMS:
            if en_homograph_tokens(form):
                continue
            k = (estimate_tokens(form), len(form.encode()))
            if k < key:
                best, key = form, k
        return best

    return _REL_PRON_RE.sub(_sub, text or "")


# Second person ``you`` → ``U`` (1 char). Same token count but utf8 3→1 bytes,
# so the cheapest rule (tokens → utf8) picks it whenever no bank row wins.
# Runs AFTER phrase/tense rows: a matrix row (du/tú/vosotros …) strictly drops
# tokens and so always beats ``U <EN chain>``; rows blocked by a guard (pro-drop
# off clause start, aux+pp, modal, have-to) leave ``you`` → it becomes ``U`` here.
# ``U`` is case- and number-neutral (subject/object, sg/pl): the following EN
# aux/verb keeps tense/number, so no person collapse. Excluded: your / yours /
# yourself (word boundary) and contractions you'd / you're / you've / you'll
# ('d/'s type detection keeps the EN contraction).
_YOU_RE = re.compile(
    r"(?<![^\W\u3040-\u30ff\u3400-\u9fff]|['’])you(?![^\W\u3040-\u30ff\u3400-\u9fff]|['’])", re.IGNORECASE
)
YOU_FORM = "U"


def apply_you_u(text: str) -> str:
    """``you`` → ``U`` when cheaper (token → utf8); your/yours/yourself/you'X stay."""
    src = unicodedata.normalize("NFC", text or "")
    if estimate_tokens(YOU_FORM) > estimate_tokens("you") or _utf8_len(YOU_FORM) >= _utf8_len("you"):
        return src
    return _YOU_RE.sub(YOU_FORM, src)


def apply_es_fr_tense(
    text: str,
    *,
    bank_path: str | Path | None = None,
    sibling_bank_path: str | Path | None = None,
    require_token_drop: bool = True,
) -> str:
    """Replace stacked EN auxiliaries with short live conjugations when tokens drop.

    High-frequency go/come/do/be/have/must/want/see/say/… across present/past/
    future/conditional. Candidates may be es/fr/pt/nl/el
    (``FINAL_TENSE_LANGS``); runtime picks cheapest (token→utf8→len). Progressive
    ``*going`` skips when followed by ``to`` (going-to future guard). Explicit
    ``going to <V>`` futures use longer bank sources. Additive sibling
    ``pt_el_latin_tense.json`` covers NEW sources only. Meaning-clear modern forms
    only — classical Latin conjugations are not registered.

    English-homograph guard: a candidate with any token spelled like an English
    word (``fixtures/en_wordlist.txt``; e.g. es ``he visto``, pt ``fora``, es
    ``van``) is skipped; the next-cheapest unique candidate wins, else EN stays.
    Progressive (be + -ing) maps only to progressive-preserving periphrases
    (estar/stare + gerund …) or stays EN — never to a simple tense.
    """
    pairs = _merge_phrase_pair_banks(
        es_fr_tense_pairs(bank_path),
        pt_el_latin_tense_pairs(sibling_bank_path),
        tense_matrix_pairs(),
    )
    return apply_you_u(
        _apply_phrase_pairs(
            apply_relative_que(text),
            pairs,
            require_token_drop=require_token_drop,
            homograph_guard=True,
        )
    )


def final_zh_de_token_pass(
    text: str,
    *,
    phrase_bank: str | Path | None = None,
    tense_bank: str | Path | None = None,
    translation_bank: str | Path | None = None,
    preserve_newlines: bool = False,
    translate_engine: str = "fixture",
    translate_fn: Any | None = None,
    prefer_low_ambiguity: bool = True,
    apply_phrases: bool = True,
    apply_tense: bool = True,
    apply_sentences: bool = True,
) -> str:
    """Final-stage token reduction (alias name kept for CLI ``--final-zh-de``).

    Prefer calling ``final_token_pass``. Order: (1) phrase candidate bank
    (ZH/DE compounds, EN acronyms, plus sibling pt/el/it/living-la via cheapest),
    (2) short conjugations (es_fr_tense + sibling pt/el gaps),
    (3) per-sentence minify restricted to ``FINAL_TOKEN_LANGS`` (zh|de).
    DensityZip runs this last as ``B-final-token`` / ``B-final-zh-de``.
    """
    out = unicodedata.normalize("NFC", text or "")
    if not out.strip():
        return out
    if apply_phrases:
        out = apply_zh_de_phrases(out, bank_path=phrase_bank)
    if apply_tense:
        out = apply_es_fr_tense(out, bank_path=tense_bank)
    if apply_sentences:
        out = minify_by_translation(
            out,
            bank_path=translation_bank,
            allow_langs=set(FINAL_TOKEN_LANGS),
            preserve_newlines=preserve_newlines,
            translate_engine=translate_engine,
            translate_fn=translate_fn,
            prefer_low_ambiguity=prefer_low_ambiguity,
        )
    return out


def final_token_pass(
    text: str,
    *,
    phrase_bank: str | Path | None = None,
    tense_bank: str | Path | None = None,
    translation_bank: str | Path | None = None,
    preserve_newlines: bool = False,
    translate_engine: str = "fixture",
    translate_fn: Any | None = None,
    prefer_low_ambiguity: bool = True,
    apply_phrases: bool = True,
    apply_tense: bool = True,
    apply_sentences: bool = True,
) -> str:
    """Final token pass — preferred name for ``final_zh_de_token_pass``."""
    return final_zh_de_token_pass(
        text,
        phrase_bank=phrase_bank,
        tense_bank=tense_bank,
        translation_bank=translation_bank,
        preserve_newlines=preserve_newlines,
        translate_engine=translate_engine,
        translate_fn=translate_fn,
        prefer_low_ambiguity=prefer_low_ambiguity,
        apply_phrases=apply_phrases,
        apply_tense=apply_tense,
        apply_sentences=apply_sentences,
    )


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
    p.add_argument(
        "--no-rle",
        action="store_true",
        help="emit full lang: tags every sentence (disable RLE mosaic)",
    )
    p.add_argument(
        "--stats",
        action="store_true",
        help="print sentence count / lang histogram JSON to stderr",
    )
    p.add_argument(
        "--preserve-newlines",
        action="store_true",
        help="keep blank-line paragraph breaks as mosaic ¶ tiles",
    )
    p.add_argument(
        "--prefer-ltr",
        action="store_true",
        help="bias Latin+CJK mixes (no kana) toward en rather than zh",
    )
    p.add_argument(
        "--translate-min",
        action="store_true",
        help="per sentence: adopt shorter bank translation when tokens drop (any in-scope lang)",
    )
    p.add_argument(
        "--translation-bank",
        default="",
        help="optional path to translation candidates JSON (default: fixtures/translations.json)",
    )
    p.add_argument(
        "--translate-engine",
        default="fixture",
        choices=TRANSLATE_ENGINES,
        help="fixture=bank only (default, CI-safe); argos/deep=parallel multi-lang MT then length+揺らぎ pick",
    )
    p.add_argument(
        "--allow-langs",
        default="",
        help="optional comma-separated lang filter for translate-min (default: all bank langs)",
    )
    p.add_argument(
        "--final-zh-de",
        action="store_true",
        help="final-stage ZH/DE token pass: phrase densifiers + sentence minify allow_langs=zh,de",
    )
    p.add_argument(
        "--zh-de-phrase-bank",
        default="",
        help="optional path to ZH/DE phrase densifier JSON (default: fixtures/zh_de_phrases.json)",
    )
    p.add_argument(
        "--es-fr-tense-bank",
        default="",
        help="optional path to ES/FR tense conjugation JSON (default: fixtures/es_fr_tense.json)",
    )
    args = p.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    langs = [x.strip() for x in args.langs.split(",") if x.strip()] or None
    pn = args.preserve_newlines
    pl = args.prefer_ltr

    if args.stats and args.mode != "expand":
        print(json.dumps(stats(text, langs, prefer_ltr=pl), ensure_ascii=False), file=sys.stderr)

    bank = args.translation_bank or None
    tm = args.translate_min
    te = args.translate_engine
    allow = {x.strip() for x in args.allow_langs.split(",") if x.strip()} or None
    phrase_bank = args.zh_de_phrase_bank or None
    tense_bank = args.es_fr_tense_bank or None
    if args.final_zh_de and args.mode in ("tag", "compress"):
        text = final_zh_de_token_pass(
            text,
            phrase_bank=phrase_bank,
            tense_bank=tense_bank,
            translation_bank=bank,
            preserve_newlines=pn,
            translate_engine=te,
        )
    elif tm and args.mode in ("tag", "compress"):
        text = minify_by_translation(
            text,
            bank_path=bank,
            preserve_newlines=pn,
            allow_langs=allow,
            translate_engine=te,
        )

    if args.mode == "tag":
        print(render(tag_sentences(text, langs, preserve_newlines=pn, prefer_ltr=pl)))
    elif args.mode == "compress":
        # translate_min already applied above when set; avoid double-apply
        print(
            compress(
                text,
                langs,
                rle=not args.no_rle,
                preserve_newlines=pn,
                prefer_ltr=pl,
                translate_min=False,
                translation_bank=bank,
                translate_engine=te,
            )
        )
    else:
        print(expand(text, preserve_newlines=pn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
