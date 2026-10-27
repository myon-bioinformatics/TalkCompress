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
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Map normalized source → list of (lang, candidate_text)."""
    data = load_translation_bank(str(path) if path is not None else None)
    idx: dict[str, list[tuple[str, str]]] = {}
    for entry in data.get("entries") or []:
        cands = entry.get("candidates") or {}
        pairs = [(str(lang), str(text)) for lang, text in cands.items() if text]
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
        pairs = [(str(k), str(v)) for k, v in candidates.items()]
    else:
        pairs = list(candidates)

    # None → no filter (all bank langs). Empty set → keep original only.
    allowed = allow_langs
    best_text, best_lang, best_n = src, "src", src_n
    best_key: tuple[int, int, int] | None = None
    for lang, cand in pairs:
        if allowed is not None and lang not in allowed:
            continue
        cand = unicodedata.normalize("NFC", cand.strip())
        if not cand:
            continue
        n = estimate_tokens(cand)
        if prefer_low_ambiguity:
            key = score_translation_candidate(cand, src_tokens=src_n)
            if key is None:
                continue
            if best_key is None or key < best_key:
                best_key = key
                best_text, best_lang, best_n = cand, lang, n
        else:
            if n < best_n:
                best_text, best_lang, best_n = cand, lang, n
    return best_text, best_lang, best_n


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
    if tm and args.mode in ("tag", "compress"):
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
