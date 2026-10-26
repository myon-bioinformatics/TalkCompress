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
ETYMON_ALIGN: dict[str, str] = {
    "information": "info",
    "información": "info",
    "informationen": "info",
    "informazione": "info",
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


def apply_unique_readings(text: str, *, compact: bool = True) -> str:
    """Replace polysemous basics with tighter verbs, optionally compact."""
    out = text
    for long, tight in sorted(UNIQUE_READINGS.items(), key=lambda kv: len(kv[0]), reverse=True):
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
        if surface.isascii():
            out = re.sub(rf"(?i)\b{re.escape(surface)}\b", etymon, out)
        else:
            out = out.replace(surface, etymon)
            out = out.replace(surface[:1].upper() + surface[1:], etymon)
    return out
