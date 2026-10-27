#!/usr/bin/env python3
"""MorphoZip (E): intra-sentence multilingual / grammar-minimal compression (layer 4).

Prefer short low-ambiguity tokens that shrink prediction candidates
(e.g. ``I`` over 私は/僕は/俺は). Keep useful counters (匹/個). Compact
pronoun inventory (2-bit core: I / 君 / 彼 / they|them|y'all) plus closed
POS inventories (articles / conjunctions / adverbs / auxiliaries /
prepositions pack1 + prep2 / particles / compare). Polarity ``!``/``¬``
is a separate 1-bit flag (not inventory width). Avoid Chinese-only bias.

Shared lexeme policy (``shared.lex_policy``) usage:
- UNIQUE_READINGS long form only (``compact=False``) — anti-ambiguity
- ETYMON_ALIGN (information / info / 情報 → ℹ️)
- EN quantity phrases → short JA counters (experimental; needs digits already present)
- strip unquoted articles ``the`` / ``a`` / ``an`` (quoted forms keep the word)
- optional integer → hex rewrite (``hex_nums``)
- protected spans ``[[keep:...]]`` / `` `keep:...` `` (wrappers stripped)

Fillers, UNIQUE_COMPACT, EN contractions (``I'll``), and spelled-number
digitization are **C (ShorthandEdge)** by default. Optional ``strip=True`` /
``--strip`` / ``--aggressive-fillers`` / ``--spelled-nums`` remain for opt-in.
``--keep-articles`` disables article stripping.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.lex_policy import (  # noqa: E402
    apply_etymon_align,
    apply_spelled_numbers,
    apply_unique_readings,
    strip_fillers,
)

# --- Closed POS inventories (E grammar-min, bits-primary) ---------------------
# Shared pattern with pronouns: bits_per = ceil(log2(N)), prefer N<=4 → 2 bits.
# Token view is informational only (B TesseraTalk estimate_tokens).
# C owns fillers / I'll / ledger (under→下, above→上, moreover→also, …).

class ClosedInventory:
    """One closed POS family: core (+ optional extended) slots and aliases."""

    __slots__ = ("name", "canonical", "extended", "aliases", "surface_re", "note")

    def __init__(
        self,
        name: str,
        canonical: tuple[str, ...],
        extended: tuple[str, ...],
        aliases: dict[str, str],
        surface_re: re.Pattern[str],
        note: str = "",
    ) -> None:
        self.name = name
        self.canonical = canonical
        self.extended = extended
        self.aliases = aliases
        self.surface_re = surface_re
        self.note = note


def utf8_bits(s: str) -> int:
    """Secondary metric: UTF-8 payload bits (not the inventory budget gate)."""
    return len(s.encode("utf-8")) * 8


def _ceil_log2(n: int) -> int:
    if n <= 1:
        return 0
    return math.ceil(math.log2(n))


def _norm_surface(form: str) -> str:
    if not form:
        return ""
    key = form.lower() if form.isascii() else form
    return key.replace("\u2019", "'").replace("'", "'")


def _build_surface_re(surfaces: list[str]) -> re.Pattern[str]:
    """Longest-first alternation; ASCII wordish surfaces get \\b."""
    parts: list[str] = []
    for s in sorted(set(surfaces), key=len, reverse=True):
        if not s or s == "∅":
            continue
        if s.isascii() and re.match(r"^[\w']+$", s):
            parts.append(rf"\b{re.escape(s)}\b")
        else:
            parts.append(re.escape(s))
    if not parts:
        return re.compile(r"(?!)")  # never matches
    return re.compile("|".join(parts), re.I)


# --- pronoun -----------------------------------------------------------------
PRONOUN_CANONICAL: tuple[str, ...] = ("I", "君", "彼", "they")
PRONOUN_EXTENDED: tuple[str, ...] = ("I", "君", "彼", "they", "it")
PRONOUN_ALIAS_TO_CANONICAL: dict[str, str] = {
    "i": "I",
    "me": "I",
    "my": "I",
    "mine": "I",
    "君": "君",
    "君の": "君",
    "彼": "彼",
    "彼の": "彼",
    "她": "彼",
    "她の": "彼",
    "they": "they",
    "them": "they",
    "their": "they",
    "theirs": "they",
    "y'all": "they",
    "it": "it",
    "its": "it",
}
_PRONOUN_SURFACE_RE = re.compile(
    r"y'all|君の|彼の|她の|\btheirs\b|\btheir\b|\bthem\b|\bthey\b|\bmine\b|"
    r"君|彼|她|\bI\b|\bme\b|\bmy\b|\bits\b|\bit\b",
    re.I,
)

# --- article (冠詞): drop → ∅ ; N=1 → 0 bits ----------------------------------
ARTICLE_CANONICAL: tuple[str, ...] = ("∅",)
ARTICLE_EXTENDED: tuple[str, ...] = ("∅",)
ARTICLE_ALIAS_TO_CANONICAL: dict[str, str] = {
    "the": "∅",
    "a": "∅",
    "an": "∅",
}
_ARTICLE_SURFACE_RE = re.compile(r"\b(?:the|a|an)\b", re.I)

# --- conjunction (接続詞): high-freq logical; C owns moreover/nevertheless ----
CONJ_CANONICAL: tuple[str, ...] = ("&", "/", "bc", "∴")
CONJ_EXTENDED: tuple[str, ...] = ("&", "/", "bc", "∴", "∵", "+")
CONJ_ALIAS_TO_CANONICAL: dict[str, str] = {
    "&": "&",
    "and": "&",
    "および": "&",
    "並びに": "&",
    "かつ": "&",
    "/": "/",
    "or": "/",
    "または": "/",
    "若しくは": "/",
    "もしくは": "/",
    "bc": "bc",
    "because": "bc",
    "∴": "∴",
    "therefore": "∴",
    "∵": "∵",
    "whereas": "∵",
    "+": "+",
    "in addition": "+",
}
_CONJ_SURFACE_RE = re.compile(
    r"および|並びに|もしくは|若しくは|または|かつ|"
    r"\bbecause\b|\btherefore\b|\bwhereas\b|\bin addition\b|"
    r"\band\b|\bor\b|\bbc\b|[＆&/∴∵+]",
    re.I,
)

# --- adverb (副詞): discourse / degree ----------------------------------------
ADVERB_CANONICAL: tuple[str, ...] = ("tho", "~", "˅", "esp.")
ADVERB_EXTENDED: tuple[str, ...] = ("tho", "~", "˅", "esp.", "also", "□", "oft")
ADVERB_ALIAS_TO_CANONICAL: dict[str, str] = {
    "tho": "tho",
    "however": "tho",
    "~": "~",
    "approximately": "~",
    "˅": "˅",
    "very": "˅",
    "really": "˅",
    "extremely": "˅",
    "esp.": "esp.",
    "esp": "esp.",
    "especially": "esp.",
    "particularly": "esp.",
    "also": "also",
    "additionally": "also",
    "□": "□",
    "always": "□",
    "oft": "oft",
    "often": "oft",
}
_ADVERB_SURFACE_RE = re.compile(
    r"\bapproximately\b|\bespecially\b|\bparticularly\b|\badditionally\b|"
    r"\bhowever\b|\bextremely\b|\breally\b|\bvery\b|\balways\b|\boften\b|"
    r"\besp\.|\btho\b|\balso\b|\boft\b|[~˅□]",
    re.I,
)

# --- auxiliary (助動詞): modality; I'll stays C --------------------------------
AUX_CANONICAL: tuple[str, ...] = ("can", "will", "must", "may")
AUX_EXTENDED: tuple[str, ...] = ("can", "will", "must", "may")
AUX_ALIAS_TO_CANONICAL: dict[str, str] = {
    "can": "can",
    "could": "can",
    "できる": "can",
    "will": "will",
    "would": "will",
    "だろう": "will",
    "でしょう": "will",
    "must": "must",
    "should": "must",
    "しなければならない": "must",
    "しなくてはならない": "must",
    "しねばならない": "must",
    "なければならない": "must",
    "なくてはならない": "must",
    "ねばならない": "must",
    "may": "may",
    "might": "may",
    "かもしれない": "may",
}
_AUX_SURFACE_RE = re.compile(
    r"しなければならない|しなくてはならない|しねばならない|なければならない|なくてはならない|ねばならない|かもしれない|"
    r"できる|でしょう|だろう|"
    r"\bcould\b|\bwould\b|\bshould\b|\bmight\b|\bcan\b|\bwill\b|\bmust\b|\bmay\b",
    re.I,
)

# --- preposition (前置詞 pack1): skip C ledger under/above/below/beneath ------
# Pack1 core N=4 → 2bit. of/without/within/before/after live in prep2 (below).
PREP_CANONICAL: tuple[str, ...] = ("w/", "4", "fr", "@")
PREP_EXTENDED: tuple[str, ...] = ("w/", "4", "fr", "@", "to")
PREP_ALIAS_TO_CANONICAL: dict[str, str] = {
    "w/": "w/",
    "with": "w/",
    "4": "4",
    "for": "4",
    "fr": "fr",
    "from": "fr",
    "@": "@",
    "at": "@",
    "to": "to",
}
_PREP_SURFACE_RE = re.compile(
    r"\bwith\b|\bfrom\b|\bfor\b|\bto\b|\bat\b|w/|fr|\b4\b|@",
    re.I,
)

# --- prep2 (前置詞 pack2): of / without / within / before / after ------------
# Second closed pack so pack1 stays N=4→2bit. Flat prep2 N=5 → 3bit (documented).
# Preferred surfaces: of→de, without→无 (w/o alias), within→内, before→前, after→後.
# Bare 前/後 for EN before/after; do not fight C ledger pair 前後/内外.
PREP2_CANONICAL: tuple[str, ...] = ("de", "无", "内", "前", "後")
PREP2_EXTENDED: tuple[str, ...] = ("de", "无", "内", "前", "後")
PREP2_ALIAS_TO_CANONICAL: dict[str, str] = {
    "de": "de",
    "of": "de",
    "无": "无",
    "without": "无",
    "w/o": "无",
    "sin": "无",
    "内": "内",
    "within": "内",
    "前": "前",
    "before": "前",
    "後": "後",
    "后": "後",
    "after": "後",
}
_PREP2_SURFACE_RE = re.compile(
    r"\bwithout\b|\bwithin\b|\bbefore\b|\bafter\b|\bof\b|w/o|"
    r"无|内|前|后|後|\bde\b|\bsin\b",
    re.I,
)

# --- compare (比較境界): 以上/以下 → ≧/≦ (JA priority; EN clear aliases) -----
# N=2 → 1bit. Do NOT rewrite under/below/above alone (C ledger → 下/上).
COMPARE_CANONICAL: tuple[str, ...] = ("≧", "≦")
COMPARE_EXTENDED: tuple[str, ...] = ("≧", "≦")
COMPARE_ALIAS_TO_CANONICAL: dict[str, str] = {
    "≧": "≧",
    ">=": "≧",
    "以上": "≧",
    "at least": "≧",
    "or more": "≧",
    "and above": "≧",
    "more than": "≧",
    "más de": "≧",
    "mas de": "≧",
    "más que": "≧",
    "mas que": "≧",
    "al menos": "≧",
    "plus de": "≧",
    "plus que": "≧",
    "mehr als": "≧",
    "≦": "≦",
    "<=": "≦",
    "以下": "≦",
    "at most": "≦",
    "or less": "≦",
    "and below": "≦",
    "less than": "≦",
    "menos de": "≦",
    "menos que": "≦",
    "como máximo": "≦",
    "como maximo": "≦",
    "moins de": "≦",
    "moins que": "≦",
    "weniger als": "≦",
}
_COMPARE_SURFACE_RE = re.compile(
    r"以上|以下|"
    r"\bat least\b|\bat most\b|\bor more\b|\bor less\b|"
    r"\band above\b|\band below\b|\bmore than\b|\bless than\b|"
    r"\bm[aá]s de\b|\bm[aá]s que\b|\bmenos de\b|\bmenos que\b|"
    r"\bal menos\b|\bcomo m[aá]ximo\b|"
    r"\bplus de\b|\bplus que\b|\bmoins de\b|\bmoins que\b|"
    r"\bmehr als\b|\bweniger als\b|"
    r">=|<=|≧|≦",
    re.I,
)

# --- particle (助詞): JA case/modality → symbol / drop ---------------------------------
# Core N=4 → 2bit. Language-agnostic minimal surfaces (symbols OK).
# Conflicts (documented): と→& overlaps conj &; から→fr overlaps prep from;
# で→∈ (not @; @ is prep at). C ledger 前後/内外 pairs untouched (bare 前/後 are prep2).
# は/が topic vs subject collapsed to ∅ (recoverable); を→∅; ね/よ/さ→∅.
PARTICLE_CANONICAL: tuple[str, ...] = ("∅", "→", "∈", "〜")
PARTICLE_EXTENDED: tuple[str, ...] = ("∅", "→", "∈", "〜", "+", "&", "fr")
PARTICLE_ALIAS_TO_CANONICAL: dict[str, str] = {
    "∅": "∅",
    "は": "∅",
    "が": "∅",
    "を": "∅",
    "ね": "∅",
    "よ": "∅",
    "さ": "∅",
    "→": "→",
    "に": "→",
    "へ": "→",
    "∈": "∈",
    "で": "∈",
    "〜": "〜",
    "まで": "〜",
    "+": "+",
    "も": "+",
    "&": "&",
    "と": "&",
    "fr": "fr",
    "から": "fr",
}
_PARTICLE_SURFACE_RE = re.compile(
    r"までは|からは|には|では|とは|"
    r"まで|から|"
    r"[はねよさをがにへとでも]|"
    r"→|∈|〜|\+|\bfr\b|&",
)

# Polarity flag (! / ¬): extra 1 bit, separate from aux/adverb inventory width.
# Shared by auxiliary negation (!can) and adverb not/never.
POLARITY_BIT = 1
POLARITY_MARKERS: tuple[str, ...] = ("!", "¬")

CLOSED_INVENTORIES: dict[str, ClosedInventory] = {
    "pronoun": ClosedInventory(
        "pronoun",
        PRONOUN_CANONICAL,
        PRONOUN_EXTENDED,
        PRONOUN_ALIAS_TO_CANONICAL,
        _PRONOUN_SURFACE_RE,
        "2-bit core; 她=彼 surface; they/them/y'all same slot",
    ),
    "article": ClosedInventory(
        "article",
        ARTICLE_CANONICAL,
        ARTICLE_EXTENDED,
        ARTICLE_ALIAS_TO_CANONICAL,
        _ARTICLE_SURFACE_RE,
        "the/a/an → ∅ (drop); N=1 → 0 bits; quoted kept",
    ),
    "conjunction": ClosedInventory(
        "conjunction",
        CONJ_CANONICAL,
        CONJ_EXTENDED,
        CONJ_ALIAS_TO_CANONICAL,
        _CONJ_SURFACE_RE,
        "because→bc OK; cuz not ruled out but prefer math-symbol family (bc/∴); "
        "dotted/math typing may land later; C owns moreover→also / nevertheless→but",
    ),
    "adverb": ClosedInventory(
        "adverb",
        ADVERB_CANONICAL,
        ADVERB_EXTENDED,
        ADVERB_ALIAS_TO_CANONICAL,
        _ADVERB_SURFACE_RE,
        "discourse/degree; bits-primary; polarity !/¬ shared w/ aux (separate 1bit); ext □=always oft=often; ∀ kept for whatever",
    ),
    "auxiliary": ClosedInventory(
        "auxiliary",
        AUX_CANONICAL,
        AUX_EXTENDED,
        AUX_ALIAS_TO_CANONICAL,
        _AUX_SURFACE_RE,
        "could→can would→will should→must might→may; I'll is C; "
        "neg → !can/!will/!must/!may; don't/not → !; polarity flag = 1bit separate",
    ),
    "preposition": ClosedInventory(
        "preposition",
        PREP_CANONICAL,
        PREP_EXTENDED,
        PREP_ALIAS_TO_CANONICAL,
        _PREP_SURFACE_RE,
        "pack1 w/|4|fr|@ → 2bit; skip C under/above; in/on deferred; for→4 揺らぎ別評価",
    ),
    "prep2": ClosedInventory(
        "prep2",
        PREP2_CANONICAL,
        PREP2_EXTENDED,
        PREP2_ALIAS_TO_CANONICAL,
        _PREP2_SURFACE_RE,
        "pack2 de|无|内|前|後 → N=5→3bit; of→de without→无(w/o alias) within→内 before→前 after→後",
    ),
    "compare": ClosedInventory(
        "compare",
        COMPARE_CANONICAL,
        COMPARE_EXTENDED,
        COMPARE_ALIAS_TO_CANONICAL,
        _COMPARE_SURFACE_RE,
        "以上→≧ 以下→≦ (1bit); EN at least/or more/and above→≧; at most/or less/and below→≦; "
        "bare under/below/above stay for C",
    ),
    "particle": ClosedInventory(
        "particle",
        PARTICLE_CANONICAL,
        PARTICLE_EXTENDED,
        PARTICLE_ALIAS_TO_CANONICAL,
        _PARTICLE_SURFACE_RE,
        "core ∅|→|∈|〜 → 2bit; は/が/を/ねよさ→∅; に/へ→→; で→∈ (not @); まで→〜; "
        "ext +|&|fr (も/と/から); と overlaps conj &; から overlaps prep fr",
    ),
}


def closed_inventory_bits(name: str, *, extended: bool = False) -> int:
    """Flat bits per closed-inventory occurrence: ceil(log2(N))."""
    inv = CLOSED_INVENTORIES[name]
    slots = inv.extended if extended else inv.canonical
    return _ceil_log2(len(slots))


def canonicalize_closed(
    name: str, form: str, *, extended: bool = False
) -> str | None:
    """Map a surface form to a canonical slot for ``name``, or None."""
    inv = CLOSED_INVENTORIES[name]
    key = _norm_surface(form)
    if name == "pronoun" and key == "i":
        canon = "I"
    else:
        canon = inv.aliases.get(key) or inv.aliases.get(form)
    if canon is None:
        return None
    slots = inv.extended if extended else inv.canonical
    if canon not in slots:
        return None
    return canon


def closed_bit_cost(
    name: str, text: str, *, extended: bool = False
) -> dict[str, float | int | list[str]]:
    """Sum flat inventory bits for each in-inventory occurrence in ``text``."""
    inv = CLOSED_INVENTORIES[name]
    slots = inv.extended if extended else inv.canonical
    width = _ceil_log2(len(slots))
    found: list[str] = []
    for m in inv.surface_re.finditer(text):
        canon = canonicalize_closed(name, m.group(0), extended=extended)
        if canon is not None:
            found.append(canon)
    return {
        "name": name,
        "inventory": list(slots),
        "inventory_n": len(slots),
        "bits_per": width,
        "count": len(found),
        "total_bits": len(found) * width,
        "canonicals": found,
        "utf8_bits_text": utf8_bits(text),
        "note": inv.note,
    }


def list_closed_inventories() -> list[str]:
    return list(CLOSED_INVENTORIES.keys())


# --- pronoun wrappers (stable API) --------------------------------------------

def pronoun_inventory_bits(*, extended: bool = False) -> int:
    """Flat bits per pronoun occurrence: ceil(log2(N)), N = inventory size.

    Core (extended=False): N=4 → 2 bits. Extended (+it): N=5 → 3 bits.
    """
    return closed_inventory_bits("pronoun", extended=extended)


def canonicalize_pronoun(form: str, *, extended: bool = False) -> str | None:
    """Map a surface form to a canonical inventory slot, or None if outside inventory."""
    return canonicalize_closed("pronoun", form, extended=extended)


# Pronouns gate on bits (inventory ceil(log2 N)); token estimates for pronouns
# (B TesseraTalk estimate_tokens, e.g. y'all ~ 1 token) are informational only.
def pronoun_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    """Sum flat inventory bits for each pronoun occurrence in ``text``.

    Primary budget metric (not UTF-8 length). they / them / y'all each cost the
    same ``pronoun_inventory_bits()`` width.
    """
    raw = closed_bit_cost("pronoun", text, extended=extended)
    return {
        "inventory": raw["inventory"],
        "inventory_n": raw["inventory_n"],
        "bits_per_pronoun": raw["bits_per"],
        "count": raw["count"],
        "total_bits": raw["total_bits"],
        "canonicals": raw["canonicals"],
        "utf8_bits_text": raw["utf8_bits_text"],
    }


# Thin aliases for other POS (mirror pronouns).
def article_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("article", extended=extended)


def article_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("article", text, extended=extended)


def conjunction_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("conjunction", extended=extended)


def conjunction_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("conjunction", text, extended=extended)


def adverb_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("adverb", extended=extended)


def adverb_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("adverb", text, extended=extended)


def auxiliary_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("auxiliary", extended=extended)


def auxiliary_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("auxiliary", text, extended=extended)


def preposition_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("preposition", extended=extended)


def preposition_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("preposition", text, extended=extended)


def prep2_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("prep2", extended=extended)


def prep2_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("prep2", text, extended=extended)


def compare_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("compare", extended=extended)


def compare_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("compare", text, extended=extended)


def particle_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("particle", extended=extended)


def particle_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("particle", text, extended=extended)


def polarity_bit_cost(text: str) -> dict[str, float | int | list[str]]:
    """Count polarity markers ``!`` / ``¬``; each costs POLARITY_BIT (1), not inventory width.

    Shared by auxiliary negation (``!can``) and adverb not/never. Affirmation = absence of marker.
    """
    found: list[str] = []
    for ch in text:
        if ch in POLARITY_MARKERS:
            found.append(ch)
    return {
        "name": "polarity",
        "markers": list(POLARITY_MARKERS),
        "bits_per": POLARITY_BIT,
        "count": len(found),
        "total_bits": len(found) * POLARITY_BIT,
        "canonicals": found,
        "note": "1-bit polarity flag separate from aux/adverb inventory width; I'll stays C",
    }


# (pattern, replacement) — applied in order; more specific first.
_SUBS: list[tuple[re.Pattern[str], str]] = [
    # --- pronouns (multi-word / longer first). Contractions (I'll) belong to C.
    # 2pl → y'all (same bit slot as they/them)
    (re.compile(r"\by'all\b", re.I), "y'all"),
    (re.compile(r"\byou all\b", re.I), "y'all"),
    (re.compile(r"\byou guys\b", re.I), "y'all"),
    (re.compile(r"\byou folks\b", re.I), "y'all"),
    (re.compile(r"\byou lot\b", re.I), "y'all"),
    (re.compile(r"皆さん|みなさん|みんな|お前ら|あなたたち|君たち"), "y'all"),
    (re.compile(r"你们"), "y'all"),
    # Gender-pair phrases: keep both surfaces; do NOT collapse to they
    (re.compile(r"\bhe or she\b", re.I), "彼/她"),
    (re.compile(r"\bshe or he\b", re.I), "她/彼"),
    (re.compile(r"\bhim or her\b", re.I), "彼/她"),
    (re.compile(r"\bher or him\b", re.I), "她/彼"),
    (re.compile(r"\bhis or her\b", re.I), "彼の/她の"),
    (re.compile(r"\bher or his\b", re.I), "她の/彼の"),
    # 3pl before bare 彼/他 (彼ら / 他们)
    (re.compile(r"彼らを|かれらを"), "them"),
    (re.compile(r"彼らの|かれらの"), "their"),
    (re.compile(r"彼ら|かれら|あの人たち"), "they"),
    (re.compile(r"他们|她们|她們"), "they"),
    # 1pl before 我
    (re.compile(r"私たちを|わたしたちを|我々を|僕たちを"), "us"),
    (re.compile(r"私たちの|わたしたちの|我々の|僕たちの"), "our"),
    (re.compile(r"私たちは|私たちが|わたしたちは|我々は|我々が|僕たちは|私たち|わたしたち|我々|僕たち|おれたち"), "we"),
    (re.compile(r"我们"), "we"),
    # 1sg JA / ZH
    (re.compile(r"私は|僕は|俺は|拙者は|わたしは|あたしは"), "I"),
    (re.compile(r"私の|僕の|俺の|わたしの"), "my"),
    (re.compile(r"私を|僕を|俺を|わたしを"), "me"),
    (re.compile(r"我"), "I"),
    # 3sg F before 彼 (彼女 contains 彼); surface 她, bit slot 彼
    (re.compile(r"彼女の"), "她の"),
    (re.compile(r"彼女は|彼女が|彼女を|彼女"), "她"),
    (re.compile(r"\bshe\b", re.I), "她"),
    (re.compile(r"\bhers\b", re.I), "她の"),
    (re.compile(r"\bher\b", re.I), "她"),
    # 3sg M
    (re.compile(r"彼の"), "彼の"),
    (re.compile(r"彼は|彼が|彼を"), "彼"),
    (re.compile(r"\bhe\b", re.I), "彼"),
    (re.compile(r"\bhim\b", re.I), "彼"),
    (re.compile(r"\bhis\b", re.I), "彼の"),
    (re.compile(r"他"), "彼"),
    # 2sg → 君 (after 2pl). Skip discourse fillers "you know/see" (C-owned).
    (re.compile(r"あなたの|お前の|君の"), "君の"),
    (re.compile(r"あなたは|あなたが|あなたを|お前は|お前が|お前を|君は|君が|君を|あなた|お前"), "君"),
    (re.compile(r"你"), "君"),
    (re.compile(r"\byours\b", re.I), "君の"),
    (re.compile(r"\byour\b", re.I), "君の"),
    (re.compile(r"\byourself\b", re.I), "君"),
    (re.compile(r"\byou\b(?!\s+(?:know|see)\b)", re.I), "君"),
    # 3sg inanimate (extended inventory slot when counting bits w/ extended=True)
    (re.compile(r"それは|それが|それを|それの|それ"), "it"),
    (re.compile(r"它"), "it"),
    # they/them/their/we/us/our/I/me/my/it — already short; leave as-is
    # EN multi-word → compact symbols (not I'll-family contractions)
    # within before with (prefix); without→无 preferred (w/o remains alias in prep2)
    (re.compile(r"\bwithin\b", re.I), "内"),
    (re.compile(r"\bwithout\b", re.I), "无"),
    (re.compile(r"\bw/o\b", re.I), "无"),
    (re.compile(r"\bwith\b", re.I), "w/"),
    (re.compile(r"\band\b", re.I), "&"),
    (re.compile(r"\bor\b", re.I), "/"),
    (re.compile(r"\bbecause\b", re.I), "bc"),
    (re.compile(r"\btherefore\b", re.I), "∴"),
    (re.compile(r"\bhowever\b", re.I), "tho"),
    (re.compile(r"\bapproximately\b", re.I), "~"),
    # equal to / more|less than handled in _PHRASE_GRAMMAR (＝/≧/≦).
    # greater than stays > (strict); less than → ≦ via phrase grammar.
    (re.compile(r"\bgreater than\b", re.I), ">"),
    # --- adverbs (closed inventory): degree + polarity-adjacent frequency
    # always→□ (∀ kept for whatever); never→¬; often→oft; bare not→! (after may not etc.)
    (re.compile(r"\bextremely\b", re.I), "˅"),
    (re.compile(r"\breally\b", re.I), "˅"),
    (re.compile(r"\bvery\b", re.I), "˅"),
    (re.compile(r"\bparticularly\b", re.I), "esp."),
    (re.compile(r"\balways\b", re.I), "□"),
    (re.compile(r"\bnever\b", re.I), "¬"),
    (re.compile(r"\boften\b", re.I), "oft"),
    # --- auxiliaries (closed inventory); I'll stays C — do not contract I will
    # Negation / affirmation: polarity ``!`` is +1 bit flag (see polarity_bit_cost).
    # Longer neg forms before positives. should→must slot ⇒ shouldn't→!must.
    (re.compile(r"\bcannot\b", re.I), "!can"),
    (re.compile(r"\bcan'?t\b", re.I), "!can"),
    (re.compile(r"\bcouldn'?t\b", re.I), "!can"),
    (re.compile(r"\bwon'?t\b", re.I), "!will"),
    (re.compile(r"\bwouldn'?t\b", re.I), "!will"),
    (re.compile(r"\bshould not\b", re.I), "!must"),
    (re.compile(r"\bshouldn'?t\b", re.I), "!must"),
    (re.compile(r"\bmust not\b", re.I), "!must"),
    (re.compile(r"\bmustn'?t\b", re.I), "!must"),
    (re.compile(r"\bmay not\b", re.I), "!may"),
    (re.compile(r"\bmight not\b", re.I), "!may"),
    (re.compile(r"\bdo not\b", re.I), "!"),
    (re.compile(r"\bdoes not\b", re.I), "!"),
    (re.compile(r"\bdid not\b", re.I), "!"),
    (re.compile(r"\bdon'?t\b", re.I), "!"),
    (re.compile(r"\bdoesn'?t\b", re.I), "!"),
    (re.compile(r"\bdidn'?t\b", re.I), "!"),
    (re.compile(r"できない|出来ない"), "!can"),
    (re.compile(r"ではない|じゃない|じゃありません|ではありません"), "!"),
    (re.compile(r"しなければならない|しなくてはならない|しねばならない|なければならない|なくてはならない|ねばならない"), "must"),
    (re.compile(r"かもしれない"), "may"),
    (re.compile(r"することができ(?:る|ます)"), "can"),
    (re.compile(r"でしょう|だろう"), "will"),
    (re.compile(r"\bcould\b", re.I), "can"),
    (re.compile(r"\bwould\b", re.I), "will"),
    (re.compile(r"\bshould\b", re.I), "must"),
    (re.compile(r"\bmight\b", re.I), "may"),
    # Bare not (after may not / do not phrases above)
    (re.compile(r"\bnot\b", re.I), "!"),
    # --- particles (助詞): after pronouns/aux JA; C 前後/内外 untouched
    # Compounds before singles. Avoid で in できる/です/である/でも…
    (re.compile(r"からは"), "fr"),
    (re.compile(r"までは"), "〜"),
    (re.compile(r"には"), "→"),
    (re.compile(r"では(?!ない)"), "∈"),
    (re.compile(r"とは"), "&"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])まで"), "〜"),
    # から: particle-from → fr (causal から ambiguous; same surface as prep intentionally)
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])から"), "fr"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])(?:に|へ)"), "→"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])で(?!き|す|あっ|しょ|した|も|ござ)"), "∈"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])と(?!し|ころ|り|りあえず)"), "&"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])も"), "+"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])を"), ""),
    # は/が: drop after CJK; skip は in はい/はあ discourse; が in known starts rare
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])は(?!い|あ|ず)"), ""),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])が(?!る|ん|っ|ち|く|くせい)"), ""),
    # sentence-final modality particles
    (re.compile(r"[ねよさ]+(?=[。．.!！？?]|$)"), ""),
    # --- prepositions pack1; C owns under/above/below/beneath — skip
    (re.compile(r"\bfrom\b", re.I), "fr"),
    # NOTE(for→4): 表層 4 は数字の four と揺らぎうる。ビット在庫(2bit)とは別に評価し、将来 for（原形）等へ戻る可能性あり（現状は 4 のまま）。
    (re.compile(r"\bfor\b", re.I), "4"),
    (re.compile(r"\bat\b", re.I), "@"),
    # --- prep2: of→de / before→前 / after→後 (within/without already above)
    (re.compile(r"\bbefore\b", re.I), "前"),
    (re.compile(r"\bafter\b", re.I), "後"),
    (re.compile(r"\bof\b", re.I), "de"),
    # --- compare: 以上/以下 → ≧/≦ (JA priority). EN multi-word in _PHRASE_GRAMMAR.
    # Do not rewrite bare under/below/above (C ledger).
    (re.compile(r"以上"), "≧"),
    (re.compile(r"以下"), "≦"),
    (re.compile(r">="), "≧"),
    (re.compile(r"<="), "≦"),
    # whatever-compounds → compact signals
    (re.compile(r"\bwhatever\b", re.I), "∀"),
    (re.compile(r"\bwhoever\b", re.I), "∀who"),
    (re.compile(r"\bwhichever\b", re.I), "∀which"),
    (re.compile(r"\bwherever\b", re.I), "∀loc"),
    (re.compile(r"\bwhenever\b", re.I), "∀when"),
    (re.compile(r"\bnonetheless\b", re.I), "tho∴"),
    (re.compile(r"\bhereinafter referred to as\b", re.I), "∴="),
    (re.compile(r"\bhereinafter\b", re.I), "∴↓"),
    (re.compile(r"\bhereafter\b", re.I), "∴→"),
    (re.compile(r"\bherein\b", re.I), "∈"),
    (re.compile(r"\bthereof\b", re.I), "∴of"),
    (re.compile(r"\btherein\b", re.I), "∈there"),
    (re.compile(r"\bwhereas\b", re.I), "∵"),
    # JA polite endings → low-ambiguity
    (re.compile(r"です。|ます。|でした。|ました。"), "。"),
    (re.compile(r"ですね|ますね"), "ね"),
    (re.compile(r"でしょうか"), "?"),
    (re.compile(r"および|並びに|かつ"), "&"),
    (re.compile(r"または|若しくは|もしくは"), "/"),
    (re.compile(r"について"), "re:"),
    (re.compile(r"という"), "="),
]

# EN quantity phrases → JA counters (unambiguous layer-4 experiments).
# Order: more specific animal/people phrases before generic pieces.
_COUNTER_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d+)\s+(?:animals?|cats?|dogs?|birds?|fish|pets?)\b", re.I), r"\1匹"),
    (re.compile(r"\b(\d+)\s+(?:people|persons?|humans?|users?|members?)\b", re.I), r"\1人"),
    (re.compile(r"\b(\d+)\s+(?:times|occasions?)\b", re.I), r"\1回"),
    (re.compile(r"\b(\d+)\s+(?:pieces?|items?|things?|objects?)\b", re.I), r"\1個"),
    (re.compile(r"\b(\d+)\s+(?:days?)\b", re.I), r"\1日"),
    (re.compile(r"\b(\d+)\s+(?:hours?)\b", re.I), r"\1時間"),
    (re.compile(r"\b(\d+)\s+(?:minutes?|mins?)\b", re.I), r"\1分"),
    (re.compile(r"\b(\d+)\s+(?:seconds?|secs?)\b", re.I), r"\1秒"),
    (re.compile(r"\b(\d+)\s+(?:books?|volumes?)\b", re.I), r"\1冊"),
    (re.compile(r"\b(\d+)\s+(?:sheets?|pages?|papers?)\b", re.I), r"\1枚"),
    (re.compile(r"\b(\d+)\s+(?:cars?|vehicles?|trucks?|buses|taxis?)\b", re.I), r"\1台"),
    (re.compile(r"\b(\d+)\s+(?:machines?|devices?|units?)\b", re.I), r"\1機"),
    (re.compile(r"\b(\d+)\s+(?:buildings?|houses?|homes?)\b", re.I), r"\1棟"),
    (re.compile(r"\b(\d+)\s+(?:floors?|storeys?|stories)\b", re.I), r"\1階"),
    (re.compile(r"\b(\d+)\s+(?:cups?|glasses|bowls?)\b", re.I), r"\1杯"),
    (re.compile(r"\b(\d+)\s+(?:pairs?|sets?)\b", re.I), r"\1組"),
    (re.compile(r"\b(\d+)\s+(?:companies?|firms?|corporations?)\b", re.I), r"\1社"),
    (re.compile(r"\b(\d+)\s+(?:letters?|emails?|messages?)\b", re.I), r"\1通"),
]

# Multi-word grammar-min applied *before* etymon so "for example" → e.g.
# is not eaten by example→ex.
_PHRASE_GRAMMAR: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bthat is to say\b", re.I), "i.e."),
    (re.compile(r"\bfor example\b", re.I), "e.g."),
    (re.compile(r"\bfor instance\b", re.I), "e.g."),
    (re.compile(r"\bin particular\b", re.I), "esp."),
    (re.compile(r"\bin addition\b", re.I), "+"),
    (re.compile(r"\binstead of\b", re.I), "vs"),
    (re.compile(r"\badditionally\b", re.I), "also"),
    (re.compile(r"\bespecially\b", re.I), "esp."),
    (re.compile(r"\bthat is\b", re.I), "i.e."),
    (re.compile(r"\bversus\b", re.I), "vs"),
    # compare / equality — language-agnostic → ≧/≦/= /≒ (BEFORE and/or/at/_SUBS)
    (re.compile(r"\bapproximately equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\babout equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\broughly equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\bequal to\b", re.I), "="),
    (re.compile(r"\bat least\b", re.I), "≧"),
    (re.compile(r"\bat most\b", re.I), "≦"),
    (re.compile(r"\bor more\b", re.I), "≧"),
    (re.compile(r"\bor less\b", re.I), "≦"),
    (re.compile(r"\band above\b", re.I), "≧"),
    (re.compile(r"\band below\b", re.I), "≦"),
    (re.compile(r"\bmore than\b", re.I), "≧"),
    (re.compile(r"\bless than\b", re.I), "≦"),
    # ES
    (re.compile(r"\bm[aá]s de\b", re.I), "≧"),
    (re.compile(r"\bm[aá]s que\b", re.I), "≧"),
    (re.compile(r"\bmenos de\b", re.I), "≦"),
    (re.compile(r"\bmenos que\b", re.I), "≦"),
    (re.compile(r"\bal menos\b", re.I), "≧"),
    (re.compile(r"\bcomo m[aá]ximo\b", re.I), "≦"),
    # FR
    (re.compile(r"\bplus de\b", re.I), "≧"),
    (re.compile(r"\bplus que\b", re.I), "≧"),
    (re.compile(r"\bmoins de\b", re.I), "≦"),
    (re.compile(r"\bmoins que\b", re.I), "≦"),
    # DE
    (re.compile(r"\bmehr als\b", re.I), "≧"),
    (re.compile(r"\bweniger als\b", re.I), "≦"),
]


def apply_phrase_grammar(text: str) -> str:
    out = text
    for pat, repl in _PHRASE_GRAMMAR:
        out = pat.sub(repl, out)
    return out


_DIGIT_FW = re.compile(r"[０-９]")
_INT_RE = re.compile(r"\b(\d+)\b")




# Unquoted EN articles. Quoted ``"the"`` / ``'the'`` keep the inner word (quotes dropped).
# Straight quotes: "the" / 'the'. Smart quotes: “the” / ‘the’.
_QUOTED_ARTICLE = re.compile(
    r"""(['"])(the|a|an)\1"""
    r"""|[\u201c\u2018](the|a|an)[\u201d\u2019]""",
    re.I,
)
_ARTICLE_WORD = re.compile(r"\b(?:the|a|an)\b", re.I)
_ART_PLACEHOLDER = "⟦ART{0}⟧"


def strip_articles(text: str) -> str:
    """Drop unquoted ``the`` / ``a`` / ``an``; quoted forms keep the inner word only."""
    restores: list[str] = []

    def _mask(m: re.Match[str]) -> str:
        inner = m.group(2) or m.group(3)
        restores.append(inner)
        return _ART_PLACEHOLDER.format(len(restores) - 1)

    out = _QUOTED_ARTICLE.sub(_mask, text)
    out = _ARTICLE_WORD.sub("", out)
    for i, inner in enumerate(restores):
        out = out.replace(_ART_PLACEHOLDER.format(i), inner)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return out


def apply_counters(text: str) -> str:
    """Map verbose EN quantity phrases toward short JA counters where unambiguous."""
    out = text
    for pat, repl in _COUNTER_SUBS:
        out = pat.sub(repl, out)
    return out


def apply_hex_nums(text: str, *, prefix: bool = True) -> str:
    """Rewrite decimal integers to lowercase hex.

    With ``prefix=True`` (default when enabled): ``42`` → ``0x2a``.
    With ``prefix=False``: bare hex digits style ``2a`` (documented; easy to
    confuse with words — prefer prefix).
    """
    def _repl(m: re.Match[str]) -> str:
        n = int(m.group(1))
        h = format(n, "x")
        return f"0x{h}" if prefix else h

    return _INT_RE.sub(_repl, text)



# Protected spans: [[keep:...]] wrappers are stripped; inner text is preserved
# verbatim through compress. Optional --protect-regex patterns similarly mask
# matched text (full match restored unchanged).
_KEEP_SPAN = re.compile(r"\[\[keep:(.*?)\]\]", re.DOTALL)
_KEEP_BT = re.compile(r"`keep:(.+?)`", re.DOTALL)
_PROTECT_PLACEHOLDER = "⟦KEEP{0}⟧"


def extract_protected(
    text: str,
    protect_regexes: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Mask protected spans; return (masked_text, list_of_inner_strings).

    Recognized forms (in order):
    - ``[[keep:...]]`` — wrappers stripped, inner preserved
    - `` `keep:...` `` — backtick form, wrappers stripped
    - each ``protect_regex`` — full match preserved as-is
    """
    restores: list[str] = []

    def _mask_keep(m: re.Match[str]) -> str:
        restores.append(m.group(1))
        return _PROTECT_PLACEHOLDER.format(len(restores) - 1)

    out = _KEEP_SPAN.sub(_mask_keep, text)
    out = _KEEP_BT.sub(_mask_keep, out)
    for pat in protect_regexes or []:
        cre = re.compile(pat)

        def _mask_full(m: re.Match[str], _cre=cre) -> str:
            restores.append(m.group(0))
            return _PROTECT_PLACEHOLDER.format(len(restores) - 1)

        out = cre.sub(_mask_full, out)
    return out, restores


def restore_protected(text: str, restores: list[str]) -> str:
    """Put protected inners back (placeholders → original text)."""
    out = text
    for i, inner in enumerate(restores):
        out = out.replace(_PROTECT_PLACEHOLDER.format(i), inner)
    return out


def compress(
    text: str,
    *,
    strip: bool = False,
    unique: bool = True,
    etymon: bool = True,
    aggressive_fillers: bool = False,
    counters: bool = True,
    spelled_nums: bool = False,
    keep_articles: bool = False,
    hex_nums: bool = False,
    hex_prefix: bool = True,
    protect_regexes: list[str] | None = None,
) -> str:
    """Compress text. ``[[keep:...]]`` / `` `keep:...` `` spans and optional
    ``protect_regexes`` are left unchanged (wrappers stripped for keep-forms).

    Default: no filler strip, no UNIQUE_COMPACT, no I'll, no spelled→digit
    (those belong to C). ``strip=True`` / ``aggressive_fillers=True`` /
    ``spelled_nums=True`` opt in. Unquoted articles ``the``/``a``/``an`` are
    stripped unless ``keep_articles``. Quoted articles keep the inner word
    (quotes dropped). Counters map digit+noun phrases (``3 animals``→``3匹``);
    digitization of spelled words is C's job (or ``spelled_nums=True``).
    """
    out, restores = extract_protected(text, protect_regexes)
    # aggressive_fillers implies strip
    do_strip = strip or aggressive_fillers
    if do_strip:
        out = strip_fillers(out, aggressive=aggressive_fillers)
    if unique:
        out = apply_unique_readings(out, compact=False)
    out = apply_phrase_grammar(out)
    if etymon:
        out = apply_etymon_align(out)
    if spelled_nums:
        out = apply_spelled_numbers(out)
    if counters:
        out = apply_counters(out)
    if not keep_articles:
        out = strip_articles(out)
    for pat, repl in _SUBS:
        out = pat.sub(repl, out)
    out = _DIGIT_FW.sub(lambda m: chr(ord(m.group(0)) - 0xFEE0), out)
    if hex_nums:
        out = apply_hex_nums(out, prefix=hex_prefix)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" *\n *", "\n", out)
    out = out.strip()
    return restore_protected(out, restores)



# Best-effort inverse maps (lossy / unambiguous subset only).
_EXPAND_COUNTERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(\d+)匹"), r"\1 animals"),
    (re.compile(r"(\d+)人"), r"\1 people"),
    (re.compile(r"(\d+)回"), r"\1 times"),
    (re.compile(r"(\d+)個"), r"\1 pieces"),
    (re.compile(r"(\d+)日"), r"\1 days"),
    (re.compile(r"(\d+)時間"), r"\1 hours"),
    (re.compile(r"(\d+)分"), r"\1 minutes"),
    (re.compile(r"(\d+)秒"), r"\1 seconds"),
    (re.compile(r"(\d+)冊"), r"\1 books"),
    (re.compile(r"(\d+)枚"), r"\1 sheets"),
    (re.compile(r"(\d+)台"), r"\1 vehicles"),
    (re.compile(r"(\d+)機"), r"\1 machines"),
    (re.compile(r"(\d+)棟"), r"\1 buildings"),
    (re.compile(r"(\d+)階"), r"\1 floors"),
    (re.compile(r"(\d+)杯"), r"\1 cups"),
    (re.compile(r"(\d+)組"), r"\1 pairs"),
    (re.compile(r"(\d+)社"), r"\1 companies"),
    (re.compile(r"(\d+)通"), r"\1 messages"),
]

# Unambiguous short → longer (subset of _SUBS / UNIQUE_COMPACT). Documented lossy.
_EXPAND_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bw/o\b", re.I), "without"),
    # CJK prep2 shorts: only expand when space/punct bounded (avoid eating JA 前後…)
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])无(?![\w\u3040-\u30ff\u3400-\u9fff])"), "without"),
    (re.compile(r"\bde\b", re.I), "of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])内(?![\w\u3040-\u30ff\u3400-\u9fff])"), "within"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])前(?![\w\u3040-\u30ff\u3400-\u9fff])"), "before"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])(?:后|後)(?![\w\u3040-\u30ff\u3400-\u9fff])"), "after"),
    (re.compile(r"!can\b"), "cannot"),
    (re.compile(r"!will\b"), "will not"),
    (re.compile(r"!must\b"), "must not"),
    (re.compile(r"!may\b"), "may not"),
    (re.compile(r"□"), "always"),
    (re.compile(r"¬"), "never"),
    (re.compile(r"\boft\b", re.I), "often"),
    (re.compile(r"≧"), "以上"),
    (re.compile(r"≦"), "以下"),
    (re.compile(r"≒"), "approximately equal"),
    (re.compile(r"\bw/\b", re.I), "with"),
    (re.compile(r"\bu r\b", re.I), "you are"),
    (re.compile(r"\bbc\b", re.I), "because"),
    (re.compile(r"\btho∴\b"), "nonetheless"),
    (re.compile(r"\btho\b", re.I), "however"),
    (re.compile(r"∴↓"), "hereinafter"),
    (re.compile(r"∴→"), "hereafter"),
    (re.compile(r"∴="), "hereinafter referred to as"),
    (re.compile(r"∴of"), "thereof"),
    (re.compile(r"∈there"), "therein"),
    (re.compile(r"\b∀who\b"), "whoever"),
    (re.compile(r"\b∀which\b"), "whichever"),
    (re.compile(r"\b∀loc\b"), "wherever"),
    (re.compile(r"\b∀when\b"), "whenever"),
    (re.compile(r"\b∀\b"), "whatever"),
    (re.compile(r"∵"), "whereas"),
    (re.compile(r"∈"), "herein"),
    (re.compile(r"∴"), "therefore"),
    (re.compile(r"\bre:\b"), "について"),
]


def expand(text: str, *, counters: bool = True, compact: bool = True) -> str:
    """Best-effort inverse of compress for counters / a subset of short forms.

    Lossy: pronoun remaps, optional filler drops, unique-readings, and many _SUBS have no
    unique inverse. Only unambiguous counter and short-token mappings are reversed.
    """
    from shared.lex_policy import UNIQUE_COMPACT

    out = text
    if counters:
        for pat, repl in _EXPAND_COUNTERS:
            out = pat.sub(repl, out)
    # UNIQUE_COMPACT inverse (short → long) when unambiguous
    if compact:
        inv: dict[str, str] = {}
        for long, short in UNIQUE_COMPACT.items():
            if long == short:
                continue
            # skip collisions
            if short in inv and inv[short] != long:
                continue
            if short not in inv:
                inv[short] = long
        for short, long in sorted(inv.items(), key=lambda kv: len(kv[0]), reverse=True):
            out = re.sub(rf"(?i)\b{re.escape(short)}\b", long, out)
    for pat, repl in _EXPAND_SUBS:
        out = pat.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


_PACK_SPLIT = re.compile(
    r"(\s+|[^\w\s\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+)",
    re.UNICODE,
)


def pack_tokens(text: str) -> str:
    """Split on whitespace/punct and rejoin with minimal separators.

    CJK / Hangul runs stay glued (no space inserted between CJK-adjacent tokens).
    Latin/digit tokens get a single space between them. Punctuation stays attached
    lightly for layer-4 packing experiments.
    """
    if not text:
        return ""
    parts = [p for p in _PACK_SPLIT.split(text) if p is not None and p != ""]
    # Drop pure whitespace tokens; keep punct as their own tokens
    tokens: list[str] = []
    for p in parts:
        if p.isspace():
            continue
        tokens.append(p)

    def _is_cjkish(s: str) -> bool:
        return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", s))

    def _is_wordish(s: str) -> bool:
        return bool(re.match(r"^[\w]+$", s, re.UNICODE))

    out: list[str] = []
    for tok in tokens:
        if not out:
            out.append(tok)
            continue
        prev = out[-1]
        # No space between CJK runs or when either side is CJK-adjacent wordish
        if _is_cjkish(prev) or _is_cjkish(tok):
            out.append(tok)
        elif _is_wordish(prev) and _is_wordish(tok):
            out.append(" ")
            out.append(tok)
        elif _is_wordish(prev) and tok and tok[0] in "([{":
            out.append(" ")
            out.append(tok)
        else:
            # punctuation: attach without leading space for ,.;:!?)]}
            if tok and tok[0] in ",.;:!?)]}":
                out.append(tok)
            elif prev and prev[-1] in "([{":
                out.append(tok)
            elif _is_wordish(tok):
                out.append(" ")
                out.append(tok)
            else:
                out.append(tok)
    return "".join(out)


def density(before: str, after: str, *, extended_pronouns: bool = False) -> dict[str, float | int | dict]:
    b, a = len(before), len(after)
    ratio = (a / b) if b else 0.0
    pb = pronoun_bit_cost(after, extended=extended_pronouns)
    closed: dict[str, dict[str, float | int | list[str] | str]] = {}
    for name in list_closed_inventories():
        ext = extended_pronouns if name == "pronoun" else False
        c = closed_bit_cost(name, after, extended=ext)
        closed[name] = {
            "inventory_n": c["inventory_n"],
            "bits_per": c["bits_per"],
            "count": c["count"],
            "total_bits": c["total_bits"],
        }
    pol = polarity_bit_cost(after)
    return {
        "chars_before": b,
        "chars_after": a,
        "saved": b - a,
        "ratio": round(ratio, 4),
        "pronoun_inventory_n": pb["inventory_n"],
        "pronoun_bits_each": pb["bits_per_pronoun"],
        "pronoun_count": pb["count"],
        "pronoun_bits_total": pb["total_bits"],
        "utf8_bits_after": pb["utf8_bits_text"],
        "polarity_bits_each": pol["bits_per"],
        "polarity_count": pol["count"],
        "polarity_bits_total": pol["total_bits"],
        "closed": closed,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MorphoZip: layer-4 grammar-minimal compress")
    p.add_argument(
        "--mode",
        choices=("compress", "expand", "pack"),
        default="compress",
        help="compress (default), expand (lossy inverse), or pack_tokens",
    )
    p.add_argument("--text", help="input; else stdin")
    p.add_argument("--stats", action="store_true", help="print density metrics to stderr")
    p.add_argument(
        "--strip",
        action="store_true",
        help="opt-in filler strip (default off; fillers are C/ShorthandEdge)",
    )
    p.add_argument(
        "--no-strip",
        action="store_true",
        help="compat: fillers already kept by default",
    )
    p.add_argument("--no-unique", action="store_true", help="skip unique-reading pass")
    p.add_argument("--no-etymon", action="store_true", help="skip etymon alignment")
    p.add_argument("--no-counters", action="store_true", help="skip EN→JA counter mapping")
    p.add_argument(
        "--aggressive-fillers",
        action="store_true",
        help="opt-in aggressive filler strip (implies --strip)",
    )
    p.add_argument(
        "--hex-nums",
        action="store_true",
        help="rewrite integers to lowercase hex (0x…); default off",
    )
    p.add_argument(
        "--hex-bare",
        action="store_true",
        help="with --hex-nums, omit 0x prefix (bare 0-F style)",
    )
    p.add_argument(
        "--protect-regex",
        action="append",
        default=None,
        dest="protect_regex",
        help="regex whose matches are left unchanged (repeatable)",
    )
    p.add_argument(
        "--keep-articles",
        action="store_true",
        help="keep English articles the/a/an (default: strip unquoted)",
    )
    p.add_argument(
        "--spelled-nums",
        action="store_true",
        help="opt-in: spelled number words → digits (default: C owns this)",
    )
    args = p.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    if args.mode == "expand":
        out = expand(text, counters=not args.no_counters)
    elif args.mode == "pack":
        out = pack_tokens(text)
    else:
        out = compress(
            text,
            strip=args.strip and not args.no_strip,
            unique=not args.no_unique,
            etymon=not args.no_etymon,
            aggressive_fillers=args.aggressive_fillers,
            counters=not args.no_counters,
            spelled_nums=args.spelled_nums,
            keep_articles=args.keep_articles,
            hex_nums=args.hex_nums,
            hex_prefix=not args.hex_bare,
            protect_regexes=args.protect_regex,
        )
    if args.stats:
        import json

        print(json.dumps(density(text, out), ensure_ascii=False), file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
