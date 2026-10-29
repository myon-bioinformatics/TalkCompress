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
)

_LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]")
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

FINAL_TENSE_LANGS: frozenset[str] = frozenset({"es", "fr", "pt", "nl", "el"})
# Person × tense matrix bank (scripts/tense_matrix.py) also allows live it.
FINAL_TENSE_MATRIX_LANGS: frozenset[str] = frozenset({"es", "fr", "pt", "nl", "el", "it"})
"""Tense densifier bank langs: live Romance + Dutch + Greek (classical Latin conjugations skipped)."""

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
_LATIN_WORD = re.compile(r"[A-Za-z0-9\u00C0-\u024F']+")
# Cyrillic / Arabic / Devanagari / Greek letter-runs
_OTHER_WORD = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u0370-\u03FF\u1F00-\u1FFF]+"
)


def estimate_tokens(text: str) -> int:
    """Rough multilingual token estimate for ranking translation candidates.

    Heuristic (stdlib-only, deterministic):
    - each CJK / kana / Hangul character ≈ 1 token
    - each Latin / digit word ≈ max(1, ceil(chars/4)) (GPT-ish subword)
    - other script letter-runs (Cyrillic, Arabic, Devanagari, Greek) ≈ same subword rule
    Punctuation and whitespace do not add tokens. Absolute counts are approximate;
    relative ranking across in-scope langs (Romance / Germanic / Greek / ja / zh) matters for B.
    """
    if not text or not text.strip():
        return 0
    s = unicodedata.normalize("NFC", text)
    n = len(_CJK_CHAR.findall(s))
    for w in _LATIN_WORD.findall(s):
        n += max(1, (len(w) + 3) // 4)
    for w in _OTHER_WORD.findall(s):
        n += max(1, (len(w) + 3) // 4)
    return n


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
        ):
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


def _subject_aux_variants(src: str) -> list[str]:
    """``src`` plus its leading subject+aux full↔contracted twin (I will X ↔ I'll X)."""
    out = [src]
    low = src.lower()
    for full, short in _SUBJ_AUX_CONTRACTIONS:
        for a, b in ((full, short), (short, full)):
            if low.startswith(a.lower() + " "):
                out.append(b + src[len(a):])
    return out


def _bank_phrase_pairs(data: dict[str, Any], *, allow_langs: set[str] | None = None) -> list[tuple[str, str, str]]:
    """(source, replacement, lang) from a bank; longest source first.

    Entries may list multiple ``candidates``; ``_apply_phrase_pairs`` then picks
    via ``_cheapest_repl`` (token → utf8 → len), same metric as C registration.
    """
    pairs: list[tuple[str, str, str]] = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        forms = _entry_candidate_forms(entry, allow_langs=allow_langs)
        if not forms:
            continue
        srcs: list[str] = []
        for src in entry.get("from") or []:
            for v in _subject_aux_variants(str(src).strip()):
                if v and v not in srcs:
                    srcs.append(v)
        for s in srcs:
            src_n = estimate_tokens(s)
            for form, lang in forms:
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
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_PHRASE_LANGS))


def es_fr_tense_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return (source_phrase, replacement, lang) for short-tense densifier bank.

    Bank file keeps the historical ``es_fr_tense.json`` name; allowed langs are
    ``FINAL_TENSE_LANGS`` (es/fr/pt/nl/el). Classical Latin conjugations are not
    registered — prefer live modern Romance / surviving Latin-derived abbrevs (C).
    """
    data = load_es_fr_tense_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_TENSE_LANGS))


def pt_el_latin_phrase_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return pairs from sibling pt/el/it/living-la phrase bank."""
    data = load_pt_el_latin_phrase_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_PT_EL_LATIN_PHRASE_LANGS))


def pt_el_latin_tense_pairs(
    path: str | Path | None = None,
) -> list[tuple[str, str, str]]:
    """Return pairs from sibling pt/el tense bank (new sources only)."""
    data = load_pt_el_latin_tense_bank(str(path) if path is not None else None)
    return _bank_phrase_pairs(data, allow_langs=set(FINAL_TENSE_LANGS) | set(FINAL_PT_EL_LATIN_PHRASE_LANGS))


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
    best: tuple[int, int, int, str] | None = None
    src_n = estimate_tokens(src)
    for repl, _lang in cands:
        n = estimate_tokens(repl)
        if n >= src_n:
            continue
        key = (n, _utf8_len(repl), len(repl), repl)
        if best is None or key < best:
            best = key
    return best[3] if best else None


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
            aux_guard = _PP_LOOKAHEAD if _HAVE_AUX_TAIL_RE.search(phrase) else ""
            # Modal/any row before "have <pp>" (I could have gone → not "pude have
            # gone"): the perfect auxiliary belongs to the following participle.
            aux_guard += _HAVE_PP_LOOKAHEAD
            pat = re.compile(
                rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9]){going_guard}{aux_guard}",
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
    return _apply_phrase_pairs(
        text,
        pairs,
        require_token_drop=require_token_drop,
        homograph_guard=True,
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
