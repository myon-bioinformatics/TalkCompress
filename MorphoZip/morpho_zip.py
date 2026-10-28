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
君/彼/她 input aliases). After marked singular subjects (he/she/it/one/someone|everybody; ça/eso; legacy 彼/她), EN 3sg ``-s``→base (``he chooses``→``he choose``; skip non-verb -s / 単複同形).
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
    (re.compile(r"彼は|彼が|彼|かれ|(?<![\w\u3040-\u30ff\u3400-\u9fff])他(?![\u3400-\u9fff])"), "he"),
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
    # bare that+(is|was|…) → eso REMOVED: eats relative `N that BE` after which→that.
    # Demonstrative "that is" → i.e. in _PHRASE_GRAMMAR; ^that / post-punct that /
    # that's / that one|thing|… still cover deixis.
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
    # cycle2 multiword prep (before of→de / from→← / with→w/)
    (re.compile(r"\bin favou?r of\b", re.I), "pro"),
    (re.compile(r"\bon behalf of\b", re.I), "代表"),
    (re.compile(r"\bby means of\b", re.I), "手段"),
    (re.compile(r"\bin terms of\b", re.I), "観点"),
    (re.compile(r"\bin accordance with\b", re.I), "準"),
    (re.compile(r"\bpursuant to\b", re.I), "準"),
    (re.compile(r"\bas for\b", re.I), "re:"),
    (re.compile(r"\bas to\b", re.I), "re:"),
    (re.compile(r"\bup to\b", re.I), "≦"),
    (re.compile(r"\bdown to\b", re.I), "至"),
    (re.compile(r"\bin between\b", re.I), "間"),
    (re.compile(r"\boff of\b", re.I), "外"),
    (re.compile(r"\bout from\b", re.I), "出"),
    (re.compile(r"\bin light of\b", re.I), "鑑"),
    (re.compile(r"\bin view of\b", re.I), "鑑"),
    (re.compile(r"\bin lieu of\b", re.I), "代"),
    (re.compile(r"\bin place of\b", re.I), "代"),
    (re.compile(r"\bin case of\b", re.I), "場合"),
    (re.compile(r"\bregardless of\b", re.I), "不問"),
    (re.compile(r"\birrespective of\b", re.I), "不問"),
    (re.compile(r"\baside from\b", re.I), "他"),
    (re.compile(r"\bapart from\b", re.I), "他"),
    (re.compile(r"\bother than\b", re.I), "他"),
    (re.compile(r"\balong with\b", re.I), "共"),
    (re.compile(r"\btogether with\b", re.I), "共"),
    (re.compile(r"\bas opposed to\b", re.I), "vs"),
    (re.compile(r"\brather than\b", re.I), "vs"),
    (re.compile(r"\bunlike\b", re.I), "≠"),
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
    # cycle2 spatial / time prep-like
    (re.compile(r"\bpast\b", re.I), "過"),
    (re.compile(r"\bround\b", re.I), "○"),
    (re.compile(r"\bfollowing\b", re.I), "次"),
    (re.compile(r"\bpreceding\b", re.I), "先"),
    (re.compile(r"\bpending\b", re.I), "未決"),
    (re.compile(r"\bwith\b", re.I), "w/"),
    (re.compile(r"\band\b", re.I), "&"),
    (re.compile(r"\bund\b", re.I), "&"),  # DE
    # FR et / ES y: alias-only (et al.; EN "x and y")
    (re.compile(r"\bor\b", re.I), "/"),
    (re.compile(r"\boder\b", re.I), "/"),  # DE
    (re.compile(r"\bou\b", re.I), "/"),  # FR

    (re.compile(r"\bbecause\b", re.I), "bc"),
    (re.compile(r"\btherefore\b", re.I), "∴"),
    # Resultatives share ∴ (cheaper than so). thereby stays: by-that-means ≠ therefore,
    # and ∴by is whereby.
    (re.compile(r"\bhence\b", re.I), "∴"),
    (re.compile(r"\bthus\b", re.I), "∴"),
    (re.compile(r"\baccordingly\b", re.I), "∴"),
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
    # Formal concessives (not contrastive however). even though is phrase-grammar.
    (re.compile(r"\balthough\b", re.I), "tho"),
    (re.compile(r"\balbeit\b", re.I), "tho"),
    (re.compile(r"\bapproximately\b", re.I), "~"),
    (re.compile(r"\broughly\b(?!\s+equal\b)", re.I), "~"),
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
    (re.compile(r"\bhenceforth\b", re.I), "∴→"),  # same sense as hereafter
    (re.compile(r"\bherein\b", re.I), "∈"),
    (re.compile(r"\bthereof\b", re.I), "∴of"),
    # ∈there loses utf8; ∈it is the dual-metric win (in that). Not herein's bare ∈.
    (re.compile(r"\btherein\b", re.I), "∈it"),
    (re.compile(r"\bthereto\b", re.I), "∴to"),  # to that; not → (toward)
    (re.compile(r"\bwhereby\b", re.I), "∴by"),
    (re.compile(r"\bwhereas\b", re.I), "∵"),
    # Prepositional concessive. tho/but lose "notwithstanding §5".
    # despite itself is already →雖 (prep tranche); emit that terminal directly.
    (re.compile(r"\bnotwithstanding\b", re.I), "雖"),
    (re.compile(r"\bnamely\b", re.I), "viz"),
    (re.compile(r"\bviz\."), "viz"),
    (re.compile(r"\baforementioned\b", re.I), "said"),
    (re.compile(r"\baforesaid\b", re.I), "said"),
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
    (re.compile(r"\bin particular\b", re.I), "特"),
    (re.compile(r"\bin addition to\b", re.I), "+"),
    (re.compile(r"\bin addition\b", re.I), "+"),
    (re.compile(r"\binstead of\b", re.I), "vs"),
    # cycle3 multiword prep (phrase-grammar: before article strip / for→4 / of→de)
    (re.compile(r"\bat the expense of\b", re.I), "犠牲"),
    (re.compile(r"\bat the risk of\b", re.I), "危"),
    (re.compile(r"\bin the event of\b", re.I), "場合"),
    (re.compile(r"\bin the middle of\b", re.I), "最中"),
    (re.compile(r"\bin the midst of\b", re.I), "最中"),
    (re.compile(r"\bon the verge of\b", re.I), "瀕"),
    (re.compile(r"\bas a consequence of\b", re.I), "∴"),
    (re.compile(r"\bas a result of\b", re.I), "∴"),
    (re.compile(r"\bin the course of\b", re.I), "過程"),
    (re.compile(r"\bover the course of\b", re.I), "通"),
    (re.compile(r"\bin the face of\b", re.I), "面前"),
    (re.compile(r"\bby virtue of\b", re.I), "力"),
    (re.compile(r"\bby way of\b", re.I), "経"),
    (re.compile(r"\bby reason of\b", re.I), "因"),
    (re.compile(r"\bon account of\b", re.I), "因"),
    (re.compile(r"\bfor fear of\b", re.I), "恐"),
    (re.compile(r"\bfor lack of\b", re.I), "欠"),
    (re.compile(r"\bfor want of\b", re.I), "欠"),
    (re.compile(r"\bin exchange for\b", re.I), "⇔"),
    (re.compile(r"\bin return for\b", re.I), "⇔"),
    (re.compile(r"\bin regard to\b", re.I), "re:"),
    (re.compile(r"\bon top of\b", re.I), "且"),
    (re.compile(r"\bin excess of\b", re.I), "超"),
    (re.compile(r"\bin contrast to\b", re.I), "対比"),
    (re.compile(r"\bin contrast with\b", re.I), "対比"),
    (re.compile(r"\bby courtesy of\b", re.I), "経"),
    (re.compile(r"\bcourtesy of\b", re.I), "経"),
    (re.compile(r"\bfor the sake of\b", re.I), "為"),
    # cycle4 multiword prep (phrase-grammar: before article strip / for→4 / of→de)
    (re.compile(r"\bfor the purpose of\b", re.I), "目的"),
    (re.compile(r"\bfor purposes of\b", re.I), "目的"),
    (re.compile(r"\bfor the benefit of\b", re.I), "益"),
    (re.compile(r"\bin the interests? of\b", re.I), "利"),
    (re.compile(r"\bto the detriment of\b", re.I), "害"),
    (re.compile(r"\bin support of\b", re.I), "援"),
    (re.compile(r"\bin charge of\b", re.I), "責"),
    (re.compile(r"\bin control of\b", re.I), "制"),
    (re.compile(r"\bin search of\b", re.I), "求"),
    (re.compile(r"\bin need of\b", re.I), "要"),
    (re.compile(r"\bin hopes of\b", re.I), "希"),
    (re.compile(r"\bin hope of\b", re.I), "希"),
    (re.compile(r"\bin the wake of\b", re.I), "跡"),
    (re.compile(r"\bin the name of\b", re.I), "名"),
    (re.compile(r"\bat the hands of\b", re.I), "手"),
    (re.compile(r"\bat the mercy of\b", re.I), "弄"),
    (re.compile(r"\bin advance of\b", re.I), "先"),
    (re.compile(r"\bahead of time\b", re.I), "早"),
    (re.compile(r"\bahead of(?!\s+time\b)", re.I), "先"),
    (re.compile(r"\bin association with\b", re.I), "連携"),
    (re.compile(r"\bin comparison with\b", re.I), "比"),
    (re.compile(r"\bin comparison to\b", re.I), "比"),
    (re.compile(r"\bin common with\b", re.I), "共通"),
    (re.compile(r"\bsubject to\b", re.I), "条件"),
    (re.compile(r"\badjacent to\b", re.I), "隣"),
    (re.compile(r"\bin defiance of\b", re.I), "反"),
    (re.compile(r"\bby order of\b", re.I), "命"),
    (re.compile(r"\bunder cover of\b", re.I), "覆"),
    (re.compile(r"\bat odds with\b", re.I), "対立"),
    (re.compile(r"\bwith a view to\b", re.I), "狙"),
    (re.compile(r"\bwith an eye to\b", re.I), "狙"),
    (re.compile(r"\bon the basis of\b", re.I), "基"),
    (re.compile(r"\bin the presence of\b", re.I), "在"),
    (re.compile(r"\bat the price of\b", re.I), "代価"),
    (re.compile(r"\bunder the auspices of\b", re.I), "傘"),
    (re.compile(r"\bin parallel with\b", re.I), "∥"),
    (re.compile(r"\bin tandem with\b", re.I), "∥"),
    # cycle4 folds (aliases → existing terminals)
    (re.compile(r"\bby dint of\b", re.I), "力"),
    (re.compile(r"\bby force of\b", re.I), "力"),
    (re.compile(r"\bon the brink of\b", re.I), "瀕"),
    (re.compile(r"\bon the point of\b", re.I), "瀕"),
    (re.compile(r"\bwith the exception of\b", re.I), "除"),
    (re.compile(r"\bexclusive of\b", re.I), "除"),
    (re.compile(r"\bsave for\b", re.I), "除"),
    (re.compile(r"\binclusive of\b", re.I), "含"),
    (re.compile(r"\bshort of\b", re.I), "欠"),
    (re.compile(r"\bin default of\b", re.I), "欠"),
    (re.compile(r"\bthanks to\b", re.I), "因"),
    (re.compile(r"\bon the grounds of\b", re.I), "因"),
    (re.compile(r"\bon grounds of\b", re.I), "因"),
    (re.compile(r"\bat the cost of\b", re.I), "犠牲"),
    (re.compile(r"\bin the process of\b", re.I), "過程"),
    (re.compile(r"\bas per\b", re.I), "準"),
    (re.compile(r"\bin conjunction with\b", re.I), "共"),
    (re.compile(r"\bin connection with\b", re.I), "re:"),
    (re.compile(r"\brelative to\b", re.I), "re:"),
    (re.compile(r"\bin respect of\b", re.I), "re:"),
    (re.compile(r"\bas regards\b", re.I), "re:"),
    (re.compile(r"\bapropos of\b", re.I), "re:"),
    (re.compile(r"\bvis-à-vis\b", re.I), "vs"),
    (re.compile(r"\bvis-a-vis\b", re.I), "vs"),
    # cycle11 spaced deferred (as of / latin / loc-time)
    (re.compile(r"\bmutatis mutandis\b", re.I), "準変"),
    (re.compile(r"\bceteris paribus\b", re.I), "他同"),
    (re.compile(r"\bsui generis\b", re.I), "独自"),
    (re.compile(r"\bpari passu\b", re.I), "同率"),
    (re.compile(r"\bex officio\b", re.I), "職権"),
    (re.compile(r"\bprima facie\b", re.I), "一応"),
    (re.compile(r"\bipso facto\b", re.I), "当然"),
    (re.compile(r"\ba priori\b", re.I), "先験"),
    (re.compile(r"\bde facto\b", re.I), "d.f."),
    (re.compile(r"\bin situ\b", re.I), "現場"),
    (re.compile(r"\bad hoc\b", re.I), "adhoc"),
    (re.compile(r"\bone-on-one\b", re.I), "1:1"),
    (re.compile(r"\bone on one\b", re.I), "1:1"),
    (re.compile(r"\bunder age\b", re.I), "年少"),
    (re.compile(r"\bby and by\b", re.I), "稍後"),
    (re.compile(r"\bfor once\b", re.I), "一度"),
    (re.compile(r"\bof late\b", re.I), "近頃"),
    (re.compile(r"\bthus far\b", re.I), "今迄"),
    (re.compile(r"\bto date\b", re.I), "今迄"),
    (re.compile(r"\bas of\b(?! yet\b)", re.I), "起"),
    (re.compile(r"\bany time\b", re.I), "∀時"),
    (re.compile(r"\bfor good\b", re.I), "∞"),
    (re.compile(r"\bhitherto\b", re.I), "従来"),
    (re.compile(r"\bunderage\b", re.I), "年少"),
    (re.compile(r"\banywhere\b", re.I), "∃loc"),
    (re.compile(r"(?<!out of )\bnowhere\b", re.I), "∅loc"),
    (re.compile(r"\banytime\b", re.I), "∀時"),
    (re.compile(r"\bsomewhat\b", re.I), "稍"),
    (re.compile(r"\bsomehow\b", re.I), "或様"),
    (re.compile(r"\bclear of\b", re.I), "離"),
    (re.compile(r"\bfree of\b", re.I), "无"),
    (re.compile(r"\bfree from\b", re.I), "无"),
    (re.compile(r"\bdevoid of\b", re.I), "无"),
    (re.compile(r"\bin the absence of\b", re.I), "无"),
    (re.compile(r"\boutside of\b", re.I), "外"),
    (re.compile(r"\binside of\b", re.I), "内"),
    # cycle5 multiword prep + prep-like adv
    (re.compile(r"\bin response to\b", re.I), "応"),
    (re.compile(r"\bin reaction to\b", re.I), "応"),
    (re.compile(r"\bin reply to\b", re.I), "応"),
    (re.compile(r"\bin answer to\b", re.I), "答"),
    (re.compile(r"\bin line with\b", re.I), "沿"),
    (re.compile(r"\bin step with\b", re.I), "沿"),
    (re.compile(r"\bin agreement with\b", re.I), "合"),
    (re.compile(r"\bin keeping with\b", re.I), "合"),
    (re.compile(r"\bdepending upon\b", re.I), "依"),
    (re.compile(r"\bdepending on\b", re.I), "依"),
    (re.compile(r"\bas well as\b", re.I), "+"),
    (re.compile(r"\bto say nothing of\b", re.I), "況"),
    (re.compile(r"\bnot to mention\b", re.I), "況"),
    (re.compile(r"\blet alone\b", re.I), "況"),
    (re.compile(r"\bmuch less\b", re.I), "況"),
    (re.compile(r"\bstill less\b", re.I), "況"),
    (re.compile(r"\bconfronted with\b", re.I), "直面"),
    (re.compile(r"\bfaced with\b", re.I), "直面"),
    (re.compile(r"\bup against\b", re.I), "直面"),
    (re.compile(r"\bpertaining to\b", re.I), "関"),
    (re.compile(r"\brelating to\b", re.I), "関"),
    (re.compile(r"\bindependent of\b", re.I), "独立"),
    (re.compile(r"\bcomparable to\b", re.I), "≒"),
    (re.compile(r"\bsimilar to\b", re.I), "≒"),
    (re.compile(r"\bakin to\b", re.I), "≒"),
    (re.compile(r"\bequivalent to\b", re.I), "≡"),
    (re.compile(r"\bconfined to\b", re.I), "限"),
    (re.compile(r"\brestricted to\b", re.I), "限"),
    (re.compile(r"\blimited to\b", re.I), "限"),
    (re.compile(r"\battributable to\b", re.I), "帰"),
    (re.compile(r"\bascribable to\b", re.I), "帰"),
    (re.compile(r"\bfor the time being\b", re.I), "暫"),
    (re.compile(r"\bfor now\b", re.I), "暫"),
    (re.compile(r"\bright away\b", re.I), "即"),
    (re.compile(r"\bstraight away\b", re.I), "即"),
    (re.compile(r"\bat once\b", re.I), "即"),
    (re.compile(r"\ball of a sudden\b", re.I), "突"),
    (re.compile(r"\bfrom time to time\b", re.I), "偶"),
    (re.compile(r"\bonce in a while\b", re.I), "偶"),
    (re.compile(r"\bevery now and then\b", re.I), "偶"),
    (re.compile(r"\bevery so often\b", re.I), "偶"),
    (re.compile(r"\bnow and again\b", re.I), "偶"),
    (re.compile(r"\bnow and then\b", re.I), "偶"),
    (re.compile(r"\bby chance\b", re.I), "偶"),
    (re.compile(r"\bby accident\b", re.I), "偶"),
    (re.compile(r"\bat last\b", re.I), "遂"),
    (re.compile(r"\bat first\b", re.I), "初"),
    (re.compile(r"\bin brief\b", re.I), "略"),
    (re.compile(r"\bin short\b", re.I), "略"),
    (re.compile(r"\bin fact\b", re.I), "実"),
    (re.compile(r"\bin practice\b", re.I), "実際"),
    (re.compile(r"\bin theory\b", re.I), "理"),
    (re.compile(r"\bin general\b", re.I), "一般"),
    (re.compile(r"\bon purpose\b", re.I), "故意"),
    (re.compile(r"\bby design\b", re.I), "故意"),
    (re.compile(r"\bin vain\b", re.I), "徒"),
    (re.compile(r"\bat the moment\b", re.I), "今"),
    (re.compile(r"\bat present\b", re.I), "今"),
    (re.compile(r"\bunder way\b", re.I), "進行"),
    (re.compile(r"\bunderway\b", re.I), "進行"),
    # cycle5 folds
    (re.compile(r"\bin the meantime\b", re.I), "∥"),
    (re.compile(r"\bin the interim\b", re.I), "∥"),
    (re.compile(r"\bover and above\b", re.I), "超"),
    (re.compile(r"\babove and beyond\b", re.I), "超"),
    (re.compile(r"\bbased upon\b", re.I), "基"),
    (re.compile(r"\bbased on\b", re.I), "基"),
    (re.compile(r"\bexcept for\b", re.I), "除"),
    (re.compile(r"\bbut for\b", re.I), "除"),
    (re.compile(r"\bacross from\b", re.I), "対側"),
    (re.compile(r"\bnext door to\b", re.I), "隣"),
    (re.compile(r"\bin conflict with\b", re.I), "対立"),
    (re.compile(r"\bat variance with\b", re.I), "対立"),
    (re.compile(r"\bin compliance with\b", re.I), "準"),
    (re.compile(r"\bin conformity with\b", re.I), "準"),
    (re.compile(r"\bfrom now on\b", re.I), "∴→"),
    (re.compile(r"\bwith reference to\b", re.I), "re:"),
    (re.compile(r"\bin reference to\b", re.I), "re:"),
    (re.compile(r"\bin relation to\b", re.I), "re:"),
    (re.compile(r"\bwith relation to\b", re.I), "re:"),
    # cycle6 prep + prep-like adv / discourse
    (re.compile(r"\bcontrary to\b", re.I), "逆"),
    (re.compile(r"\bcounter to\b", re.I), "逆"),
    (re.compile(r"\bproportional to\b", re.I), "比例"),
    (re.compile(r"\bin pursuit of\b", re.I), "追"),
    (re.compile(r"\bwith regard to\b", re.I), "re:"),
    (re.compile(r"\bwith respect to\b", re.I), "re:"),
    (re.compile(r"\bafter all\b", re.I), "結局"),
    (re.compile(r"\babove all\b", re.I), "最"),
    (re.compile(r"\ball in all\b", re.I), "総"),
    (re.compile(r"\ball the same\b", re.I), "猶"),
    (re.compile(r"\bby and large\b", re.I), "概"),
    (re.compile(r"\bon the whole\b", re.I), "概"),
    (re.compile(r"\bby far\b", re.I), "遥"),
    (re.compile(r"\bfor sure\b", re.I), "確"),
    (re.compile(r"\bfor certain\b", re.I), "確"),
    (re.compile(r"\bin any case\b", re.I), "何れ"),
    (re.compile(r"\bin any event\b", re.I), "何れ"),
    (re.compile(r"\bat any rate\b", re.I), "何れ"),
    (re.compile(r"\bin the end\b", re.I), "最終"),
    (re.compile(r"\bin the long run\b", re.I), "長期"),
    (re.compile(r"\bon the contrary\b", re.I), "反対"),
    (re.compile(r"\bon the other hand\b", re.I), "他方"),
    (re.compile(r"\bto some extent\b", re.I), "或程"),
    (re.compile(r"\bto a certain extent\b", re.I), "或程"),
    (re.compile(r"\bas usual\b", re.I), "常"),
    (re.compile(r"\bas always\b", re.I), "常"),
    (re.compile(r"\blittle by little\b", re.I), "徐"),
    (re.compile(r"\bbit by bit\b", re.I), "徐"),
    (re.compile(r"\bstep by step\b", re.I), "逐"),
    (re.compile(r"\bone by one\b", re.I), "逐一"),
    (re.compile(r"\bside by side\b", re.I), "並列"),
    (re.compile(r"\bagain and again\b", re.I), "繰"),
    (re.compile(r"\bover and over again\b", re.I), "繰"),
    (re.compile(r"\bover and over\b", re.I), "繰"),
    (re.compile(r"\btime after time\b", re.I), "繰"),
    (re.compile(r"\bas a result\b", re.I), "結果"),
    (re.compile(r"\bin advance\b", re.I), "予"),
    (re.compile(r"\bby all means\b", re.I), "是非"),
    (re.compile(r"\bin essence\b", re.I), "本質"),
    (re.compile(r"\bin detail\b", re.I), "詳"),
    (re.compile(r"\bin retrospect\b", re.I), "回顧"),
    (re.compile(r"\bin hindsight\b", re.I), "回顧"),
    (re.compile(r"\bwithout fail\b", re.I), "必ず"),
    (re.compile(r"\bonce again\b", re.I), "再"),
    (re.compile(r"\bonce more\b", re.I), "再"),
    (re.compile(r"\bright now\b", re.I), "今"),
    # cycle7 spatial / state prep + prep-like adv
    (re.compile(r"\bnorth of\b", re.I), "北"),
    (re.compile(r"\bsouth of\b", re.I), "南"),
    (re.compile(r"\beast of\b", re.I), "東"),
    (re.compile(r"\bwest of\b", re.I), "西"),
    (re.compile(r"\bto the left of\b", re.I), "左"),
    (re.compile(r"\bto the right of\b", re.I), "右"),
    (re.compile(r"\bon the part of\b", re.I), "側"),
    (re.compile(r"\bin disregard of\b", re.I), "無視"),
    (re.compile(r"\bout of control\b", re.I), "暴走"),
    (re.compile(r"\bout of date\b", re.I), "廃"),
    (re.compile(r"\bout of order\b", re.I), "故障"),
    (re.compile(r"\bunder pressure\b", re.I), "圧"),
    (re.compile(r"\bunder control\b", re.I), "制御"),
    (re.compile(r"\bliable to\b", re.I), "負"),
    (re.compile(r"\bresistant to\b", re.I), "耐"),
    (re.compile(r"\bsensitive to\b", re.I), "敏"),
    (re.compile(r"\binferior to\b", re.I), "劣"),
    (re.compile(r"\bpreferable to\b", re.I), "優"),
    (re.compile(r"\bsuperior to\b", re.I), "優"),
    (re.compile(r"\bno longer\b", re.I), "最早"),
    (re.compile(r"\bany longer\b", re.I), "最早"),
    (re.compile(r"\bnot anymore\b", re.I), "最早"),
    (re.compile(r"\bas yet\b", re.I), "未"),
    (re.compile(r"\bon the one hand\b", re.I), "一方"),
    (re.compile(r"\bon one hand\b", re.I), "一方"),
    (re.compile(r"\bin the short run\b", re.I), "短期"),
    (re.compile(r"\bto a large extent\b", re.I), "大程"),
    (re.compile(r"\bshortly after\b", re.I), "直後"),
    (re.compile(r"\bsoon after\b", re.I), "直後"),
    (re.compile(r"\bshortly before\b", re.I), "直前"),
    (re.compile(r"\bday by day\b", re.I), "日々"),
    (re.compile(r"\byear by year\b", re.I), "年々"),
    (re.compile(r"\bface to face\b", re.I), "対面"),
    # cycle7 folds
    (re.compile(r"\bcontiguous to\b", re.I), "隣"),
    (re.compile(r"\bprevious to\b", re.I), "前"),
    (re.compile(r"\bnear to\b", re.I), "近"),
    (re.compile(r"\bas a matter of fact\b", re.I), "実"),
    # cycle8 prep + prep-like adv
    (re.compile(r"\bupstream of\b", re.I), "上流"),
    (re.compile(r"\bupstream from\b", re.I), "上流"),
    (re.compile(r"\bdownstream of\b", re.I), "下流"),
    (re.compile(r"\bdownstream from\b", re.I), "下流"),
    (re.compile(r"\bout of place\b", re.I), "不所"),
    (re.compile(r"\bout of reach\b", re.I), "届外"),
    (re.compile(r"\bout of nowhere\b", re.I), "突"),
    (re.compile(r"\bout of the blue\b", re.I), "突"),
    (re.compile(r"\bunder fire\b", re.I), "被弾"),
    (re.compile(r"\bunder review\b", re.I), "審査中"),
    (re.compile(r"\bimmune to\b", re.I), "免疫"),
    (re.compile(r"\bprone to\b", re.I), "傾向"),
    (re.compile(r"\bpreparatory to\b", re.I), "準備"),
    (re.compile(r"\bpreliminary to\b", re.I), "準備"),
    (re.compile(r"\bfurther to\b", re.I), "追伸"),
    (re.compile(r"\bin praise of\b", re.I), "賛"),
    (re.compile(r"\bsuch as\b", re.I), "如"),
    (re.compile(r"\bfor real\b", re.I), "真"),
    (re.compile(r"\bin turn\b", re.I), "順"),
    (re.compile(r"\bin full\b", re.I), "全"),
    (re.compile(r"\bin succession\b", re.I), "連続"),
    (re.compile(r"\bback to back\b", re.I), "連続"),
    (re.compile(r"\bhand in hand\b", re.I), "携"),
    (re.compile(r"\bhead to head\b", re.I), "直接"),
    (re.compile(r"\blong since\b", re.I), "久"),
    (re.compile(r"\bright then\b", re.I), "其時"),
    (re.compile(r"\bjust then\b", re.I), "其時"),
    (re.compile(r"\ben route\b", re.I), "途中"),
    (re.compile(r"\bby no means\b", re.I), "決して"),
    (re.compile(r"\bin no way\b", re.I), "決して"),
    (re.compile(r"\bwithout doubt\b", re.I), "疑無"),
    (re.compile(r"\bno doubt\b", re.I), "疑無"),
    (re.compile(r"\bin some way\b", re.I), "或様"),
    (re.compile(r"\bin many ways\b", re.I), "多様"),
    (re.compile(r"\bat all times\b", re.I), "常時"),
    (re.compile(r"\bat times\b", re.I), "時々"),
    (re.compile(r"\bat random\b", re.I), "乱"),
    (re.compile(r"\bexcluding\b", re.I), "除"),
    # cycle9 prep + prep-like adv
    (re.compile(r"\bfor the duration of\b", re.I), "期間"),
    (re.compile(r"\bonce and for all\b", re.I), "断"),
    (re.compile(r"\bso to speak\b", re.I), "言わば"),
    (re.compile(r"\bas it were\b", re.I), "言わば"),
    (re.compile(r"\bas such\b", re.I), "斯"),
    (re.compile(r"\bever since\b", re.I), "以来"),
    (re.compile(r"\bcharacteristic of\b", re.I), "特質"),
    (re.compile(r"\bindicative of\b", re.I), "示"),
    (re.compile(r"\bsuggestive of\b", re.I), "示唆"),
    (re.compile(r"\bcomposed of\b", re.I), "構成"),
    (re.compile(r"\bconsisting of\b", re.I), "構成"),
    (re.compile(r"\bcomprised of\b", re.I), "構成"),
    (re.compile(r"\btypical of\b", re.I), "典型"),
    (re.compile(r"\bcognizant of\b", re.I), "知"),
    (re.compile(r"\bcognisant of\b", re.I), "知"),
    (re.compile(r"\bmindful of\b", re.I), "念"),
    (re.compile(r"\bcapable of\b", re.I), "能"),
    (re.compile(r"\bincapable of\b", re.I), "不能"),
    (re.compile(r"\bworthy of\b", re.I), "値"),
    (re.compile(r"\bfond of\b", re.I), "好"),
    (re.compile(r"\bproud of\b", re.I), "誇"),
    (re.compile(r"\bfull of\b", re.I), "満"),
    (re.compile(r"\brid of\b", re.I), "撤"),
    (re.compile(r"\bbereft of\b", re.I), "欠"),
    (re.compile(r"\bafraid of\b", re.I), "恐"),
    (re.compile(r"\bscared of\b", re.I), "恐"),
    (re.compile(r"\babreast of\b", re.I), "並"),
    (re.compile(r"\bsimultaneously\b", re.I), "同時"),
    (re.compile(r"\bconcurrently\b", re.I), "同時"),
    (re.compile(r"\brespectively\b", re.I), "各"),
    (re.compile(r"\bsimilarly\b", re.I), "同様"),
    (re.compile(r"\blikewise\b", re.I), "同様"),
    (re.compile(r"\balternately\b", re.I), "交互"),
    (re.compile(r"\balternatively\b", re.I), "交互"),
    (re.compile(r"\bcurrently\b", re.I), "現"),
    (re.compile(r"\bpresently\b", re.I), "現"),
    (re.compile(r"\bformerly\b", re.I), "旧"),
    (re.compile(r"\bpreviously\b", re.I), "旧"),
    (re.compile(r"\bconversely\b", re.I), "逆"),
    (re.compile(r"\bthereupon\b", re.I), "其時"),
    (re.compile(r"\bwhereupon\b", re.I), "其時"),
    (re.compile(r"\boffshore\b", re.I), "沖"),
    # cycle10 prep + prep-like adv (final of ~10)
    (re.compile(r"\bmore often than not\b", re.I), "大抵"),
    (re.compile(r"\bthrough and through\b", re.I), "徹底"),
    (re.compile(r"\bout of stock\b", re.I), "品切"),
    (re.compile(r"\bat first glance\b", re.I), "一見"),
    (re.compile(r"\bat first sight\b", re.I), "一見"),
    (re.compile(r"\bat a glance\b", re.I), "一見"),
    (re.compile(r"\bat stake\b", re.I), "賭"),
    (re.compile(r"\bat length\b", re.I), "遂"),
    (re.compile(r"\bfor keeps\b", re.I), "永久"),
    (re.compile(r"\bfor the most part\b", re.I), "概"),
    (re.compile(r"\bfirst and foremost\b", re.I), "最"),
    (re.compile(r"\bin a nutshell\b", re.I), "略"),
    (re.compile(r"\bin a row\b", re.I), "連続"),
    (re.compile(r"\bin earnest\b", re.I), "本気"),
    (re.compile(r"\bin effect\b", re.I), "実質"),
    (re.compile(r"\bin the main\b", re.I), "概"),
    (re.compile(r"\bas a whole\b", re.I), "総"),
    (re.compile(r"\bas a rule\b", re.I), "概"),
    (re.compile(r"\bas of yet\b", re.I), "未"),
    (re.compile(r"\boff and on\b", re.I), "断続"),
    (re.compile(r"\bon and off\b", re.I), "断続"),
    (re.compile(r"\ball along\b", re.I), "当初"),
    (re.compile(r"\bforever after\b", re.I), "以後"),
    (re.compile(r"\bever after\b", re.I), "以後"),
    (re.compile(r"\ben masse\b", re.I), "一斉"),
    (re.compile(r"\bad infinitum\b", re.I), "∞"),
    (re.compile(r"\binside out\b", re.I), "裏返"),
    (re.compile(r"\bupside down\b", re.I), "逆さ"),
    (re.compile(r"\bweary of\b", re.I), "厭"),
    (re.compile(r"\bashamed of\b", re.I), "恥"),
    (re.compile(r"\bjealous of\b", re.I), "嫉"),
    (re.compile(r"\benvious of\b", re.I), "嫉"),
    (re.compile(r"\bempty of\b", re.I), "空"),
    (re.compile(r"\bmade of\b", re.I), "製"),
    (re.compile(r"\bmade from\b", re.I), "製"),
    (re.compile(r"\bcounterclockwise\b", re.I), "反時計"),
    (re.compile(r"\banticlockwise\b", re.I), "反時計"),
    (re.compile(r"\bclockwise\b", re.I), "時計"),
    (re.compile(r"\bnationwide\b", re.I), "全国"),
    (re.compile(r"\bworldwide\b", re.I), "世界"),
    (re.compile(r"\bglobally\b", re.I), "世界"),
    (re.compile(r"\bunderwater\b", re.I), "水中"),
    (re.compile(r"\boverboard\b", re.I), "船外"),
    (re.compile(r"\bashore\b", re.I), "岸"),
    (re.compile(r"\bbackwards\b", re.I), "後方"),
    (re.compile(r"\bbackward\b", re.I), "後方"),
    (re.compile(r"\bsideways\b", re.I), "横"),
    (re.compile(r"\bafterward\b", re.I), "後"),
    (re.compile(r"\bconsidering\b", re.I), "鑑"),
    (re.compile(r"\bvis-a-vis\b", re.I), "vs"),
    (re.compile(r"\badditionally\b", re.I), "+"),
    (re.compile(r"\balso\b", re.I), "+"),
    (re.compile(r"\bespecially\b", re.I), "esp."),
    (re.compile(r"\bthat is\b", re.I), "i.e."),
    (re.compile(r"\bversus\b", re.I), "vs"),
    # Formal/legal phrases before for→4 / that-deixis / and→& eat a piece.
    (re.compile(r"\bprovided, however, that\b", re.I), "if"),
    (re.compile(r"\bprovided that\b", re.I), "if"),
    (re.compile(r"\bin the event that\b", re.I), "if"),
    (re.compile(r"\bto the extent that\b", re.I), "insofar"),
    (re.compile(r"\bin so far as\b", re.I), "insofar"),
    (re.compile(r"\binsofar as\b", re.I), "insofar"),
    # pursuant to / in accordance with → 準, in lieu of → 代,
    # as opposed to / rather than → vs are prep cycle2 (_SUBS)
    (re.compile(r"\bgiven that\b", re.I), "bc"),
    (re.compile(r"\binasmuch as\b", re.I), "bc"),
    (re.compile(r"\beven though\b", re.I), "tho"),
    (re.compile(r"\bnow therefore\b", re.I), "∴"),
    (re.compile(r"\bfor this reason\b", re.I), "∴"),
    (re.compile(r"\bas a consequence\b", re.I), "∴"),
    (re.compile(r"\bnull and void\b", re.I), "void"),
    (re.compile(r"\bterms and conditions\b", re.I), "T&C"),
    (re.compile(r"\band others\b", re.I), "etal"),
    # Consume the optional period; \b after "." never matches.
    (re.compile(r"\bet al\.?(?!\w)", re.I), "etal"),
    (re.compile(r"\bthe foregoing\b", re.I), "supra"),
    (re.compile(r"\bvice versa\b", re.I), "⇄"),
    # compare / equality — language-agnostic → ≧/≦/= /≒ (BEFORE and/or/at/_SUBS)
    (re.compile(r"\bapproximately equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\babout equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\broughly equal(?: to)?\b", re.I), "≒"),
    (re.compile(r"\bequal to\b", re.I), "="),
    (re.compile(r"\bat least\b", re.I), "≧"),
    (re.compile(r"\bat most\b", re.I), "≦"),
    (re.compile(r"\bor more\b", re.I), "≧"),
    (re.compile(r"\bmore or less\b", re.I), "殆"),
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
    # --- objective gap-fill: thin closed-class (det/quant/conj/reciprocal/hedge/aux) ---
    # Protect noun "a while" before while→∥; multiword before article strip / bare dets.
    (re.compile(r"\ba while\b", re.I), "awhile"),
    (re.compile(r"\beach other\b", re.I), "互"),
    (re.compile(r"\bone another\b", re.I), "互"),
    (re.compile(r"\ba lot of\b", re.I), "多"),
    (re.compile(r"\blots of\b", re.I), "多"),
    (re.compile(r"\ba few\b", re.I), "few"),
    (re.compile(r"\ba little\b", re.I), "少"),
    (re.compile(r"\bin order to\b", re.I), "to"),
    (re.compile(r"\bso that\b", re.I), "so"),
    (re.compile(r"\bwant to\b", re.I), "wanna"),
    (re.compile(r"\bkind of\b", re.I), "kinda"),
    (re.compile(r"\bsort of\b", re.I), "sorta"),
    (re.compile(r"\bunless\b", re.I), "!if"),
    (re.compile(r"\bwhether\b", re.I), "if"),
    (re.compile(r"(?<!\bonce in a )(?<!\ba )\bwhilst\b", re.I), "∥"),
    (re.compile(r"(?<!\bonce in a )(?<!\ba )\bwhile\b", re.I), "∥"),
    (re.compile(r"\bmaybe\b", re.I), "或"),
    (re.compile(r"\bperhaps\b", re.I), "或"),
    (re.compile(r"\bprobably\b", re.I), "恐"),
    (re.compile(r"\busually\b", re.I), "常"),
    (re.compile(r"\balready\b", re.I), "既"),
    (re.compile(r"\bonly\b", re.I), "僅"),
    (re.compile(r"\bstill\b", re.I), "尚"),
    # gap-fill bare dets/quants (AFTER multiword some/every/each phrases)
    (re.compile(r"\bevery\b(?!where\b|one\b|body\b|day\b|time\b|thing\b)", re.I), "∀"),
    (re.compile(r"\beach\b(?!\s+other\b)", re.I), "各"),
    (re.compile(r"\bsome\b(?!where\b|how\b|what\b|one\b|body\b|times?\b|thing\b|day\b|extent\b|ways?\b)", re.I), "∃"),
    (re.compile(r"\bnone\b", re.I), "∅"),
    (re.compile(r"\bboth\b", re.I), "両"),
    (re.compile(r"\bseveral\b", re.I), "数"),
    (re.compile(r"\bvarious\b", re.I), "諸"),
    (re.compile(r"\bnumerous\b", re.I), "多"),
    # --- relative pronouns / 関係代名詞 (after that is→i.e.; not deixis/interrogative) ---
    # EN: which→that (post-nominal / non-restrictive); whom→who. Prefer EN-internal that over que.
    # Do NOT emit bare q. Keep deixis that→eso gate; complementizer that untouched.
    (re.compile(r",\s*which\b", re.I), ", that"),
    (re.compile(
        r"\b(?!(?:in|of|for|to|with|on|at|by|from|about|into|onto|upon|through|"
        r"under|over|during|as|after|before|since|until|than|and|or|but|if|"
        r"when|while|where|who|whom|whose|that|this|these|those)\b)"
        r"([A-Za-z][A-Za-z0-9\-]*)\s+which\b"
        r"(?=\s+(?:is|are|was|were|has|have|had|will|would|can|could|may|might|"
        r"must|shall|should|do|does|did|I|he|she|it|we|they|you|U|my|his|her|"
        r"its|our|their|not)\b)",
        re.I,
    ), r"\1 that"),
    (re.compile(r"\bWhom\b"), "Who"),
    (re.compile(r"\bwhom\b"), "who"),
    # Romance/DE long relatives → que (shared pivot; dual-metric win)
    (re.compile(r"\blesquelles\b", re.I), "que"),
    (re.compile(r"\blesquels\b", re.I), "que"),
    (re.compile(r"\blaquelle\b", re.I), "que"),
    (re.compile(r"\blequel\b", re.I), "que"),
    # DE welcher*: post-nominal relative only (bare Welche? = interrogative)
    (re.compile(
        r"\b([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\-]*)\s+welch(?:er|e|es)\b"
        r"(?=\s+(?:ist|sind|war|waren|hat|haben|hatte|hatten|wird|werden|"
        r"kann|können|muss|müssen|soll|sollen|darf|dürfen|will|wollen|"
        r"ich|du|er|sie|es|wir|ihr|Sie|mein|dein|sein|unser|euer|ihr)\b)",
        re.I,
    ), r"\1 que"),
    (re.compile(r"\blos que\b", re.I), "que"),
    (re.compile(r"\blas que\b", re.I), "que"),
    (re.compile(r"\bel que\b", re.I), "que"),
    (re.compile(r"\bla que\b", re.I), "que"),
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



# --- EN 3sg → base after marked singular subjects -----------------------------
# Once subject is a marked 3sg / singular pronoun (inventory + generic one /
# everyone…; deixis ça/eso; legacy 彼/她), English 3sg -s is redundant → base.
# you→U does not take 3sg. Irregulars: has/does/goes.
# Skip one closed adverb/polarity between subject and verb (grammar avoidance).
# Exclude: 単複同形 / irregular-plural -s nouns / non-verb -s (was, news…).
_IRREG_3SG_BASE: dict[str, str] = {
    "has": "have",
    "does": "do",
    "goes": "go",
}
# Surfaces ending in -s that are NOT EN 3sg verbs (keep unchanged).
# Policy: skip 単複同形 and non +s/+es plurals; also past was, possessives, adverbs.
_NON_3SG_S: frozenset[str] = frozenset(
    {
        # past be (not present 3sg -s)
        "was",
        # 単複同形 / mass / pluralia tantum in -s
        "news",
        "series",
        "species",
        "means",  # noun invariant; verb "he means" traded off per 単複同形
        "physics",
        "mathematics",
        "economics",
        "politics",
        "ethics",
        "athletics",
        "linguistics",
        "acoustics",
        "logistics",
        "statistics",
        "tactics",
        "measles",
        "mumps",
        "diabetes",
        "billiards",
        "scissors",
        "trousers",
        "pants",
        "clothes",
        "goods",
        "glasses",
        "binoculars",
        "headphones",
        "belongings",
        "surroundings",
        "earnings",
        "savings",
        "riches",
        "archives",
        "remains",
        "odds",
        "premises",
        "headquarters",
        "crossroads",
        "barracks",
        "gallows",
        "bellows",
        "congratulations",
        "thanks",
        "regards",
        # adverbs / discourse ending in -s (not verbs)
        "sometimes",
        "onwards",
        "outwards",
        "inwards",
        "downwards",
        "upwards",
        "yes",
        "plus",
        "minus",
        # possessives / pronouns ending in -s (never 3sg verbs here)
        "his",
        "its",
        "hers",
        "ours",
        "yours",
        "theirs",
        # short -s nouns that are not 3sg verbs after these subjects
        "bus",
        "gas",
        "chaos",
        "atlas",
        "canvas",
        "virus",
        "census",
    }
)
# Optional single adverb / polarity between subject and verb (singular-limited path).
_3SG_SKIP_ADV = (
    r"(?:always|never|often|sometimes|also|still|just|really|actually|even|"
    r"already|usually|probably|perhaps|maybe|soon|now|then|here|there|"
    r"□|˅|oft|¬|esp\.)\s+"
)
# Marked singular subjects: inventory he/she/it, generic one/someone/…,
# deixis ça/eso (after this/that fold), legacy 彼/她.
_3SG_SUBJECT = (
    r"[Hh]e|[Ss]he|[Ii]t|[Oo]ne|"
    r"[Ss]omeone|[Ss]omebody|[Ee]veryone|[Ee]verybody|"
    r"彼|她|ça|Ça|eso|Eso"
)
_AFTER_INV_PRON_VERB = re.compile(
    rf"\b({_3SG_SUBJECT})\s+(?:{_3SG_SKIP_ADV})?([A-Za-z]+)\b"
)


def _en_verb_base_from_3sg(verb: str) -> str:
    """Map EN 3sg surface to base/prototype; leave non-3sg unchanged."""
    low = verb.lower()
    if low in _NON_3SG_S:
        return verb
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
        return verb[:-1]
    return verb


def drop_3sg_after_inventory_pronoun(text: str) -> str:
    """After marked singular subjects, fold EN 3sg -s to base verb (原型).

    ``he chooses`` → ``he choose``; ``it works`` → ``it work``;
    ``everyone always wants`` → ``everyone always want``.
    Possessives / 単複同形 -s nouns / ``was`` are not stripped.
    """

    def _sub(m: re.Match[str]) -> str:
        subj, verb = m.group(1), m.group(2)
        # Re-attach any skipped adverb that the match consumed via full span.
        full = m.group(0)
        # full is "SUBJ [adv ]VERB"; rebuild with base verb, keep mid as-is.
        mid_end = full.rfind(verb)
        mid = full[len(subj) : mid_end]  # includes spaces + optional adv
        return f"{subj}{mid}{_en_verb_base_from_3sg(verb)}"

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
    (re.compile(r"∴to"), "thereto"),
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
    (re.compile(r"\bpro\b", re.I), "in favor of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])代表(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on behalf of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])手段(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by means of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])観点(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in terms of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])準(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in accordance with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])至(?![\w\u3040-\u30ff\u3400-\u9fff])"), "down to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])出(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out from"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])鑑(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in light of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])為(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for the sake of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])場合(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in case of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])不問(?![\w\u3040-\u30ff\u3400-\u9fff])"), "regardless of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])過(?![\w\u3040-\u30ff\u3400-\u9fff])"), "past"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])次(?![\w\u3040-\u30ff\u3400-\u9fff])"), "following"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])未決(?![\w\u3040-\u30ff\u3400-\u9fff])"), "pending"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])力(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by virtue of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])経(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by way of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])恐(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for fear of"),
    (re.compile(r"⇔"), "in exchange for"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])且(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on top of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])犠牲(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at the expense of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])危(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at the risk of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])最中(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the middle of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])瀕(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on the verge of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])欠(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for lack of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])超(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in excess of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])対比(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in contrast to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])過程(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the course of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])面前(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the face of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])目的(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for the purpose of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])益(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for the benefit of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])利(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the interest of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])害(?![\w\u3040-\u30ff\u3400-\u9fff])"), "to the detriment of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])援(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in support of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])責(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in charge of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])制(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in control of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])求(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in search of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])要(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in need of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])希(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in hope of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])跡(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the wake of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])名(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the name of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])手(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at the hands of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])弄(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at the mercy of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])連携(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in association with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])比(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in comparison with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])共通(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in common with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])条件(?![\w\u3040-\u30ff\u3400-\u9fff])"), "subject to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])隣(?![\w\u3040-\u30ff\u3400-\u9fff])"), "adjacent to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])反(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in defiance of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])命(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by order of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])覆(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under cover of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])対立(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at odds with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])狙(?![\w\u3040-\u30ff\u3400-\u9fff])"), "with a view to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])基(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on the basis of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])在(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the presence of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])代価(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at the price of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])傘(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under the auspices of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])応(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in response to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])答(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in answer to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])合(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in agreement with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])況(?![\w\u3040-\u30ff\u3400-\u9fff])"), "let alone"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])直面(?![\w\u3040-\u30ff\u3400-\u9fff])"), "faced with"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])関(?![\w\u3040-\u30ff\u3400-\u9fff])"), "pertaining to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])独立(?![\w\u3040-\u30ff\u3400-\u9fff])"), "independent of"),
    (re.compile(r"≡"), "equivalent to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])限(?![\w\u3040-\u30ff\u3400-\u9fff])"), "limited to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])帰(?![\w\u3040-\u30ff\u3400-\u9fff])"), "attributable to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])暫(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for the time being"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])即(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at once"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])突(?![\w\u3040-\u30ff\u3400-\u9fff])"), "all of a sudden"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])偶(?![\w\u3040-\u30ff\u3400-\u9fff])"), "from time to time"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])遂(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at last"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])初(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at first"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])略(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in short"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])実際(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in practice"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])実(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in fact"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])理(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in theory"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一般(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in general"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])故意(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on purpose"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])徒(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in vain"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])今(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at present"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])早(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ahead of time"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])進行(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under way"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])反対(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on the contrary"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])逆(?![\w\u3040-\u30ff\u3400-\u9fff])"), "contrary to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])比例(?![\w\u3040-\u30ff\u3400-\u9fff])"), "proportional to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])追(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in pursuit of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])結局(?![\w\u3040-\u30ff\u3400-\u9fff])"), "after all"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])最(?![\w\u3040-\u30ff\u3400-\u9fff])"), "above all"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])総(?![\w\u3040-\u30ff\u3400-\u9fff])"), "all in all"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])猶(?![\w\u3040-\u30ff\u3400-\u9fff])"), "all the same"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])概(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by and large"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])遥(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by far"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])確(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for sure"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])何れ(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in any case"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])最終(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the end"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])長期(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the long run"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])他方(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on the other hand"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])或程(?![\w\u3040-\u30ff\u3400-\u9fff])"), "to some extent"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])常(?![\w\u3040-\u30ff\u3400-\u9fff])"), "as usual"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])殆(?![\w\u3040-\u30ff\u3400-\u9fff])"), "more or less"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])徐(?![\w\u3040-\u30ff\u3400-\u9fff])"), "little by little"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])逐一(?![\w\u3040-\u30ff\u3400-\u9fff])"), "one by one"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])逐(?![\w\u3040-\u30ff\u3400-\u9fff])"), "step by step"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])並列(?![\w\u3040-\u30ff\u3400-\u9fff])"), "side by side"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])繰(?![\w\u3040-\u30ff\u3400-\u9fff])"), "again and again"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])結果(?![\w\u3040-\u30ff\u3400-\u9fff])"), "as a result"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])予(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in advance"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])是非(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by all means"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])本質(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in essence"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])詳(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in detail"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])回顧(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in retrospect"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])必ず(?![\w\u3040-\u30ff\u3400-\u9fff])"), "without fail"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])北(?![\w\u3040-\u30ff\u3400-\u9fff])"), "north of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])南(?![\w\u3040-\u30ff\u3400-\u9fff])"), "south of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])東(?![\w\u3040-\u30ff\u3400-\u9fff])"), "east of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])西(?![\w\u3040-\u30ff\u3400-\u9fff])"), "west of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])左(?![\w\u3040-\u30ff\u3400-\u9fff])"), "to the left of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])右(?![\w\u3040-\u30ff\u3400-\u9fff])"), "to the right of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])側(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on the part of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])無視(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in disregard of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])暴走(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of control"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])廃(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of date"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])故障(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of order"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])圧(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under pressure"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])制御(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under control"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])負(?![\w\u3040-\u30ff\u3400-\u9fff])"), "liable to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])耐(?![\w\u3040-\u30ff\u3400-\u9fff])"), "resistant to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])敏(?![\w\u3040-\u30ff\u3400-\u9fff])"), "sensitive to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])劣(?![\w\u3040-\u30ff\u3400-\u9fff])"), "inferior to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])優(?![\w\u3040-\u30ff\u3400-\u9fff])"), "superior to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])最早(?![\w\u3040-\u30ff\u3400-\u9fff])"), "no longer"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])未(?![\w\u3040-\u30ff\u3400-\u9fff])"), "as yet"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一方(?![\w\u3040-\u30ff\u3400-\u9fff])"), "on one hand"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])短期(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in the short run"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])大程(?![\w\u3040-\u30ff\u3400-\u9fff])"), "to a large extent"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])直後(?![\w\u3040-\u30ff\u3400-\u9fff])"), "shortly after"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])直前(?![\w\u3040-\u30ff\u3400-\u9fff])"), "shortly before"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])日々(?![\w\u3040-\u30ff\u3400-\u9fff])"), "day by day"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])年々(?![\w\u3040-\u30ff\u3400-\u9fff])"), "year by year"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])対面(?![\w\u3040-\u30ff\u3400-\u9fff])"), "face to face"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])上流(?![\w\u3040-\u30ff\u3400-\u9fff])"), "upstream of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])下流(?![\w\u3040-\u30ff\u3400-\u9fff])"), "downstream of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])不所(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of place"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])届外(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of reach"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])被弾(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under fire"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])審査中(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under review"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])免疫(?![\w\u3040-\u30ff\u3400-\u9fff])"), "immune to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])傾向(?![\w\u3040-\u30ff\u3400-\u9fff])"), "prone to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])準備(?![\w\u3040-\u30ff\u3400-\u9fff])"), "preparatory to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])追伸(?![\w\u3040-\u30ff\u3400-\u9fff])"), "further to"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])賛(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in praise of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])如(?![\w\u3040-\u30ff\u3400-\u9fff])"), "such as"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])真(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for real"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])順(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in turn"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])全(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in full"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])連続(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in succession"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])携(?![\w\u3040-\u30ff\u3400-\u9fff])"), "hand in hand"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])直接(?![\w\u3040-\u30ff\u3400-\u9fff])"), "head to head"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])久(?![\w\u3040-\u30ff\u3400-\u9fff])"), "long since"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])其時(?![\w\u3040-\u30ff\u3400-\u9fff])"), "right then"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])途中(?![\w\u3040-\u30ff\u3400-\u9fff])"), "en route"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])決して(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by no means"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])疑無(?![\w\u3040-\u30ff\u3400-\u9fff])"), "no doubt"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])或様(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in some way"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])多様(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in many ways"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])時々(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at times"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])常時(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at all times"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])乱(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at random"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])並(?![\w\u3040-\u30ff\u3400-\u9fff])"), "abreast of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])知(?![\w\u3040-\u30ff\u3400-\u9fff])"), "cognizant of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])念(?![\w\u3040-\u30ff\u3400-\u9fff])"), "mindful of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])好(?![\w\u3040-\u30ff\u3400-\u9fff])"), "fond of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])誇(?![\w\u3040-\u30ff\u3400-\u9fff])"), "proud of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])能(?![\w\u3040-\u30ff\u3400-\u9fff])"), "capable of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])不能(?![\w\u3040-\u30ff\u3400-\u9fff])"), "incapable of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])値(?![\w\u3040-\u30ff\u3400-\u9fff])"), "worthy of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])典型(?![\w\u3040-\u30ff\u3400-\u9fff])"), "typical of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])示(?![\w\u3040-\u30ff\u3400-\u9fff])"), "indicative of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])示唆(?![\w\u3040-\u30ff\u3400-\u9fff])"), "suggestive of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])特質(?![\w\u3040-\u30ff\u3400-\u9fff])"), "characteristic of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])撤(?![\w\u3040-\u30ff\u3400-\u9fff])"), "rid of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])満(?![\w\u3040-\u30ff\u3400-\u9fff])"), "full of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])構成(?![\w\u3040-\u30ff\u3400-\u9fff])"), "composed of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])期間(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for the duration of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])沖(?![\w\u3040-\u30ff\u3400-\u9fff])"), "offshore"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])同時(?![\w\u3040-\u30ff\u3400-\u9fff])"), "simultaneously"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])各(?![\w\u3040-\u30ff\u3400-\u9fff])"), "respectively"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])同様(?![\w\u3040-\u30ff\u3400-\u9fff])"), "similarly"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])特(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in particular"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])言わば(?![\w\u3040-\u30ff\u3400-\u9fff])"), "so to speak"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])斯(?![\w\u3040-\u30ff\u3400-\u9fff])"), "as such"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])断(?![\w\u3040-\u30ff\u3400-\u9fff])"), "once and for all"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])現(?![\w\u3040-\u30ff\u3400-\u9fff])"), "currently"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])旧(?![\w\u3040-\u30ff\u3400-\u9fff])"), "formerly"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])交互(?![\w\u3040-\u30ff\u3400-\u9fff])"), "alternately"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])以来(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ever since"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])厭(?![\w\u3040-\u30ff\u3400-\u9fff])"), "weary of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])恥(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ashamed of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])嫉(?![\w\u3040-\u30ff\u3400-\u9fff])"), "jealous of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])空(?![\w\u3040-\u30ff\u3400-\u9fff])"), "empty of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])製(?![\w\u3040-\u30ff\u3400-\u9fff])"), "made of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])岸(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ashore"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])船外(?![\w\u3040-\u30ff\u3400-\u9fff])"), "overboard"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])水中(?![\w\u3040-\u30ff\u3400-\u9fff])"), "underwater"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])全国(?![\w\u3040-\u30ff\u3400-\u9fff])"), "nationwide"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])世界(?![\w\u3040-\u30ff\u3400-\u9fff])"), "worldwide"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])時計(?![\w\u3040-\u30ff\u3400-\u9fff])"), "clockwise"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])反時計(?![\w\u3040-\u30ff\u3400-\u9fff])"), "counterclockwise"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])裏返(?![\w\u3040-\u30ff\u3400-\u9fff])"), "inside out"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])逆さ(?![\w\u3040-\u30ff\u3400-\u9fff])"), "upside down"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])後方(?![\w\u3040-\u30ff\u3400-\u9fff])"), "backwards"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])横(?![\w\u3040-\u30ff\u3400-\u9fff])"), "sideways"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一斉(?![\w\u3040-\u30ff\u3400-\u9fff])"), "en masse"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])当初(?![\w\u3040-\u30ff\u3400-\u9fff])"), "all along"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])以後(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ever after"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])永久(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for keeps"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])断続(?![\w\u3040-\u30ff\u3400-\u9fff])"), "off and on"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])徹底(?![\w\u3040-\u30ff\u3400-\u9fff])"), "through and through"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])大抵(?![\w\u3040-\u30ff\u3400-\u9fff])"), "more often than not"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一見(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at a glance"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])賭(?![\w\u3040-\u30ff\u3400-\u9fff])"), "at stake"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])本気(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in earnest"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])実質(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in effect"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])品切(?![\w\u3040-\u30ff\u3400-\u9fff])"), "out of stock"),
    # cycle11
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])起(?![\w\u3040-\u30ff\u3400-\u9fff])"), "as of"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一度(?![\w\u3040-\u30ff\u3400-\u9fff])"), "for once"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])近頃(?![\w\u3040-\u30ff\u3400-\u9fff])"), "of late"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])従来(?![\w\u3040-\u30ff\u3400-\u9fff])"), "hitherto"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])今迄(?![\w\u3040-\u30ff\u3400-\u9fff])"), "thus far"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])年少(?![\w\u3040-\u30ff\u3400-\u9fff])"), "under age"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])稍後(?![\w\u3040-\u30ff\u3400-\u9fff])"), "by and by"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])∃loc(?![\w\u3040-\u30ff\u3400-\u9fff])"), "anywhere"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])∅loc(?![\w\u3040-\u30ff\u3400-\u9fff])"), "nowhere"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])∀時(?![\w\u3040-\u30ff\u3400-\u9fff])"), "anytime"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])稍(?![\w\u3040-\u30ff\u3400-\u9fff])"), "somewhat"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])準変(?![\w\u3040-\u30ff\u3400-\u9fff])"), "mutatis mutandis"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])他同(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ceteris paribus"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])独自(?![\w\u3040-\u30ff\u3400-\u9fff])"), "sui generis"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])同率(?![\w\u3040-\u30ff\u3400-\u9fff])"), "pari passu"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])職権(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ex officio"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])一応(?![\w\u3040-\u30ff\u3400-\u9fff])"), "prima facie"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])当然(?![\w\u3040-\u30ff\u3400-\u9fff])"), "ipso facto"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])先験(?![\w\u3040-\u30ff\u3400-\u9fff])"), "a priori"),
    (re.compile(r"(?<![\w\u3040-\u30ff\u3400-\u9fff])現場(?![\w\u3040-\u30ff\u3400-\u9fff])"), "in situ"),
    (re.compile(r"(?<![\w:])1:1(?![\w:])"), "one-on-one"),
    (re.compile(r"(?<![\w])d\.f\.(?![\w])", re.I), "de facto"),
    (re.compile(r"(?<![\w])adhoc(?![\w])", re.I), "ad hoc"),
    (re.compile(r"∈there"), "therein"),  # legacy; compress now emits ∈it
    (re.compile(r"∈it"), "therein"),
    (re.compile(r"⇄"), "vice versa"),
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
