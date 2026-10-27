#!/usr/bin/env python3
"""MorphoZip (E): intra-sentence multilingual / grammar-minimal compression (layer 4).

Prefer short low-ambiguity tokens that shrink prediction candidates
(e.g. ``I`` over 私は/僕は/俺は). Keep useful counters (匹/個). Compact
pronoun inventory (case-split nom/poss/obj: I–my–me … U–your–you … he–his–him … she–her … they–their–them; surface utf8+token first) plus closed
POS inventories (articles / conjunctions / adverbs / auxiliaries /
prepositions pack1 + prep2 / particles / compare). Polarity ``!``/``¬``
is a separate 1-bit flag (not inventory width). Avoid Chinese-only bias.

Shared lexeme policy (``shared.lex_policy``) usage:
- UNIQUE_READINGS long form only (``compact=False``) — anti-ambiguity
- ETYMON_ALIGN (comm / cfg / doc…; information→ℹ️ is C family=emoji)
- EN quantity phrases → short JA counters (experimental; needs digits already present)
- strip unquoted articles ``the`` / ``a`` / ``an`` (quoted forms keep the word)
- optional integer → hex rewrite (``hex_nums``)
- protected spans ``[[keep:...]]`` / `` `keep:...` `` (wrappers stripped)

Fillers, UNIQUE_COMPACT, EN contractions (``I'll``), and spelled-number
digitization are **C (ShorthandEdge)** by default. Optional ``strip=True`` /
``--strip`` / ``--aggressive-fillers`` / ``--spelled-nums`` remain for opt-in.
``--keep-articles`` disables article stripping.

``tho`` is informal **English** clipping of ``though`` (and contrastive
``however`` via ``however``→``though``→``tho``); not a foreign-language form.
Concessive/degree ``however hard…`` stays. Pronoun surfaces: you→``U``, he/she stay (open ``she`` slot; utf8+token first;
君/彼/她 input aliases). After he/she, EN 3sg ``-s``→base (``he chooses``→``he choose``).
``whichever``→``∀opt`` (no bare ``which`` residue). Purpose-for ML:
para/pour/für/ために/为了→``4``.
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
# Case axis (主格/所有格/目的格): do **not** collapse across case.
# Rows (nom–poss–obj): I–my–me | we–our–us | U–your–you | y'all–y'all's–y'all |
# he–his–him | she–her–her | it–its–it | they–their–them.
# Surface still utf8+token first (you_nom→U; he/she stay; no 彼/君 emit).
# Inventory bits = ceil(log2 N) for *design/report* only (same dual-metric spirit
# as other lex: token + utf8, cheapest, meaning gate) — not a surface override.
PRONOUN_CANONICAL: tuple[str, ...] = (
    # 1sg (incl. independent possessive mine)
    "I", "my", "me", "mine",
    # 1pl
    "we", "our", "us", "ours",
    # 2sg
    "U", "your", "you", "yours",
    # 2pl (y'all = EN compact plural; nom+obj share surface)
    "y'all", "y'all's",
    # 3sg M/F/N
    "he", "his", "him",
    "she", "her", "hers",
    "it", "its",
    # 3pl
    "they", "their", "them", "theirs",
)
# Extended: reflexive extras only (indep. poss now in core)
PRONOUN_EXTENDED: tuple[str, ...] = PRONOUN_CANONICAL + ("myself", "yourself", "themselves")
PRONOUN_ALIAS_TO_CANONICAL: dict[str, str] = {
    # --- 1sg ---
    "i": "I",
    "my": "my",
    "me": "me",
    "mine": "mine",
    "yo": "I",  # ES nom
    "je": "I",
    "ich": "I",
    # --- 1pl ---
    "we": "we",
    "our": "our",
    "ours": "ours",
    "us": "us",
    "nosotros": "we",
    "nous": "we",
    "wir": "we",
    # --- 2sg: nom U / poss your / obj you ---
    "u": "U",
    "your": "your",
    "yours": "yours",
    "you": "you",  # objective (nom rewritten to U in _SUBS)
    "君": "U",
    "君の": "your",
    "tú": "U",
    "tu": "U",
    "du": "U",
    "usted": "U",
    # --- 2pl ---
    "y'all": "y'all",
    "y'alls": "y'all's",
    "y'all's": "y'all's",
    "ustedes": "y'all",
    # --- 3sg M ---
    "he": "he",
    "his": "his",
    "him": "him",
    "彼": "he",
    "彼の": "his",
    "他": "he",
    "él": "he",
    "il": "he",
    # --- 3sg F (open she slot; do not fold into he) ---
    "she": "she",
    "her": "her",  # poss determiner + obj share EN surface
    "hers": "hers",
    "彼女": "she",
    "彼女の": "her",
    "她": "she",
    "她的": "her",
    "她の": "her",
    "ella": "she",
    "elle": "she",
    # --- 3sg N (neuter = things/objects; NO separate 物 slot) ---
    # Deixis (this/that/these/those, これ/それ/あれ, ça, eso, …) is a
    # *separate axis* — do not alias into it. Register deixis later.
    # 它 = ZH neuter pronoun for things (not deixis 这/那) → it.
    "it": "it",
    "its": "its",
    "它": "it",
    "它的": "its",
    # --- 3pl ---
    "they": "they",
    "them": "them",
    "their": "their",
    "theirs": "theirs",
    "ellos": "they",
    "ellas": "they",
    "ils": "they",
    "elles": "they",
}
_PRONOUN_SURFACE_RE = re.compile(
    r"y'all's|y'alls|y'all|君の|彼女の|彼の|她的|她の|"
    r"\btheirs\b|\btheir\b|\bthem\b|\bthey\b|\bmine\b|\bours\b|\byours\b|"
    r"\bustedes\b|\busted\b|\bellos\b|\bellas\b|\belles\b|\bils\b|\bnosotros\b|\bnous\b|\bwir\b|"
    r"\byo\b|\bje\b|\bich\b|\bt[uú]\b|\bdu\b|\b[eé]l\b|\bil\b|\bella\b|\belle\b|"
    r"\byou\b|\byour\b|\byourself\b|"
    r"\bhe\b|\bhim\b|\bhis\b|\bshe\b|\bher\b|\bhers\b|"
    r"\bwe\b|\bour\b|\bus\b|\bme\b|\bmy\b|\bits\b|\bit\b|"
    r"彼女|君|彼|她|他|\bU\b|\bI\b",
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
    "y": "&",  # ES
    "et": "&",  # FR
    "und": "&",  # DE
    "および": "&",
    "並びに": "&",
    "かつ": "&",
    "/": "/",
    "or": "/",
    "ou": "/",  # FR (bare ES o skipped — too ambiguous)
    "oder": "/",  # DE
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
    r"\band\b|\bor\b|\bund\b|\bet\b|\by\b|\boder\b|\bou\b|\bbc\b|[＆&/∴∵+]",
    re.I,
)

# --- adverb (副詞): discourse / degree ----------------------------------------
ADVERB_CANONICAL: tuple[str, ...] = ("tho", "~", "˅", "esp.")
ADVERB_EXTENDED: tuple[str, ...] = ("tho", "~", "˅", "esp.", "also", "□", "oft")
ADVERB_ALIAS_TO_CANONICAL: dict[str, str] = {
    "tho": "tho",
    # informal EN clip of though (not a foreign word). Compress: contrastive
    # however→though (gated), then though→tho. Concessive however hard… stays.
    "though": "tho",
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
    r"\bhowever\b|\bthough\b|\bextremely\b|\breally\b|\bvery\b|\balways\b|\boften\b|"
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
# from/から canonical is ← (pairs with particle →); fr kept as alias only —
# colloquial EN "for real" (fr) 揺らぎ risk; do not prefer emitting fr.
PREP_CANONICAL: tuple[str, ...] = ("w/", "4", "←", "@")
PREP_EXTENDED: tuple[str, ...] = ("w/", "4", "←", "@", "to")
PREP_ALIAS_TO_CANONICAL: dict[str, str] = {
    "w/": "w/",
    "with": "w/",
    "con": "w/",  # ES
    "avec": "w/",  # FR
    "mit": "w/",  # DE
    "4": "4",
    "for": "4",
    "para": "4",  # ES purpose-for
    "pour": "4",  # FR
    "für": "4",  # DE
    "fur": "4",
    "ために": "4",  # JA purpose-for
    "為に": "4",
    "为了": "4",  # ZH purpose-for
    "←": "←",
    "from": "←",
    "fr": "←",  # alias; for-real 揺らぎ — prefer ← as emitted short
    "desde": "←",  # ES
    "depuis": "←",  # FR
    "aus": "←",  # DE out-of/from
    "@": "@",
    "at": "@",
    "bei": "@",  # DE at/by
    "to": "to",
}
_PREP_SURFACE_RE = re.compile(
    r"\bwith\b|\bfrom\b|\bfor\b|\bto\b|\bat\b|"
    r"\bcon\b|\bavec\b|\bmit\b|\bpara\b|\bpour\b|\bf[uü]r\b|"
    r"\bdesde\b|\bdepuis\b|\baus\b|\bbei\b|"
    r"ために|為に|为了|"
    r"w/|\bfr\b|\b4\b|@|←",
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
    "sin": "无",  # ES
    "sans": "无",  # FR
    "ohne": "无",  # DE
    "内": "内",
    "within": "内",
    "dentro": "内",  # ES
    "innerhalb": "内",  # DE
    "前": "前",
    "before": "前",
    "antes": "前",  # ES
    "avant": "前",  # FR
    "vor": "前",  # DE
    "後": "後",
    "后": "後",
    "after": "後",
    "después": "後",  # ES
    "despues": "後",
    "après": "後",  # FR
    "apres": "後",
    "nach": "後",  # DE after (also to — accepted alias)
}
_PREP2_SURFACE_RE = re.compile(
    r"\bwithout\b|\bwithin\b|\bbefore\b|\bafter\b|\bof\b|w/o|"
    r"\bsin\b|\bsans\b|\bohne\b|\bdentro\b|\binnerhalb\b|"
    r"\bantes\b|\bavant\b|\bvor\b|"
    r"\bdespu[eé]s\b|\bapr[eè]s\b|\bnach\b|"
    r"无|内|前|后|後|\bde\b",
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
# Conflicts (documented): と→& overlaps conj & (OK tokenize-wise);
# から→← shares prep from slot (← pairs with に/へ→→); fr is alias only (for-real 揺らぎ).
# で→∈ (not @; @ is prep at). C ledger 前後/内外 pairs untouched (bare 前/後 are prep2).
# は/が topic vs subject collapsed to ∅ (recoverable); を→∅; ね/よ/さ→∅.
PARTICLE_CANONICAL: tuple[str, ...] = ("∅", "→", "∈", "〜")
PARTICLE_EXTENDED: tuple[str, ...] = ("∅", "→", "∈", "〜", "+", "&", "←")
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
    "←": "←",
    "から": "←",
    "fr": "←",  # alias only; same as prep from
}
_PARTICLE_SURFACE_RE = re.compile(
    r"までは|からは|には|では|とは|"
    r"まで|から|"
    r"[はねよさをがにへとでも]|"
    r"→|←|∈|〜|\+|\bfr\b|&",
)

# Polarity flag (! / ¬): extra 1 bit, separate from aux/adverb inventory width.
# Shared by auxiliary negation (!can) and adverb not/never.
POLARITY_BIT = 1
POLARITY_MARKERS: tuple[str, ...] = ("!", "¬")


# --- deixis (指示代名詞) — separate axis from person/neuter pronouns -------------
# NOT folded into it. Canonical = cheapest surface per slot (token → utf8).
# Slots: proximal/distal × sg/pl + JA far-distal あれ.
# FR/ES compact (ça/eso) and ZH 这/那 win when cheaper than EN/JA.
DEIXIS_CANONICAL: tuple[str, ...] = (
    "ça",    # proximal sg (this/これ/esto/ceci/这 → ça)
    "eso",   # distal sg   (that/それ/cela/那 → eso)
    "these", # proximal pl
    "those", # distal pl
    "あれ",   # JA far-distal (no cheaper cross-lang peer)
)
DEIXIS_EXTENDED: tuple[str, ...] = DEIXIS_CANONICAL + ("これ", "それ", "this", "that")
DEIXIS_ALIAS_TO_CANONICAL: dict[str, str] = {
    # proximal sg → ça
    "this": "ça",
    "これ": "ça",
    "これは": "ça",
    "これが": "ça",
    "これを": "ça",
    "これの": "ça",
    "ça": "ça",
    "ca": "ça",
    "esto": "ça",
    "ceci": "ça",
    "这": "ça",
    "这个": "ça",
    # distal sg → eso
    "that": "eso",
    "それ": "eso",
    "それは": "eso",
    "それが": "eso",
    "それを": "eso",
    "それの": "eso",
    "eso": "eso",
    "esa": "eso",
    "cela": "eso",
    "那": "eso",
    "那个": "eso",
    # proximal pl → these
    "these": "these",
    "これら": "these",
    "これらの": "these",
    "estos": "these",
    "estas": "these",
    "ceux-ci": "these",
    "这些": "these",
    # distal pl → those
    "those": "those",
    "それら": "those",
    "それらの": "those",
    "esos": "those",
    "esas": "those",
    "ceux-là": "those",
    "ceux-la": "those",
    "那些": "those",
    # far distal → あれ
    "あれ": "あれ",
    "あれは": "あれ",
    "あれが": "あれ",
    "あれを": "あれ",
    "あれの": "あれ",
    "aquel": "あれ",
    "aquella": "あれ",
}
_DEIXIS_SURFACE_RE = re.compile(
    r"これらの|それらの|これの|それの|あれの|"
    r"これは|これが|これを|それは|それが|それを|あれは|あれが|あれを|"
    r"これ|それ|あれ|"
    r"这些|那些|这个|那个|[这那]|"
    r"ceux-là|ceux-la|ceux-ci|"
    r"\bthese\b|\bthose\b|\bthis\b|\bthat\b|"
    r"\bestos\b|\bestas\b|\besos\b|\besas\b|"
    r"\besto\b|\beso\b|\besa\b|\baquel\b|\baquella\b|"
    r"\bceci\b|\bcela\b|\b(?:ça|ça|ca)\b",
    re.I,
)

CLOSED_INVENTORIES: dict[str, ClosedInventory] = {
    "pronoun": ClosedInventory(
        "pronoun",
        PRONOUN_CANONICAL,
        PRONOUN_EXTENDED,
        PRONOUN_ALIAS_TO_CANONICAL,
        _PRONOUN_SURFACE_RE,
        "case-split core + indep. poss (mine/ours/yours/theirs/hers): I/my/me/mine … U/your/you/yours … he/his/him … she/her/hers … it/its (neuter=things) … they/their/them/theirs + y'all; N→ceil(log2 N) bits design/report; surface utf8+token first; deixis = separate inventory",
    ),
    "deixis": ClosedInventory(
        "deixis",
        DEIXIS_CANONICAL,
        DEIXIS_EXTENDED,
        DEIXIS_ALIAS_TO_CANONICAL,
        _DEIXIS_SURFACE_RE,
        "指示代名詞 axis (≠ person/neuter it): this/これ/这→ça; that/それ/那→eso; these/これら; those/それら; あれ far-distal; token→utf8 cheapest; N=5→3bit design/report",
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
        "pack1 w/|4|←|@ → 2bit; from/から→← (fr alias, for-real 揺らぎ); ML con/avec/mit, para/pour/für, ために/為に/为了, desde/depuis/aus, bei; skip C under/above; in/on deferred; for→4 揺らぎ別評価",
    ),
    "prep2": ClosedInventory(
        "prep2",
        PREP2_CANONICAL,
        PREP2_EXTENDED,
        PREP2_ALIAS_TO_CANONICAL,
        _PREP2_SURFACE_RE,
        "pack2 de|无|内|前|後 → N=5→3bit; ML sin/sans/ohne, dentro/innerhalb, antes/avant/vor, después/après/nach; of→de without→无 within→内 before→前 after→後",
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

def deixis_inventory_bits(*, extended: bool = False) -> int:
    return closed_inventory_bits("deixis", extended=extended)


def canonicalize_deixis(form: str, *, extended: bool = False) -> str | None:
    return canonicalize_closed("deixis", form, extended=extended)


def deixis_bit_cost(text: str, *, extended: bool = False) -> dict[str, float | int | list[str]]:
    return closed_bit_cost("deixis", text, extended=extended)


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
    # Gender-pair phrases: keep both EN surfaces; do NOT collapse to they
    (re.compile(r"\bhe or she\b", re.I), "he/she"),
    (re.compile(r"\bshe or he\b", re.I), "she/he"),
    (re.compile(r"\bhim or her\b", re.I), "him/her"),
    (re.compile(r"\bher or him\b", re.I), "her/him"),
    (re.compile(r"\bhis or her\b", re.I), "his/her"),
    (re.compile(r"\bher or his\b", re.I), "her/his"),
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
    # ES/FR/DE subject-side (same bit slots; skip ambiguous el/er/sie/vous)
    (re.compile(r"\byo\b", re.I), "I"),
    (re.compile(r"\bje\b", re.I), "I"),
    (re.compile(r"\bich\b", re.I), "I"),
    (re.compile(r"\bustedes\b", re.I), "y'all"),
    (re.compile(r"\busted\b", re.I), "U"),
    (re.compile(r"\bt[uú]\b", re.I), "U"),
    # DE du: alias-only (FR du = de+le false friend)
    (re.compile(r"\bellos\b", re.I), "they"),
    (re.compile(r"\bellas\b", re.I), "they"),
    (re.compile(r"\belles\b", re.I), "they"),
    (re.compile(r"\bils\b", re.I), "they"),
    # 3sg Romance → he/she (EN surface; utf8+token over 彼/她)
    (re.compile(r"\bella\b", re.I), "she"),
    (re.compile(r"\belle\b", re.I), "she"),
    (re.compile(r"\bél\b", re.I), "he"),  # accented only (el = article)
    (re.compile(r"\bil\b", re.I), "he"),
    # JA/ZH 3sg — case-split (do not emit 彼/她; do not collapse を into nom)
    (re.compile(r"彼女の"), "her"),
    (re.compile(r"彼女を"), "her"),
    (re.compile(r"彼女は|彼女が|彼女"), "she"),
    (re.compile(r"彼の|かれの"), "his"),
    (re.compile(r"彼を|かれを"), "him"),
    (re.compile(r"彼は|彼が|彼|かれ|他"), "he"),
    (re.compile(r"她的"), "her"),
    (re.compile(r"她"), "she"),
    # EN 3sg: keep he/she/him/her/his (case intact; do NOT rewrite to 彼/她)
    # 2sg case-split: nom→U, poss→your, obj→you. Skip discourse you know/see (C).
    (re.compile(r"あなたの|お前の|君の"), "your"),
    (re.compile(r"あなたを|お前を|君を"), "you"),
    (re.compile(r"あなたは|あなたが|お前は|お前が|君は|君が|あなた|お前|君"), "U"),
    (re.compile(r"你"), "U"),
    # EN your/yours stay (poss); yourself → you (obj-ish)
    (re.compile(r"\byourself\b", re.I), "you"),
    # obj you after common verb/prep — sentinel so later nom you→U cannot re-eat
    (re.compile(
        r"\b(see|saw|seen|meet|met|tell|told|give|gave|given|ask|asked|"
        r"for|to|with|from|at|on|about|of|near|call|called|show|showed|shown)\s+you\b",
        re.I,
    ), r"\1 <<YOUOBJ>>"),
    (re.compile(r"\byou\b(?!\s+(?:know|see)\b)", re.I), "U"),
    # Deixis inventory (≠ neuter it): token→utf8 cheapest per slot.
    # proximal sg → ça; distal sg → eso; pl → these/those; far → あれ.
    (re.compile(r"これらの|これら"), "these"),
    (re.compile(r"それらの|それら"), "those"),
    (re.compile(r"これの|これは|これが|これを|これ"), "ça"),
    (re.compile(r"それの|それは|それが|それを|それ"), "eso"),
    (re.compile(r"あれの|あれは|あれが|あれを|あれ"), "あれ"),
    (re.compile(r"这些"), "these"),
    (re.compile(r"那些"), "those"),
    (re.compile(r"这个|这"), "ça"),
    (re.compile(r"那个|那"), "eso"),
    (re.compile(r"\bthese\b", re.I), "these"),
    (re.compile(r"\bthose\b", re.I), "those"),
    (re.compile(r"\bthis\b", re.I), "ça"),
    # EN that: demonstrative only — skip complementizer/relative
    # ("I think that…", "the book that…"). Keep bare that when ambiguous.
    (re.compile(r"\bthat('s|s)\b", re.I), r"eso\1"),
    (re.compile(r"\bthat\s+(one|ones|thing|stuff|guy|girl|man|woman|person|people|day|time|way|book|idea|problem|issue|point|part|side|end)\b", re.I), r"eso \1"),
    (re.compile(r"\bthat\s+(is|was|were|are|be|being|been)\b", re.I), r"eso \1"),
    (re.compile(r"(?m)^that\b", re.I), "eso"),
    (re.compile(r"([.!?…]\s*)that\b", re.I), r"\1eso"),
    (re.compile(r"\besto\b", re.I), "ça"),
    (re.compile(r"\b(?:eso|esa)\b", re.I), "eso"),
    (re.compile(r"\bestos\b|\bestas\b", re.I), "these"),
    (re.compile(r"\besos\b|\besas\b", re.I), "those"),
    (re.compile(r"\bceci\b", re.I), "ça"),
    (re.compile(r"\bcela\b", re.I), "eso"),
    (re.compile(r"\b(?:ça|ça)\b", re.I), "ça"),
    (re.compile(r"\baquel(?:la)?\b", re.I), "あれ"),
    # Neuter it/its = things/objects (no 物 slot). ZH 它 = neuter → it (not deixis).
    (re.compile(r"它的"), "its"),
    (re.compile(r"它"), "it"),
    # EN case forms already short — leave I/my/me/he/him/his/she/her/they/them/…
    # Purpose-for JA/ZH before particle に→→ (ために would otherwise become ため→)
    (re.compile(r"ために|為に"), "4"),
    (re.compile(r"为了"), "4"),
    # EN multi-word → compact symbols (not I'll-family contractions)
    # within before with (prefix); without→无 preferred (w/o remains alias in prep2)
    (re.compile(r"\bwithin\b", re.I), "内"),
    (re.compile(r"\bwithout\b", re.I), "无"),
    (re.compile(r"\bw/o\b", re.I), "无"),
    # throughout / therewith before with→w/ (prefix / compound)
    (re.compile(r"\bthroughout\b", re.I), "通"),
    (re.compile(r"\bpartout\b", re.I), "通"),  # FR
    (re.compile(r"\btherewith\b", re.I), "∴w/"),
    # --- finite high-freq prep / prep-like adv (not closed-inventory N growth) ---
    # multiword BEFORE of→de / from→← (else "out of"→"out de", "far from"→"far ←")
    (re.compile(r"\bin spite of\b", re.I), "雖"),
    (re.compile(r"\bin front of\b", re.I), "前"),
    (re.compile(r"\bin back of\b", re.I), "後"),
    (re.compile(r"\baccording to\b", re.I), "依"),
    (re.compile(r"\bowing to\b", re.I), "因"),
    (re.compile(r"\bdue to\b", re.I), "因"),
    (re.compile(r"\bprior to\b", re.I), "前"),
    (re.compile(r"\bsubsequent to\b", re.I), "後"),
    (re.compile(r"\bnext to\b", re.I), "傍"),
    (re.compile(r"\bclose to\b", re.I), "近"),
    (re.compile(r"\bfar from\b", re.I), "遠"),
    (re.compile(r"\baway from\b", re.I), "離"),
    (re.compile(r"\bout of\b", re.I), "外"),
    (re.compile(r"\bopposite to\b", re.I), "対側"),
    (re.compile(r"\bopposite\b", re.I), "対側"),
    (re.compile(r"\bacross\b", re.I), "↔"),
    (re.compile(r"\balong\b", re.I), "沿"),
    (re.compile(r"\balongside\b", re.I), "傍"),
    (re.compile(r"\bamong(?:st)?\b", re.I), "中"),
    (re.compile(r"\bamid(?:st)?\b", re.I), "中"),
    (re.compile(r"\bbeside\b", re.I), "傍"),
    (re.compile(r"\bbesides\b", re.I), "他"),
    (re.compile(r"\bbeyond\b", re.I), "≫"),
    (re.compile(r"\bbetween\b", re.I), "間"),
    (re.compile(r"\bagainst\b", re.I), "対"),
    (re.compile(r"\baround\b", re.I), "○"),
    (re.compile(r"\bduring\b", re.I), "中"),
    (re.compile(r"\bexcept\b", re.I), "除"),
    (re.compile(r"\bincluding\b", re.I), "含"),
    (re.compile(r"\binside\b", re.I), "内"),
    (re.compile(r"\boutside\b", re.I), "外"),
    (re.compile(r"\bthrough\b", re.I), "通"),
    (re.compile(r"\bthru\b", re.I), "通"),
    (re.compile(r"\buntil\b", re.I), "〜"),
    (re.compile(r"\btill\b", re.I), "〜"),
    (re.compile(r"\bdespite\b", re.I), "雖"),
    (re.compile(r"\baboard\b", re.I), "乗"),
    (re.compile(r"\boverhead\b", re.I), "頭上"),
    (re.compile(r"\boverseas\b", re.I), "海外"),
    (re.compile(r"\bunderground\b", re.I), "地下"),
    (re.compile(r"\bunderneath\b", re.I), "下"),  # pairs C spatial-under
    (re.compile(r"\bupstairs\b", re.I), "上階"),
    (re.compile(r"\bdownstairs\b", re.I), "下階"),
    (re.compile(r"\bindoors\b", re.I), "屋内"),
    (re.compile(r"\boutdoors\b", re.I), "屋外"),
    (re.compile(r"\bahead\b", re.I), "→"),
    (re.compile(r"\baside\b", re.I), "脇"),
    (re.compile(r"\bapart\b", re.I), "離"),
    (re.compile(r"\btogether\b", re.I), "共"),
    (re.compile(r"\binstead\b(?!\s+of\b)", re.I), "代"),  # bare; "instead of" → vs in phrases
    (re.compile(r"\bmeanwhile\b", re.I), "∥"),
    (re.compile(r"\bafterwards\b", re.I), "後"),
    (re.compile(r"\bnearby\b", re.I), "近"),
    (re.compile(r"\bbeneath\b", re.I), "下"),  # pairs C spatial-under
    (re.compile(r"\bcirca\b", re.I), "c."),
    (re.compile(r"\binto\b", re.I), "入"),
    (re.compile(r"\bbeforehand\b", re.I), "先"),
    (re.compile(r"\bforever\b", re.I), "∞"),
    (re.compile(r"\bovernight\b", re.I), "泊"),
    (re.compile(r"\bthereafter\b", re.I), "後"),
    (re.compile(r"\beverywhere\b", re.I), "∀loc"),
    (re.compile(r"\bsomewhere\b", re.I), "某处"),
    (re.compile(r"\belsewhere\b", re.I), "别处"),
    (re.compile(r"\banew\b", re.I), "再"),
    (re.compile(r"\bwith\b", re.I), "w/"),
    (re.compile(r"\band\b", re.I), "&"),
    (re.compile(r"\bund\b", re.I), "&"),  # DE
    # FR et / ES y: alias-only (et al.; EN "x and y")
    (re.compile(r"\bor\b", re.I), "/"),
    (re.compile(r"\boder\b", re.I), "/"),  # DE
    (re.compile(r"\bou\b", re.I), "/"),  # FR

    (re.compile(r"\bbecause\b", re.I), "bc"),
    (re.compile(r"\btherefore\b", re.I), "∴"),
    # Contrastive however → though (general EN synonym). Skip concessive/degree
    # "however hard/much/…" (however + Adj/Adv). Safe on "However," / "however I …".
    # Separate rule below: though → tho (informal EN clip). Two general rules,
    # not a special-cased however→tho exception.
    (
        re.compile(
            r"\bhowever\b(?!\s+(?:"
            r"hard|difficult|easy|much|many|long|far|often|well|bad|good|"
            r"late|early|fast|slow|strong|weak|big|small|high|low|"
            r"important|different|similar|possible|necessary|likely|"
            r"great|little|few|large|huge|tiny|brief|short|"
            r"approximately|very|really|extremely|especially|particularly|"
            r"\w+(?:ly|ier|iest)"
            r")\b)",
            re.I,
        ),
        "though",
    ),
    # Informal EN clipping: though → tho (not a foreign-language form).
    (re.compile(r"\bthough\b", re.I), "tho"),
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
    (re.compile(r"からは"), "←"),
    (re.compile(r"までは"), "〜"),
    (re.compile(r"には"), "→"),
    (re.compile(r"では(?!ない)"), "∈"),
    (re.compile(r"とは"), "&"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])まで"), "〜"),
    # から: particle-from → ← (pairs with に/へ→→; fr is alias only — for-real 揺らぎ)
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])から"), "←"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])(?:に|へ)"), "→"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])で(?!き|す|あっ|しょ|した|も|ござ)"), "∈"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])と(?!し|ころ|り|りあえず)"), "&"),
    # After you→U / 彼→he, JA と/も may follow ASCII pronoun surfaces
    (re.compile(r"\b(he|she|I|U|they|we|it)と(?!し|ころ|り|りあえず)", re.I), r"\1&"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])も"), "+"),
    (re.compile(r"\b(he|she|I|U|they|we|it)も", re.I), r"\1+"),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])を"), ""),
    # は/が: drop after CJK; skip は in はい/はあ discourse; が in known starts rare
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])は(?!い|あ|ず)"), ""),
    (re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])が(?!る|ん|っ|ち|く|くせい)"), ""),
    # sentence-final modality particles
    (re.compile(r"[ねよさ]+(?=[。．.!！？?]|$)"), ""),
    # --- prepositions pack1; C owns under/above/below/beneath — skip
    # from/から → ← (LTR-minimal; pairs with →). fr not emitted (for-real 揺らぎ); fr alias in inventory only.
    (re.compile(r"\bdesde\b", re.I), "←"),  # ES
    (re.compile(r"\bdepuis\b", re.I), "←"),  # FR
    (re.compile(r"\baus\b", re.I), "←"),  # DE
    (re.compile(r"\bfrom\b", re.I), "←"),
    # toward(s) → → (pairs with ← from; same surface as particle に/へ)
    (re.compile(r"\btowards?\b", re.I), "→"),
    (re.compile(r"\bhacia\b", re.I), "→"),  # ES
    (re.compile(r"\bvers\b", re.I), "→"),  # FR
    # NOTE(for→4): 表層 4 は数字の four と揺らぎうる。ビット在庫(2bit)とは別に評価し、将来 for（原形）等へ戻る可能性あり（現状は 4 のまま）。
    (re.compile(r"\bpara\b", re.I), "4"),  # ES purpose-for
    (re.compile(r"\bpour\b", re.I), "4"),  # FR
    (re.compile(r"\bf[uü]r\b", re.I), "4"),  # DE
    (re.compile(r"\bfor\b", re.I), "4"),
    (re.compile(r"\bcon\b", re.I), "w/"),  # ES
    (re.compile(r"\bavec\b", re.I), "w/"),  # FR
    (re.compile(r"\bmit\b", re.I), "w/"),  # DE
    (re.compile(r"\bbei\b", re.I), "@"),  # DE at/by
    (re.compile(r"\bat\b", re.I), "@"),
    # --- prep2: of→de / before→前 / after→後 (within/without already above)
    (re.compile(r"\binnerhalb\b", re.I), "内"),
    (re.compile(r"\bdentro\b", re.I), "内"),
    # sin/sans: alias-only (EN false friends); ohne rare enough to rewrite
    (re.compile(r"\bohne\b", re.I), "无"),
    (re.compile(r"\bantes\b", re.I), "前"),
    (re.compile(r"\bavant\b", re.I), "前"),
    (re.compile(r"\bvor\b", re.I), "前"),
    (re.compile(r"\bbefore\b", re.I), "前"),
    (re.compile(r"\bdespu[eé]s\b", re.I), "後"),
    (re.compile(r"\bapr[eè]s\b", re.I), "後"),
    (re.compile(r"\bnach\b", re.I), "後"),
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
    (re.compile(r"\bwhichever\b", re.I), "∀opt"),  # no bare "which" residue
    (re.compile(r"\bwherever\b", re.I), "∀loc"),
    (re.compile(r"\bwhenever\b", re.I), "∀when"),
    (re.compile(r"\bnonetheless\b", re.I), "tho∴"),
    (re.compile(r"\bhereinafter referred to as\b", re.I), "∴="),
    (re.compile(r"\bhereinafter\b", re.I), "∴↓"),
    (re.compile(r"\bhereafter\b", re.I), "∴→"),
    (re.compile(r"\bherein\b", re.I), "∈"),
    (re.compile(r"\bthereof\b", re.I), "∴of"),
    (re.compile(r"\btherein\b", re.I), "∈there"),
    (re.compile(r"\bwhereby\b", re.I), "∴by"),
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



# --- EN 3sg → base after 3sg pronouns (he/she; legacy 彼/她) -------------------
# Once subject is a marked 3sg pronoun, English 3sg -s is redundant → prototype.
# you→U does not take 3sg. Irregulars: has/does/goes.
_IRREG_3SG_BASE: dict[str, str] = {
    "has": "have",
    "does": "do",
    "goes": "go",
}
# Fixed-width lookbehinds only: match pronoun+space+verb, keep pronoun.
_AFTER_INV_PRON_VERB = re.compile(
    r"\b([Hh]e|[Ss]he|彼|她)\s([A-Za-z]+)\b"
)



def _en_verb_base_from_3sg(verb: str) -> str:
    """Map EN 3sg surface to base/prototype; leave non-3sg unchanged."""
    low = verb.lower()
    if low in _IRREG_3SG_BASE:
        base = _IRREG_3SG_BASE[low]
        if verb.isupper():
            return base.upper()
        if verb[0].isupper():
            return base.capitalize()
        return base
    # flies → fly; watches → watch; comes → come
    if len(low) > 3 and low.endswith("ies"):
        stem = verb[:-3] + ("Y" if verb[-3].isupper() else "y")
        return stem
    if len(low) > 3 and low.endswith(("sses", "zzes", "xes", "ches", "shes")):
        return verb[:-2]
    if low.endswith("oes") and len(low) > 3:  # does already irregular; heroes-like rare
        return verb[:-2]
    if low.endswith("s") and not low.endswith("ss") and len(low) > 2:
        # avoid stripping plural-looking nouns blindly: only clear verbal -s
        return verb[:-1]
    return verb


def drop_3sg_after_inventory_pronoun(text: str) -> str:
    """After he/she (or legacy 彼/她), fold EN 3sg -s to base verb (原型).

    ``he chooses`` → ``he choose``. Possessives do not trigger.
    """

    def _sub(m: re.Match[str]) -> str:
        return f"{m.group(1)} {_en_verb_base_from_3sg(m.group(2))}"

    return _AFTER_INV_PRON_VERB.sub(_sub, text or "")


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
    # Pronoun inventory already folded → drop redundant EN 3sg -s (原型)
    out = drop_3sg_after_inventory_pronoun(out).replace('<<YOUOBJ>>', 'you')
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
    (re.compile(r"←"), "from"),
    (re.compile(r"\bfr\b", re.I), "from"),  # legacy alias short
    (re.compile(r"\bw/\b", re.I), "with"),
    (re.compile(r"\bU\b"), "you"),  # capital U pronoun surface
    (re.compile(r"\bu r\b", re.I), "you are"),
    (re.compile(r"\bbc\b", re.I), "because"),
    (re.compile(r"\btho∴\b"), "nonetheless"),
    (re.compile(r"\btho\b", re.I), "though"),  # informal EN clip inverse
    (re.compile(r"∴↓"), "hereinafter"),
    (re.compile(r"∴→"), "hereafter"),
    (re.compile(r"∴="), "hereinafter referred to as"),
    (re.compile(r"∴of"), "thereof"),
    (re.compile(r"∴w/"), "therewith"),
    (re.compile(r"∴by"), "whereby"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])通(?![\w\u3040-\u30ff\u3400-\u9fff])"), "throughout"),
    (re.compile(r"↔"), "across"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])沿(?![\w\u3040-\u30ff\u3400-\u9fff])"), "along"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])傍(?![\w\u3040-\u30ff\u3400-\u9fff])"), "beside"),
    (re.compile(r"≫"), "beyond"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])間(?![\w\u3040-\u30ff\u3400-\u9fff])"), "between"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])対(?![\w\u3040-\u30ff\u3400-\u9fff])"), "against"),
    (re.compile(r"○"), "around"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])除(?![\w\u3040-\u30ff\u3400-\u9fff])"), "except"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])含(?![\w\u3040-\u30ff\u3400-\u9fff])"), "including"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])外(?![\w\u3040-\u30ff\u3400-\u9fff])"), "outside"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])雖(?![\w\u3040-\u30ff\u3400-\u9fff])"), "despite"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])乗(?![\w\u3040-\u30ff\u3400-\u9fff])"), "aboard"),
    (re.compile(r"∥"), "meanwhile"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])共(?![\w\u3040-\u30ff\u3400-\u9fff])"), "together"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])代(?![\w\u3040-\u30ff\u3400-\u9fff])"), "instead"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])近(?![\w\u3040-\u30ff\u3400-\u9fff])"), "nearby"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])依(?![\w\u3040-\u30ff\u3400-\u9fff])"), "according to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])因(?![\w\u3040-\u30ff\u3400-\u9fff])"), "due to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])対側(?![\w\u3040-\u30ff\u3400-\u9fff])"), "opposite"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])遠(?![\w\u3040-\u30ff\u3400-\u9fff])"), "far from"),
    (re.compile(r"\bc\.(?!\w)"), "circa"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])入(?![\w\u3040-\u30ff\u3400-\u9fff])"), "into"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])先(?![\w\u3040-\u30ff\u3400-\u9fff])"), "beforehand"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])泊(?![\w\u3040-\u30ff\u3400-\u9fff])"), "overnight"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])某处(?![\w\u3040-\u30ff\u3400-\u9fff])"), "somewhere"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])别处(?![\w\u3040-\u30ff\u3400-\u9fff])"), "elsewhere"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])再(?![\w\u3040-\u30ff\u3400-\u9fff])"), "anew"),
    (re.compile(r"∈there"), "therein"),
    (re.compile(r"\b∀who\b"), "whoever"),
    (re.compile(r"\b∀opt\b"), "whichever"),
    (re.compile(r"\b∀which\b"), "whichever"),  # legacy
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
