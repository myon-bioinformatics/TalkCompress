"""Lexeme policy: fillers, unique-reading preference, light etymon alignment.

Layer ownership (TalkCompress):
- **C ShorthandEdge**: ``strip_fillers``, ``UNIQUE_COMPACT`` (via ``apply_unique_readings(..., compact=True)``
  or ``apply_unique_compact``), same-language EN contractions (``I will``→``I'll``),
  spelled EN number words → digits. Also slang / hereafter / packs.
- **E MorphoZip**: ``UNIQUE_READINGS`` long form only (``compact=False``), ``ETYMON_ALIGN`` (ℹ️),
  first-person / counters / articles / grammar-min. Does **not** strip fillers, apply UNIQUE_COMPACT,
  contract ``I'll``, or digitize spelled numbers by default.
- Helpers live here so both layers can import them; callers choose which passes to run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
    "get": "obtain",
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
    "raise": "raise",
    "devise": "devise",
    "proceed": "proc",
    "examine": "exam",
    "record": "rec",
    "traverse": "trav",
    "decompose": "decomp",
    "implement": "impl",
    "deploy": "deploy",
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
    "emit": "emit",
    "reduce": "red",
    "accelerate": "accel",
    "decelerate": "decel",
    "monitor": "mon",
    "verify": "vfy",
    "iterate": "iter",
}

# Shared etymon clippings across EN/Latin/FR/ES/DE/IT.
# Avoid false friends (e.g. FR nombre ≠ number).
# Prefer INFORMATION SOURCE emoji (U+2139 U+FE0F) over Latin "info" for density.
INFO_GLYPH = "ℹ️"  # U+2139 + U+FE0F

ETYMON_ALIGN: dict[str, str] = {
    "information": INFO_GLYPH,
    "información": INFO_GLYPH,
    "informationen": INFO_GLYPH,
    "informazione": INFO_GLYPH,
    "info": INFO_GLYPH,
    "情報": INFO_GLYPH,
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
    """
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
        out = re.sub(rf"(?i)\b{re.escape(word)}\b", str(num), out)
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
    ("its", "it is", "it's"),
    ("thats", "that is", "that's"),
    ("theres", "there is", "there's"),
    ("therere", "there are", "there're"),
    ("dont", "do not", "don't"),
    ("doesnt", "does not", "doesn't"),
    ("cant", "cannot", "can't"),
    ("wont", "will not", "won't"),
    ("shouldnt", "should not", "shouldn't"),
    ("wouldnt", "would not", "wouldn't"),
)

_EN_CONTRACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"\b{re.escape(src)}\b", re.I), dst)
    for _sid, src, dst in EN_CONTRACTION_SPEC
]


def en_contraction_ledger_rows() -> list[dict[str, Any]]:
    """C ledger row skeletons for EN contractions (family=abbrev).

    Rewrite engine is ``apply_en_contractions`` (``ledger_apply=False``) so the
    ledger stays a registration record and does not fight latin abbrevs such as
    ``that is``→``i.e.`` or double-apply. Pipeline note: after C ``do not``→
    ``don't`` / ``cannot``→``can't``, E may fold ``don't``→``!`` / ``can't``→``!can``.
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
    return rows


def apply_en_contractions(text: str) -> str:
    """Same-language EN contractions (``I will``→``I'll``, …). C-owned.

    Applies JA first-person subject → ``I`` first so ``私は will`` becomes ``I'll``.
    """
    out = _FIRST_PERSON_SUBJ.sub("I", text)
    for pat, repl in _EN_CONTRACTIONS:
        out = pat.sub(repl, out)
    return out


def strip_fillers(text: str, *, aggressive: bool = False) -> str:
    """Remove light fillers / interjections. ``aggressive`` enables hedge words like just/like."""
    out = text
    for f in sorted(FILLERS_JA, key=len, reverse=True):
        out = out.replace(f, "")

    en = list(FILLERS_EN)
    if not aggressive:
        en = [f for f in en if f not in _AGGRESSIVE_ONLY]
    en.sort(key=len, reverse=True)
    for f in en:
        out = re.sub(rf"(?i)\b{re.escape(f)}\b", "", out)

    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return out.strip()


def apply_unique_readings(text: str, *, compact: bool = False) -> str:
    """Replace polysemous basics with tighter verbs; optionally UNIQUE_COMPACT.

    Default ``compact=False`` (E / anti-ambiguity long form). Pass ``compact=True``
    from C (ShorthandEdge) to also clip ascertain→ascrt etc.
    """
    out = text
    for long, tight in sorted(UNIQUE_READINGS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(rf"(?i)\b{re.escape(long)}\b", tight, out)
    if compact:
        out = apply_unique_compact(out)
    return out


def apply_unique_compact(text: str) -> str:
    """Apply UNIQUE_COMPACT only (C ownership). ascertain→ascrt, configure→cfg, …"""
    out = text
    for long, short in sorted(UNIQUE_COMPACT.items(), key=lambda kv: len(kv[0]), reverse=True):
        if long == short:
            continue
        out = re.sub(rf"(?i)\b{re.escape(long)}\b", short, out)
    return out


def apply_etymon_align(text: str) -> str:
    """Collapse related-language surface forms toward a shared short etymon."""
    out = text
    for surface, etymon in sorted(ETYMON_ALIGN.items(), key=lambda kv: len(kv[0]), reverse=True):
        if surface.isascii():
            out = re.sub(rf"(?i)\b{re.escape(surface)}\b", etymon, out)
        else:
            out = out.replace(surface, etymon)
            out = out.replace(surface[:1].upper() + surface[1:], etymon)
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
