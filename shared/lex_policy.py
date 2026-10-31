"""Lexeme policy: fillers, unique-reading preference, light etymon alignment.

Layer ownership (TalkCompress):
- **C ShorthandEdge**: ``strip_fillers``, ``UNIQUE_COMPACT`` (via ``apply_unique_readings(..., compact=True)``
  or ``apply_unique_compact``), same-language EN contractions (``I will``→``I'll``),
  spelled EN number words → digits. Also slang / hereafter / packs.
- **E MorphoZip**: ``UNIQUE_READINGS`` long form only (``compact=False``), ``ETYMON_ALIGN`` (comm/cfg/doc…;
  information→ℹ️ is **C** ``family=emoji`` with ML→pivot→emoji), first-person / counters / articles / grammar-min.
  Does **not** strip fillers, apply UNIQUE_COMPACT, contract ``I'll``, or digitize spelled numbers by default.
- Helpers live here so both layers can import them; callers choose which passes to run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Also support direct CLI execution with shared/ on sys.path.
if __package__:
    from .romance_gate import apply_outside_romance
    from .unicode_boundary import mark_pattern
else:
    from romance_gate import apply_outside_romance
    from unicode_boundary import mark_pattern

# Preserve the existing kana/CJK and symbol substring policy.
_LATIN_EDGE_CH = r"[^\W\u3040-\u30ff\u3400-\u9fff]"


def nonascii_word_pattern(src: str) -> str:
    """Bound letter-like edges by words and all Unicode mark categories."""
    pat = re.escape(src)
    if re.match(_LATIN_EDGE_CH, src):
        pat = rf"(?<!{_LATIN_EDGE_CH})(?<!{mark_pattern()}){pat}"
    if re.search(rf"{_LATIN_EDGE_CH}$", src):
        pat = rf"{pat}(?!{_LATIN_EDGE_CH}|{mark_pattern()})"
    return pat


def _ascii_ci(word: str) -> str:
    """Escape *word*; for ASCII words keep IGNORECASE ASCII-only (ı/İ/ſ/K ≠ i/s/k)."""
    return f"(?a:{re.escape(word)})" if word.isascii() else re.escape(word)


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
    "like",  # discourse "like"; may over-strip — MorphoZip notes
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "basically",
    "actually",
    "literally",
    "just",
    # expanded discourse grease
    "you see",
    "i guess",
    "i suppose",
    "right",
    "anyway",
    "anyhow",
    "so yeah",
    "yeah so",
    "to be fair",
    "at the end of the day",
    "needless to say",
    "as it were",
    "per se",
    "hmm",
    "huh",
    "mmm",
    "y'know",
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
    # expanded
    "うーん",
    "うんと",
    "なんかこう",
    "要するに",
    "いわゆる",
    "どっちかっていうと",
    "どちらかというと",
    "ぶっちゃけ",
    "てか",
    "っていうか",
    "なんかその",
)

# Rank-1 / unique-reading: prefer jargon / specialized verbs (fewer senses).
UNIQUE_READINGS: dict[str, str] = {
    # get: removed (o200k: get 1tok/4B; obtain 1/7, obt 1/4 = loser/tie).
    # get+adj/pp (get tired), get+ppl (get going) also keep get (become = 2tok/13B).
    "make": "construct",
    "do": "perform",
    "put": "place",
    "take": "acquire",
    "give": "provide",
    "look at": "see",  # o200k: look at 2/8, inspect 1/8, insp 1/5, 👀 2/5, see 1/4
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
    # tech / procedural expansions
    "write down": "record",
    "run through": "traverse",
    "break down": "decompose",
    "build out": "implement",
    "roll out": "deploy",
    "spin up": "instantiate",
    "tear down": "decommission",
    "look into": "investigate",
    "sort out": "disentangle",
    "carry out": "execute",
    "point out": "indicate",
    "work out": "compute",
    "turn on": "enable",
    "turn off": "disable",
    "send out": "dispatch",
    "pull in": "ingest",
    "push out": "emit",
    "cut down": "reduce",
    "speed up": "accelerate",
    "slow down": "decelerate",
    "keep track of": "monitor",
    "make sure": "verify",
    "go through": "iterate",
}

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
    "proceed": "proc",
    "examine": "exam",
    "record": "rec",
    "traverse": "trav",
    "decompose": "decomp",
    "implement": "impl",
    "instantiate": "inst",
    "decommission": "decom",
    "investigate": "inv",
    "disentangle": "untangle",
    "execute": "exec",
    "indicate": "ind",
    "compute": "cmp",
    "enable": "en",
    "disable": "dis",
    "dispatch": "disp",
    "ingest": "ing",
    "reduce": "red",
    "accelerate": "accel",
    "decelerate": "decel",
    "monitor": "mon",
    "verify": "vfy",
    "iterate": "iter",
}

# Shared etymon clippings across EN/Latin/FR/ES/DE/IT.
# Avoid false friends (e.g. FR nombre ≠ number).
# INFORMATION SOURCE emoji (U+2139 U+FE0F); C family=emoji owns the rewrite (not ETYMON).
INFO_GLYPH = "ℹ️"  # U+2139 + U+FE0F

# information / info / 情報 / información… → ℹ️ moved to C family=emoji (EMOJI_SPEC).
ETYMON_ALIGN: dict[str, str] = {
    "communication": "comm",
    "comunicación": "comm",
    "kommunikation": "comm",
    "comunicazione": "comm",
    "configuration": "cfg",
    "configuración": "cfg",
    "configurazione": "cfg",
    "konfiguration": "cfg",
    "document": "doc",
    "documento": "doc",
    "dokument": "doc",
    "documentation": "docs",
    "documentación": "docs",
    "documentazione": "docs",
    "problem": "prob",
    "problème": "prob",
    "problema": "prob",
    "function": "fn",
    "función": "fn",
    "funktion": "fn",
    "funzione": "fn",
    "fonction": "fn",
    "example": "ex",
    "ejemplo": "ex",
    "exemple": "ex",
    "beispiel": "ex",
    "esempio": "ex",
    "number": "num",
    "número": "num",
    "nummer": "num",
    "numero": "num",
    "answer": "resp",
    "respuesta": "resp",
    "réponse": "resp",
    "antwort": "resp",
    "risposta": "resp",
    "message": "msg",
    "mensaje": "msg",
    "nachricht": "msg",
    "messaggio": "msg",
    "project": "proj",
    "proyecto": "proj",
    "projet": "proj",
    "projekt": "proj",
    "progetto": "proj",
    "system": "sys",
    "sistema": "sys",
    "système": "sys",
    "process": "proc",
    "proceso": "proc",
    "processus": "proc",
    "prozess": "proc",
    "processo": "proc",
    "result": "res",
    "resultado": "res",
    "résultat": "res",
    "ergebnis": "res",
    "risultato": "res",
    "service": "svc",
    "servicio": "svc",
    "dienst": "svc",
    "servizio": "svc",
    "request": "req",
    "solicitud": "req",
    "requête": "req",
    "anfrage": "req",
    "richiesta": "req",
    "response": "resp",
    "error": "err",
    "erreur": "err",
    "fehler": "err",
    "errore": "err",
    "version": "ver",
    "versión": "ver",
    "versione": "ver",
    "parameter": "param",
    "parámetro": "param",
    "paramètre": "param",
    "parametro": "param",
    "directory": "dir",
    "directorio": "dir",
    "répertoire": "dir",
    "verzeichnis": "dir",
    "application": "app",
    "aplicación": "app",
    "anwendung": "app",
    "applicazione": "app",
    "database": "db",
    "base de datos": "db",
    "base de données": "db",
    "datenbank": "db",
    "network": "net",
    "réseau": "net",
    "netzwerk": "net",
    "rete": "net",
    "security": "sec",
    "seguridad": "sec",
    "sécurité": "sec",
    "sicherheit": "sec",
    "sicurezza": "sec",
    "development": "dev",
    "desarrollo": "dev",
    "développement": "dev",
    "entwicklung": "dev",
    "sviluppo": "dev",
    "production": "prod",
    "producción": "prod",
    "produktion": "prod",
    "produzione": "prod",
}

_AGGRESSIVE_ONLY = frozenset(
    {"like", "just", "actually", "literally", "right", "anyway", "anyhow", "per se"}
)


# --- C-owned same-language abbreviation helpers ---------------------------------

_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_TENS_ALT = {"fourty": 40}  # common misspelling
_ALL_NUM_WORDS: dict[str, int] = {**_ONES, **_TENS, **_TENS_ALT}

_COMPOUND_NUM = re.compile(
    r"\b("
    + "|".join(sorted({**_TENS, **_TENS_ALT}, key=len, reverse=True))
    + r")[\s-]+("
    + "|".join(
        sorted(
            _ONES.keys()
            - {
                "zero",
                "ten",
                "eleven",
                "twelve",
                "thirteen",
                "fourteen",
                "fifteen",
                "sixteen",
                "seventeen",
                "eighteen",
                "nineteen",
            },
            key=len,
            reverse=True,
        )
    )
    + r")\b",
    re.I,
)
_A_ONE_HUNDRED = re.compile(r"\b(?:a|one)\s+hundred\b", re.I)
_A_ONE_THOUSAND = re.compile(r"\b(?:a|one)\s+thousand\b", re.I)
_BARE_HUNDRED = re.compile(r"\bhundred\b", re.I)
_BARE_THOUSAND = re.compile(r"\bthousand\b", re.I)


def apply_spelled_numbers(text: str) -> str:
    """Best-effort EN number words → digits (zero–twenty, tens, hundred/thousand).

    C (ShorthandEdge) owns this pass. Handles ``three``→``3``,
    ``twenty-one`` / ``twenty one``→``21``, ``a hundred`` / ``one hundred``→``100``.
    es / pt / fr sentences are skipped (French ``four`` = oven, not 4).
    """
    return apply_outside_romance(text, _spelled_numbers_en)


def _spelled_numbers_en(text: str) -> str:
    out = text
    out = _A_ONE_HUNDRED.sub("100", out)
    out = _A_ONE_THOUSAND.sub("1000", out)
    out = _BARE_HUNDRED.sub("100", out)
    out = _BARE_THOUSAND.sub("1000", out)

    def _comp(m: re.Match[str]) -> str:
        tens = _ALL_NUM_WORDS[m.group(1).lower()]
        ones = _ONES[m.group(2).lower()]
        return str(tens + ones)

    out = _COMPOUND_NUM.sub(_comp, out)
    for word, num in sorted(_ALL_NUM_WORDS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(rf"(?i)\b{_ascii_ci(word)}\b", str(num), out)
    return out


# Light EN contractions (same-language abbreviation). C-owned.
# JA subject → I first so ``私は will`` → ``I'll``.
# Single source: EN_CONTRACTION_SPEC drives both apply path and C ledger registration.
_FIRST_PERSON_SUBJ = re.compile(r"私は|僕は|俺は|拙者は|わたしは|あたしは")

# (ledger id suffix after "c-", surface source, short form)
EN_CONTRACTION_SPEC: tuple[tuple[str, str, str], ...] = (
    ("ill", "I will", "I'll"),
    ("id", "I would", "I'd"),
    ("ive", "I have", "I've"),
    ("im", "I am", "I'm"),
    ("ur", "you are", "u r"),
    ("were", "we are", "we're"),
    ("theyre", "they are", "they're"),
    ("hes", "he is", "he's"),
    ("its", "it is", "it's"),
    # that is → i.e. owned by conj-that-is / MorphoZip; do not dual-claim via that's
    ("theres", "there is", "there's"),
    ("therere", "there are", "there're"),
    ("dont", "do not", "don't"),
    ("doesnt", "does not", "doesn't"),
    ("cant", "cannot", "can't"),
    ("wont", "will not", "won't"),
    ("shouldnt", "should not", "shouldn't"),
    ("wouldnt", "would not", "wouldn't"),
    ("isnt", "is not", "isn't"),
    ("arent", "are not", "aren't"),
    ("wasnt", "was not", "wasn't"),
    ("werent", "were not", "weren't"),
    ("hasnt", "has not", "hasn't"),
    ("havent", "have not", "haven't"),
    ("hadnt", "had not", "hadn't"),
    ("couldnt", "could not", "couldn't"),
    ("mustnt", "must not", "mustn't"),
    ("lets", "let us", "let's"),
    ("wouldve", "would have", "would've"),
    ("shouldve", "should have", "should've"),
    ("couldve", "could have", "could've"),
    ("mightve", "might have", "might've"),
    ("willve", "will have", "will've"),
)

_EN_CONTRACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"\b{_ascii_ci(src)}\b", re.I), dst)
    for _sid, src, dst in EN_CONTRACTION_SPEC
]


# Ledger rows pruned after the o200k-calibrated estimate_tokens: the short form
# costs more tokens than English, or ties on tokens without saving utf8 bytes.
# Adoption (cheapest-form rule): fewer o200k tokens, or a token tie with strictly
# fewer utf8 bytes.
LEDGER_PRUNED_O200K: frozenset[str] = frozenset(
    {
    "adv-a-priori",
    "adv-after-all",
    "adv-afterwards",
    "adv-already",
    "adv-alternately",
    "adv-anew",
    "adv-anytime",
    "adv-anywhere",
    "adv-apart",
    "adv-aside",
    "adv-backwards",
    "adv-beforehand",
    "adv-de-facto",
    "adv-downstairs",
    "adv-elsewhere",
    "adv-ever-after",
    "adv-everywhere",
    "adv-ex-officio",
    "adv-forever",
    "adv-formerly",
    "adv-in-effect",
    "adv-in-practice",
    "adv-in-situ",
    "adv-in-succession",
    "adv-indoors",
    "adv-inside-out",
    "adv-instead",
    "adv-meanwhile",
    "adv-mutatis-mutandis",
    "adv-nearby",
    "adv-no-doubt",
    "adv-nowhere",
    "adv-of-late",
    "adv-offshore",
    "adv-on-purpose",
    "adv-only",
    "adv-outdoors",
    "adv-overboard",
    "adv-overhead",
    "adv-overnight",
    "adv-overseas",
    "adv-pending",
    "adv-probably",
    "adv-respectively",
    "adv-right-then",
    "adv-shortly-after",
    "adv-shortly-before",
    "adv-so-to-speak",
    "adv-somewhat",
    "adv-somewhere",
    "adv-sui-generis",
    "adv-thereafter",
    "adv-under-way",
    "adv-underground",
    "adv-underwater",
    "adv-upside-down",
    "adv-upstairs",
    "adv-very",
    "aux-neg-can",
    "c-inter-alia",
    "c-na",
    "c-regarding",
    "compare-le",
    "conj-for-example",
    "conj-hence",
    "conj-unless",
    "conj-while",
    "deixis-these",
    "deixis-those",
    "deixis-あれ",
    "det-both",
    "det-each",
    "det-every",
    "det-none",
    "det-some",
    "e-conj-therefore",
    "e-conj-whereas",
    "emoji-alarm",
    "emoji-cry",
    "emoji-hundred",
    "emoji-information",
    "emoji-mail",
    "emoji-money",
    "emoji-party",
    "emoji-pray",
    "emoji-rocket",
    "emoji-skull",
    "emoji-time",
    "emoji-warn",
    "emoji-wrench",
    "furniture-table",
    "legal-herein",
    "legal-notwithstanding",
    "legal-therein",
    "legal-thereof",
    "legal-thereto",
    "legal-therewith",
    "legal-whereby",
    "music-dim7",
    "path-doc",
    "polarity-never",
    "prep-aboard",
    "prep-across",
    "prep-against",
    "prep-along",
    "prep-beside",
    "prep-between",
    "prep-beyond",
    "prep-circa",
    "prep-composed-of",
    "prep-despite",
    "prep-except",
    "prep-faced-with",
    "prep-further-to",
    "prep-immune-to",
    "prep-including",
    "prep-opposite",
    "prep-past",
    "prep-preceding",
    "prep-prone-to",
    "prep-typical-of",
    "prep-under-review",
    "prep-until",
    "prep-with",
    "prep2-after",
    "pronoun-I",
    "pronoun-ella",
    "pronoun-elle",
    "pronoun-he-or-she",
    "pronoun-mine",
    "pronoun-ours",
    "pronoun-theirs",
    "pronoun-usted",
    "pronoun-ustedes",
    "pronoun-you-all",
    "pronoun-yours",
    "pronoun-yourself",
    "quant-various",
    "symbol-infinity",
    }
)


def en_contraction_ledger_rows() -> list[dict[str, Any]]:
    """C ledger row skeletons for EN contractions (family=abbrev).

    Rewrite engine is ``apply_en_contractions`` (``ledger_apply=False``) so the
    ledger stays a registration record and does not double-apply. Bare ``that is``
    is owned by latin ``conj-that-is``→``i.e.`` (not contracted to ``that's``).
    Pipeline note: after C ``do not``→``don't`` / ``cannot``→``can't``, E may fold
    ``don't``→``!`` / ``can't``→``!can``.
    """
    rows: list[dict[str, Any]] = []
    for sid, src, dst in EN_CONTRACTION_SPEC:
        forms = [src]
        low = src.lower()
        if low != src:
            forms.append(low)
        rows.append(
            {
                "id": f"c-{sid}",
                "kind": "lex",
                "apply_layer": "C",
                "family": "abbrev",
                "abbrev_kind": "contraction",
                "ledger_apply": False,
                "rewrite_via": "apply_en_contractions",
                "from": forms,
                "to": dst,
                "rationale": (
                    f"{src}→{dst} は C 同一言語略（I'll 族）。"
                    "書換は apply_en_contractions；台帳は登録のみ。"
                ),
            }
        )
    return [r for r in rows if r["id"] not in LEDGER_PRUNED_O200K]


def apply_en_contractions(text: str) -> str:
    """Same-language EN contractions (``I will``→``I'll``, …). C-owned.

    Applies JA first-person subject → ``I`` first so ``私は will`` becomes ``I'll``.
    """
    out = _FIRST_PERSON_SUBJ.sub("I", text)
    for pat, repl in _EN_CONTRACTIONS:
        out = pat.sub(repl, out)
    return out


# --- C-owned word→emoji (family=emoji); ledger applies (unlike contractions) -----
# Spec tuple: (id_suffix, pivot, pivot_lang, from-forms, short glyph, rationale)
# Multilingual path (C policy): ML aliases → pivot (default EN; JA when EN awkward)
# → emoji. One pivot per emoji id. forms[0] is metrics sample (must utf8-shrink).
# Pivot is recorded on the ledger row so 台帳を見て判断できる. Bare fire/idea/eyes/…
# that are utf8-flat may also live in EMOJI_RUNTIME_EXTRA (DEFAULT_MAP).
# Short-form priority (C policy): math/symbol first when it clearly covers meaning;
# else emoji. Do not invent redundant new math when inventory already covers it.
# information→ℹ️ is C emoji (not ETYMON). FYI phrase stays DEFAULT_MAP-first.
EMOJI_SPEC: tuple[tuple[str, str, str, tuple[str, ...], str, str], ...] = (
    (
        "thumbs-up",
        "thumbs up",
        "en",
        (
            "thumbs up",
            "thumbs-up",
            "thumbsup",
            "いいね",
        ),
        "👍",
        "ML→pivot thumbs up→👍",
    ),
    ("star", "star", "en", ('star',), "★", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("heart", "red heart", "en", ('red heart',), "♡", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("check", "check", "en", ('check mark', 'check'), "✓", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("cross", "cross mark", "en", ('cross mark',), "✕", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("eyes", "eye emoji", "en", ('eye emoji',), "👀", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("wave", "wave hello", "en", ('wave hello',), "👋", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("ok-hand", "ok hand", "en", ('ok hand',), "👌", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("thumbs-down", "thumbs down", "en", ('thumbs down', 'thumbs-down'), "👎", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("clap", "clapping", "en", ('clapping',), "👏", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("idea", "idea bulb", "en", ('idea bulb',), "💡", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("pin", "pin it", "en", ('pin it',), "📌", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("fire", "on fire", "en", ('on fire',), "🔥", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("laugh", "laugh", "en", ('laugh',), "😂", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("thinking", "thinking face", "en", ('thinking face',), "🤔", "o200k 同数・utf8 減（tie+bytes 採用）"),
)

# Token-only extras for DEFAULT_MAP (utf8 flat or ambiguous bare forms). Not ledger.
EMOJI_RUNTIME_EXTRA: dict[str, str] = {
    "thumbs up": "👍",  # o200k 2→1 token; covered by ledger too
}


def emoji_policy_rows() -> list[dict[str, Any]]:
    """C policy rows: emoji pivot path + short-form priority (math/symbol first)."""
    return [
        {
            "id": "policy-emoji-pivot",
            "kind": "policy",
            "apply_layer": "C",
            "family": "emoji",
            "metrics": None,
            "rationale": (
                "絵文字の多言語経路は共通ルールで寄せる: ML 別名 → pivot（既定 EN；"
                "EN が不自然なら JA 可）→ 絵文字。emoji id ごとに pivot を1つ固定。"
                "台帳の pivot / pivot_lang を見て一発で判断できること。"
                "短形優先で数学/記号が意味を覆う場合は絵文字経路に乗らない。"
            ),
            "payload": {
                "path": ["ml_aliases", "pivot", "emoji"],
                "default_pivot_lang": "en",
                "alt_pivot_lang": "ja",
                "one_pivot_per_emoji_id": True,
                "apply": "two_step_preferred",
                "note": "alias→pivot then pivot→emoji; end state may collapse to one replace",
            },
        },
        {
            "id": "policy-short-form-priority",
            "kind": "policy",
            "apply_layer": "C",
            "metrics": None,
            "rationale": (
                "短形の優先順位: (1) 意味がはっきり載るなら数学/記号"
                "（≥≤、←→、∴∵、&、✓、★、≠、∞ 等の E/C 在庫）を優先。"
                "(2) 数学/記号が噛み合わないときだけ絵文字。"
                "両方効くなら新数学記号を増やさず既存記号を選ぶ（絵文字より記号）。"
            ),
            "payload": {
                "order": ["ml_math_symbol_inventory", "emoji"],
                "prefer_math_symbol_when_both": True,
                "prefer_emoji_over_new_math": False,
                "fallback_examples": ["≥", "≤", "←", "→", "∴", "∵", "&", "✓", "★", "≠", "∞"],
                "owns": "C judgment; E inventories remain E-owned for closed packs",
                "overlap_note": (
                    "check→✓（not ✅）; star→★（not ⭐）; cross→✕（not ❌）；"
                    "approx stays E ~/≒ — do not invent ≈"
                ),
            },
        },
        {
            "id": "policy-cross-lang-cheapest",
            "kind": "policy",
            "apply_layer": "C",
            "metrics": None,
            "rationale": (
                "言語横断で意味が通る候補があるとき、GPT 系生成と BERT 系双方向/マスクの"
                "両方で楽になる表層を選ぶ（圧縮候補の中での楽さ）。"
                "dual metric: トークン（B estimate_tokens）を第一とし、同点なら短い"
                "ビット（E utf8_bits / 在庫時 closed_inventory_bits）→ 文字長 → 先出順。"
                "表現の揺らぎは一意の canonical emit へ寄せる。"
                "言語ルールは記述網羅ではなく token/bit 圧縮都合で取り入れる。"
                "登録時 utf8 が縮まない候補は落とす。ヘルパー: shared.ledger.select_cheapest_form。"
            ),
            "payload": {
                # Align names with select_cheapest_form rank_by return.
                "rank_by": ["token", "utf8_bits", "len", "order"],
                "require_utf8_shrink_vs_sample": True,
                "helper": "shared.ledger.select_cheapest_form",
                "token_via": "B TesseraTalk estimate_tokens",
                "bit_via": "E MorphoZip utf8_bits (default) / closed_inventory_bits",
                "easing": "gpt_and_bert_friendly",
                "on_token_tie": "shorter_utf8_bits",
                "yuragi": "unique_canonical_emit",
                "language_rules": "compression_convenience",
                "examples": [
                    "tables→机（JA が EN より token+utf8 楽）",
                    "yo→I（ES→EN 主語）",
                    "check mark→✓（記号が絵文字 ✅ と同コストなら記号）",
                ],
            },
        },
    ]


# --- C-owned open math/symbol (family=symbol); not E closed POS -------------
# Prefer these over emoji when meaning is clear (policy-short-form-priority).
# Skip forms already owned by E (~ / ≒ / = / ≥ / ≤ / ∴ / bc / ∀ …).
# Spec: (id_suffix, from-forms, glyph, rationale); forms[0] = metrics sample.
SYMBOL_SPEC: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("neq", ('not equal', 'not equals'), "≠", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("degree", ('degrees',), "°", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("propto", ('proportional to', 'propto'), "∝", "o200k 同数・utf8 減（tie+bytes 採用）"),
    ("div", ('divided by',), "÷", "o200k 同数・utf8 減（tie+bytes 採用）"),
    (
        "much-less-than",
        ("much less than", "≪"),
        "≪",
        "much less than→≪（o200k 3→2 token・utf8 減。much less 単独は E 況 のまま）",
    ),
    (
        "not-exists",
        ("there is no", "∄"),
        "∄",
        "there is no→∄（o200k 3→2 token・utf8 減。there is→there's より先に適用）",
    ),
    (
        "plusminus",
        ("plus or minus", "plus-minus", "プラスマイナス"),
        "±",
        "plus or minus→±",
    ),
    (
        "percent",
        ("パーセント", "per cent", "percent"),
        "%",
        "パーセント→%（cross-lang cheapest；sample=パーセント）",
    ),
    (
        "implies",
        ("implies that", "含意", "implies"),
        "⇒",
        "implies→⇒",
    ),
    (
        "iff",
        ("if and only if",),
        "⇔",
        "if and only if→⇔",
    ),
    (
        "sqrt",
        ("square root", "sqrt"),
        "√",
        "square root→√",
    ),
    (
        "times",
        ("multiplied by", "×"),
        "×",
        "multiplied by→×（bare times は時刻と曖昧のため見送り）",
    ),
)


def symbol_ledger_rows() -> list[dict[str, Any]]:
    """C ledger row skeletons for open math/symbol (family=symbol)."""
    rows: list[dict[str, Any]] = []
    for sid, forms, dst, rationale in SYMBOL_SPEC:
        forms_list = list(forms)
        if dst not in forms_list:
            forms_list.append(dst)
        rows.append(
            {
                "id": f"symbol-{sid}",
                "kind": "lex",
                "apply_layer": "C",
                "family": "symbol",
                "ledger_apply": True,
                "from": forms_list,
                "to": dst,
                "rationale": rationale,
            }
        )
    return [r for r in rows if r["id"] not in LEDGER_PRUNED_O200K]


def emoji_ledger_rows() -> list[dict[str, Any]]:
    """C ledger row skeletons for word→emoji (family=emoji, ledger_apply=True).

    Each row records ``pivot`` / ``pivot_lang`` so the ledger alone shows the
    ML→pivot→emoji judgment. ``from`` lists surface forms (metrics sample first).
    """
    rows: list[dict[str, Any]] = []
    for sid, pivot, pivot_lang, forms, dst, rationale in EMOJI_SPEC:
        forms_list = list(forms)
        if pivot not in forms_list:
            forms_list.append(pivot)
        rows.append(
            {
                "id": f"emoji-{sid}",
                "kind": "lex",
                "apply_layer": "C",
                "family": "emoji",
                "ledger_apply": True,
                "pivot": pivot,
                "pivot_lang": pivot_lang,
                "from": forms_list,
                "to": dst,
                "rationale": rationale,
            }
        )
    return [r for r in rows if r["id"] not in LEDGER_PRUNED_O200K]


def emoji_default_map() -> dict[str, str]:
    """Flat long→glyph map for ShorthandEdge DEFAULT_MAP (spec + runtime extras)."""
    out: dict[str, str] = {}
    for _sid, _pivot, _lang, forms, dst, _r in EMOJI_SPEC:
        for f in forms:
            key = f.lower() if f.isascii() else f
            out[key] = dst
            if f.isascii():
                out[f.lower()] = dst
    out.update(EMOJI_RUNTIME_EXTRA)
    return out


def emoji_pivot_alias_pairs() -> list[tuple[str, str, str]]:
    """(alias, pivot, emoji_id) for aliases that are not the pivot itself."""
    pairs: list[tuple[str, str, str]] = []
    for sid, pivot, _lang, forms, _dst, _r in EMOJI_SPEC:
        for f in forms:
            if f != pivot:
                pairs.append((f, pivot, f"emoji-{sid}"))
    return pairs


# Pure fillers (um/uh/erm/er) are still stripped anywhere. Single-word
# interjections that are also content words (well = adverb/adj,
# oh/ah in "Oh no!"). Drop them ONLY in clause-initial interjection position
# with their trailing comma ("Well, if you…" → "If you…"); never elsewhere
# ("I feel well", "as well", "did it well, I think" stay intact).
_INTERJECTION_ONLY = frozenset({"ah", "oh", "well"})
_INTERJ_RE = re.compile(
    r"(?i)(^|(?<=[.!?;:,\n\"“‘(\])])\s*)\s*\b(?:um|uh|erm|er|ah|oh|well)\b\s*,\s*"
)


def _strip_interjections(text: str) -> str:
    def _sub(m: re.Match[str]) -> str:
        return m.group(1)

    prev = None
    out = text
    while prev != out:
        prev = out
        new = []
        pos = 0
        for m in _INTERJ_RE.finditer(out):
            new.append(out[pos:m.start()])
            new.append(_sub(m))
            rest = out[m.end():]
            # re-capitalize the following word if the dropped interjection was
            if rest and m.group(0).strip()[:1].isupper() and rest[0].islower():
                new.append(rest[0].upper())
                pos = m.end() + 1
            else:
                pos = m.end()
        new.append(out[pos:])
        out = "".join(new)
    return out


# Fillers that are also content words / clauses ("I know you", "very well",
# "you see the house", "turn right"): strip only when comma-delimited.
_PUNCT_BOUNDED_ONLY: frozenset[str] = frozenset({
    "oh", "ah", "well", "right", "like", "anyway", "anyhow", "you know", "i mean",
    "you see", "i guess", "i suppose", "y'know", "just", "actually",
})


def strip_fillers(text: str, *, aggressive: bool = False) -> str:
    """Remove light fillers / interjections. ``aggressive`` enables hedge words like just/like."""
    out = text
    for f in sorted(FILLERS_JA, key=len, reverse=True):
        out = out.replace(f, "")

    en = list(FILLERS_EN)
    if not aggressive:
        en = [f for f in en if f not in _AGGRESSIVE_ONLY]
    en.sort(key=len, reverse=True)
    out = _strip_interjections(out)
    for f in en:
        if f in _INTERJECTION_ONLY:
            continue
        e = _ascii_ci(f)
        # "Oh, X" / "Well, X": drop the filler together with its comma.
        out = re.sub(rf"(?i)(?:(?<=^)|(?<=[\s“\"(\[—])){e}\s*,\s*", "", out)
        # "..., I suppose, ..." / "..., you know." : drop with the leading comma.
        out = re.sub(rf"(?i),\s*{e}(?=\s*[,.;:!?”\"—)\]]|\s*$)", "", out)
        if f in _PUNCT_BOUNDED_ONLY:
            continue
        # Bare filler only when it is not an exclamation ("Oh!" / "Oh, oh!").
        out = re.sub(rf"(?i)\b{e}\b(?!\s*[!?])", "", out)

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r",(?:\s*,)+", ",", out)  # "So, uh, ok" → "So, ok" (no ",,")
    out = re.sub(r"^\s*,\s*", "", out)  # never leave a dangling leading comma
    return out.strip()


_DO_MAIN_VERB = re.compile(
    r"(?i)\bdo\b(?=\s+(?:the|a|an|it|this|my|your|his|her|our|their|some|any|"
    r"everything|something|anything|nothing|work|homework|research|business|"
    r"job|task|tasks|chores|dishes|laundry)\b)"
)


def apply_unique_readings(text: str, *, compact: bool = False) -> str:
    """Replace polysemous basics with tighter verbs; optionally UNIQUE_COMPACT.

    Default ``compact=False`` (E / anti-ambiguity long form). Pass ``compact=True``
    from C (ShorthandEdge) to also clip ascertain→ascrt etc.
    """
    out = text
    for long, tight in sorted(UNIQUE_READINGS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if long == "do":
            # Only main-verb do + object. Aux/pro-verb do ("I do.", "Do you?") untouched.
            out = re.sub(_DO_MAIN_VERB, tight, out)
            continue
        out = re.sub(rf"(?i)\b{_ascii_ci(long)}\b", tight, out)
    if compact:
        out = apply_unique_compact(out)
    return out


def apply_unique_compact(text: str) -> str:
    """Apply UNIQUE_COMPACT only (C ownership). ascertain→ascrt, configure→cfg, …"""
    out = text
    for long, short in sorted(UNIQUE_COMPACT.items(), key=lambda kv: len(kv[0]), reverse=True):
        if long == short:
            continue
        out = re.sub(rf"(?i)\b{_ascii_ci(long)}\b", short, out)
    return out


def apply_etymon_align(text: str) -> str:
    """Collapse related-language surface forms toward a shared short etymon."""
    out = text
    for surface, etymon in sorted(ETYMON_ALIGN.items(), key=lambda kv: len(kv[0]), reverse=True):
        if surface.isascii():
            out = re.sub(rf"(?i)\b{_ascii_ci(surface)}\b", etymon, out)
        else:
            for form in (surface, surface[:1].upper() + surface[1:]):
                out = re.sub(nonascii_word_pattern(form), etymon, out)
    return out


# --- JSON policy load/dump (process-local override) ---


def dump_policy() -> dict[str, Any]:
    """Serialize current FILLERS / UNIQUE / ETYMON tables to a JSON-friendly dict."""
    return {
        "fillers_en": list(FILLERS_EN),
        "fillers_ja": list(FILLERS_JA),
        "unique_readings": dict(UNIQUE_READINGS),
        "unique_compact": dict(UNIQUE_COMPACT),
        "etymon_align": dict(ETYMON_ALIGN),
        "aggressive_only": sorted(_AGGRESSIVE_ONLY),
    }


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load JSON policy and override module-level tables in-process.

    Keys (all optional): fillers_en, fillers_ja, unique_readings, unique_compact,
    etymon_align, aggressive_only. Missing keys leave current values unchanged.
    Returns the applied payload (merged view of what was set).
    """
    global FILLERS_EN, FILLERS_JA, UNIQUE_READINGS, UNIQUE_COMPACT, ETYMON_ALIGN, _AGGRESSIVE_ONLY

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("lex policy JSON must be an object")

    applied: dict[str, Any] = {}
    if "fillers_en" in data:
        FILLERS_EN = tuple(str(x) for x in data["fillers_en"])
        applied["fillers_en"] = list(FILLERS_EN)
    if "fillers_ja" in data:
        FILLERS_JA = tuple(str(x) for x in data["fillers_ja"])
        applied["fillers_ja"] = list(FILLERS_JA)
    if "unique_readings" in data:
        UNIQUE_READINGS = {str(k): str(v) for k, v in dict(data["unique_readings"]).items()}
        applied["unique_readings"] = dict(UNIQUE_READINGS)
    if "unique_compact" in data:
        UNIQUE_COMPACT = {str(k): str(v) for k, v in dict(data["unique_compact"]).items()}
        applied["unique_compact"] = dict(UNIQUE_COMPACT)
    if "etymon_align" in data:
        ETYMON_ALIGN = {str(k): str(v) for k, v in dict(data["etymon_align"]).items()}
        applied["etymon_align"] = dict(ETYMON_ALIGN)
    if "aggressive_only" in data:
        _AGGRESSIVE_ONLY = frozenset(str(x) for x in data["aggressive_only"])
        applied["aggressive_only"] = sorted(_AGGRESSIVE_ONLY)
    return applied


def _as_keyset(section: str, data: dict[str, Any]) -> set[str]:
    """Keys (or items for list sections) for diffing one policy section."""
    if section in ("fillers_en", "fillers_ja", "aggressive_only"):
        vals = data.get(section)
        if vals is None:
            return set()
        return {str(x) for x in vals}
    mapping = data.get(section)
    if not isinstance(mapping, dict):
        return set()
    return {str(k) for k in mapping}


def diff_policy(
    a: dict[str, Any] | str | Path,
    b: dict[str, Any] | str | Path,
) -> dict[str, dict[str, list[str]]]:
    """Diff two lex policies (dicts or JSON paths).

    Returns ``{section: {"added": [...], "removed": [...]}}`` for
    fillers_en/ja, unique_readings, unique_compact, etymon_align, aggressive_only.
    ``added`` = in b but not a; ``removed`` = in a but not b.
    For mapping sections, only keys are compared (not values).
    """

    def _load(x: dict[str, Any] | str | Path) -> dict[str, Any]:
        if isinstance(x, dict):
            return x
        return json.loads(Path(x).read_text(encoding="utf-8"))

    left = _load(a)
    right = _load(b)
    sections = (
        "fillers_en",
        "fillers_ja",
        "unique_readings",
        "unique_compact",
        "etymon_align",
        "aggressive_only",
    )
    out: dict[str, dict[str, list[str]]] = {}
    for sec in sections:
        ka, kb = _as_keyset(sec, left), _as_keyset(sec, right)
        added = sorted(kb - ka)
        removed = sorted(ka - kb)
        if added or removed:
            out[sec] = {"added": added, "removed": removed}
        else:
            out[sec] = {"added": [], "removed": []}
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="TalkCompress shared lexeme policy tools")
    p.add_argument("--dump", action="store_true", help="print current policy JSON to stdout")
    p.add_argument(
        "--diff",
        metavar="OTHER.json",
        help="diff current (or --base) policy keys against OTHER.json",
    )
    p.add_argument(
        "--base",
        metavar="BASE.json",
        help="with --diff: use BASE.json instead of in-process dump as left side",
    )
    args = p.parse_args(argv)

    if args.dump:
        print(json.dumps(dump_policy(), ensure_ascii=False, indent=2))
        return 0
    if args.diff:
        left = json.loads(Path(args.base).read_text(encoding="utf-8")) if args.base else dump_policy()
        result = diff_policy(left, args.diff)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
