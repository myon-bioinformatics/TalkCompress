"""Person × tense coverage matrix for the B-final short-tense bank.

Builds every (subject, tense, verb) cell for the existing high-frequency verb
set, scores live-language candidates (es/fr/pt/it/nl/el) with
``estimate_tokens`` + utf8, and writes:

* ``TesseraTalk/fixtures/tense_matrix.json`` — adopted cells only (runtime bank)
* ``docs/tense_matrix_report.json`` — every cell incl. rejects + reason
* ``docs/tense_matrix.md`` — compact summary

Usage::

    uv run python scripts/tense_matrix.py            # rebuild (deterministic)
    uv run python scripts/tense_matrix.py --check    # exit 1 if outputs stale
    python scripts/tense_matrix.py --refresh-conj    # needs mlconjug3 (scratch venv)

Policy: adopt only when token AND utf8 strictly shrink vs the full EN source.
Personal pronouns are dropped (person-marked verb); demonstratives
(this/that/these/those) and relatives (who/which/that) keep the subject and
only compress the verb chain. Relatives / ``that`` need an EN aux that marks
number (is/are, has/have, was/were, -s); will/past/had cells are rejected as
number-ambiguous. Aux-capable verbs (do/have) skip forms that would eat
do-support or a perfect auxiliary. Bare ``that`` is multi-POS in EN
(demonstrative / relative / complementizer), so every ``that`` cell stays EN.

English-homograph guard (same function as runtime,
``tessera_talk.en_homograph_tokens``): a candidate with any token spelled like
an English word (es ``he visto``, pt ``fora``, es ``van``, pt ``a`` …) is
dropped before ranking; the next-cheapest unique form wins, else EN stays.

Progressive (be + -ing) only competes progressive-preserving periphrases —
es estar + gerundio, pt estar + gerúndio / estar a + inf, it stare +
gerundio, fr être en train de + inf, nl zijn aan het + inf. Simple present /
imperfect / future and nl simple past are not candidates (aspect loss; the
Romance imperfect is also habitual).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONJ_PATH = ROOT / "TesseraTalk/fixtures/tense_conj_table.json"
BANK_PATH = ROOT / "TesseraTalk/fixtures/tense_matrix.json"
REPORT_PATH = ROOT / "docs/tense_matrix_report.json"
MD_PATH = ROOT / "docs/tense_matrix.md"

TENSES = ("pres", "fut", "past", "perf", "futperf", "pluperf", "presprog", "pastprog", "futprog")

# en: base, past, pp, ing, 3s ; es/pt/it/fr infinitive keys into conj table
VERBS: dict[str, dict[str, str]] = {
    "go": dict(en="go went gone going goes", es="ir", pt="ir", it="andare", fr="aller"),
    "come": dict(en="come came come coming comes", es="venir", pt="vir", it="venire", fr="venir"),
    "do": dict(en="do did done doing does", es="hacer", pt="fazer", it="fare", fr="faire"),
    "see": dict(en="see saw seen seeing sees", es="ver", pt="ver", it="vedere", fr="voir"),
    "take": dict(en="take took taken taking takes", es="tomar", pt="tomar", it="prendere", fr="prendre"),
    "find": dict(en="find found found finding finds", es="encontrar", pt="achar", it="trovare", fr="trouver"),
    "want": dict(en="want wanted wanted wanting wants", es="querer", pt="querer", it="volere", fr="vouloir"),
    "have": dict(en="have had had having has", es="tener", pt="ter", it="avere", fr="avoir"),
    "think": dict(en="think thought thought thinking thinks", es="pensar", pt="pensar", it="pensare", fr="penser"),
    "say": dict(en="say said said saying says", es="decir", pt="dizer", it="dire", fr="dire"),
    "know": dict(en="know knew known knowing knows", es="saber", pt="saber", it="sapere", fr="savoir"),
    "give": dict(en="give gave given giving gives", es="dar", pt="dar", it="dare", fr="donner"),
}

PP = {
    "es": "ido venido hecho visto tomado encontrado querido tenido pensado dicho sabido dado",
    "pt": "ido vindo feito visto tomado achado querido tido pensado dito sabido dado",
    "it": "andato venuto fatto visto preso trovato voluto avuto pensato detto saputo dato",
    "fr": "allé venu fait vu pris trouvé voulu eu pensé dit su donné",
}
GER = {
    "es": "yendo viniendo haciendo viendo tomando encontrando queriendo teniendo pensando diciendo sabiendo dando",
    "pt": "indo vindo fazendo vendo tomando achando querendo tendo pensando dizendo sabendo dando",
    "it": "andando venendo facendo vedendo prendendo trovando volendo avendo pensando dicendo sapendo dando",
}
_VKEYS = list(VERBS)
PP = {L: dict(zip(_VKEYS, s.split())) for L, s in PP.items()}
GER = {L: dict(zip(_VKEYS, s.split())) for L, s in GER.items()}
ESSERE = {"go", "come"}  # it essere / fr être auxiliaries
P6 = ("1s", "2s", "3s", "1p", "2p", "3p")


def _p6(s: str) -> dict[str, str]:
    return dict(zip(P6, s.split()))


AUX = {
    ("es", "perf"): _p6("he has ha hemos habéis han"),
    ("es", "pluperf"): _p6("había habías había habíamos habíais habían"),
    ("es", "futperf"): _p6("habré habrás habrá habremos habréis habrán"),
    ("es", "presprog"): _p6("estoy estás está estamos estáis están"),
    ("es", "pastprog"): _p6("estaba estabas estaba estábamos estabais estaban"),
    ("es", "futprog"): _p6("estaré estarás estará estaremos estaréis estarán"),
    ("pt", "pluperf"): _p6("tinha tinhas tinha tínhamos tínheis tinham"),
    ("pt", "futperf"): _p6("terei terás terá teremos tereis terão"),
    ("pt", "presprog"): _p6("estou estás está estamos estais estão"),
    ("pt", "pastprog"): _p6("estava estavas estava estávamos estáveis estavam"),
    ("pt", "futprog"): _p6("estarei estarás estará estaremos estareis estarão"),
    ("it", "perf"): _p6("ho hai ha abbiamo avete hanno"),
    ("it", "perf+e"): _p6("sono sei è siamo siete sono"),
    ("it", "pluperf"): _p6("avevo avevi aveva avevamo avevate avevano"),
    ("it", "pluperf+e"): _p6("ero eri era eravamo eravate erano"),
    ("it", "futperf"): _p6("avrò avrai avrà avremo avrete avranno"),
    ("it", "futperf+e"): _p6("sarò sarai sarà saremo sarete saranno"),
    ("it", "presprog"): _p6("sto stai sta stiamo state stanno"),
    ("it", "pastprog"): _p6("stavo stavi stava stavamo stavate stavano"),
    ("it", "futprog"): _p6("starò starai starà staremo starete staranno"),
    ("fr", "perf"): _p6("ai as a avons avez ont"),
    ("fr", "perf+e"): _p6("suis es est sommes êtes sont"),
    ("fr", "pluperf"): _p6("avais avais avait avions aviez avaient"),
    ("fr", "pluperf+e"): _p6("étais étais était étions étiez étaient"),
    ("fr", "futperf"): _p6("aurai auras aura aurons aurez auront"),
    ("fr", "futperf+e"): _p6("serai seras sera serons serez seront"),
    # être + en train de (progressive periphrasis)
    ("fr", "presprog"): _p6("suis es est sommes êtes sont"),
    ("fr", "pastprog"): _p6("étais étais était étions étiez étaient"),
    ("fr", "futprog"): _p6("serai seras sera serons serez seront"),
}
PROG = ("presprog", "pastprog", "futprog")
# nl zijn + aan het + inf: (1s, 2s, 3s, pl) per tense; futprog = zal … zijn
NL_ZIJN = {"presprog": "ben bent is zijn", "pastprog": "was was was waren", "futprog": "zal zult zal zullen"}

# nl: (1s, 3s/jij, pl) present ; (sg, pl) past.  nl present is NOT future.
NL_PRES = {
    "go": "ga gaat gaan", "come": "kom komt komen", "do": "doe doet doen", "see": "zie ziet zien",
    "take": "neem neemt nemen", "find": "vind vindt vinden", "want": "wil wil willen",
    "have": "heb heeft hebben", "think": "denk denkt denken", "say": "zeg zegt zeggen",
    "know": "weet weet weten", "give": "geef geeft geven",
}
NL_PAST = {
    "go": "ging gingen", "come": "kwam kwamen", "do": "deed deden", "see": "zag zagen",
    "take": "nam namen", "find": "vond vonden", "want": "wilde wilden", "have": "had hadden",
    "think": "dacht dachten", "say": "zei zeiden", "know": "wist wisten", "give": "gaf gaven",
}
# el aorist (simple past): 3s, 1p, 3p — single words; future needs θα (multiword).
EL_AOR = {
    "go": "πήγε πήγαμε πήγαν", "come": "ήρθε ήρθαμε ήρθαν", "do": "έκανε κάναμε έκαναν",
    "see": "είδε είδαμε είδαν", "take": "πήρε πήραμε πήραν", "find": "βρήκε βρήκαμε βρήκαν",
    "say": "είπε είπαμε είπαν", "give": "έδωσε δώσαμε έδωσαν",
}

# subject rows: (label, en surface, person key, number, keep_subject, kind)
SUBJECTS = [
    ("1s", "I", "1s", "sg", False, "pron"),
    ("2", "you", "2", "?", False, "pron"),
    ("3s-he", "he", "3s", "sg", False, "pron"),
    ("3s-she", "she", "3s", "sg", False, "pron"),
    ("3s-it", "it", "3s", "sg", False, "pron"),
    ("1p", "we", "1p", "pl", False, "pron"),
    ("3p", "they", "3p", "pl", False, "pron"),
    ("dem-this", "this", "3s", "sg", True, "dem"),
    ("dem-that", "that", "3s", "sg", True, "dem-that"),
    ("dem-these", "these", "3p", "pl", True, "dem"),
    ("dem-those", "those", "3p", "pl", True, "dem"),
    ("rel-who-sg", "who", "3s", "sg", True, "rel"),
    ("rel-who-pl", "who", "3p", "pl", True, "rel"),
    ("rel-which-sg", "which", "3s", "sg", True, "rel"),
    ("rel-which-pl", "which", "3p", "pl", True, "rel"),
]
NUMBER_MARKED = {"pres", "perf", "presprog", "pastprog"}


def _en(subj: str, person: str, tense: str, verb: str) -> str:
    base, past, pp, ing, s3 = VERBS[verb]["en"].split()
    sg3 = person == "3s"
    be_pres = {"1s": "am", "3s": "is"}.get(person, "are")
    be_past = "was" if person in ("1s", "3s") else "were"
    have = "has" if sg3 else "have"
    chain = {
        "pres": s3 if sg3 else base,
        "fut": f"will {base}",
        "past": past,
        "perf": f"{have} {pp}",
        "futperf": f"will have {pp}",
        "pluperf": f"had {pp}",
        "presprog": f"{be_pres} {ing}",
        "pastprog": f"{be_past} {ing}",
        "futprog": f"will be {ing}",
    }[tense]
    return f"{subj} {chain}"


def _reject_reason(sub: tuple, tense: str, verb: str) -> str | None:
    _label, surf, person, _num, _keep, kind = sub
    if kind == "dem-that":
        return "multi-POS EN 'that' (dem / rel / complementizer): left unconverted (揺らぎ回避)"
    if kind == "rel" and tense not in NUMBER_MARKED:
        return "number-ambiguous: relative with will/past/had (EN aux does not mark sg/pl)"
    if kind in ("dem", "dem-that") and tense in ("pres", "past"):
        return "demonstrative + bare verb: noun/idiom homographs (this saw, that said, these finds)"
    if verb in ("do", "have") and tense in ("pres", "past"):
        return "aux-capable verb: would eat do-support / perfect aux (he does not…, he had eaten)"
    if verb == "have" and tense == "fut":
        return "aux-capable verb: 'will have' prefixes future perfect (will have eaten)"
    return None


def _person_slots(person: str) -> list[tuple[str, str]]:
    """(romance person slot, number tag) candidates for an EN person."""
    if person == "2":
        return [("2s", "2sg-tú"), ("3s", "2sg-usted"), ("2p", "2pl-vosotros/vous"), ("3p", "2pl-ustedes")]
    return [(person, "")]


def _candidates(conj: dict, person: str, tense: str, verb: str, num: str) -> list[dict]:
    out: list[dict] = []

    def add(form: str, lang: str, shape: str, tag: str) -> None:
        out.append({"form": form, "lang": lang, "shape": shape, "number": tag})

    for slot, tag in _person_slots(person):
        for L in ("es", "pt", "it", "fr"):
            c = conj[L][VERBS[verb][L]]
            pl = slot.endswith("p")
            e = verb in ESSERE
            pp = PP[L][verb]
            if L in ("it", "fr") and e and pl:
                pp = pp + ("i" if L == "it" else "s") if L == "fr" else pp[:-1] + "i"
            if tense == "pres":
                add(c["pres"][slot], L, "simple", tag)
            elif tense == "fut":
                add(c["fut"][slot], L, "simple", tag)
            elif tense == "past":
                add(c["pret"][slot], L, "simple", tag)
                if L in ("it", "fr"):
                    aux = AUX[(L, "perf+e" if e else "perf")][slot]
                    add(f"{aux} {pp}", L, "compound", tag)
            elif tense == "perf":
                if L in ("es", "it", "fr"):
                    aux = AUX[(L, "perf+e" if e and L != "es" else "perf")][slot]
                    add(f"{aux} {pp}", L, "compound", tag)
                if L in ("es", "pt"):
                    add(c["pret"][slot], L, "simple-preterite", tag)
            elif tense == "pluperf":
                key = (L, "pluperf+e") if e and L in ("it", "fr") else (L, "pluperf")
                add(f"{AUX[key][slot]} {pp}", L, "compound", tag)
                if L == "pt":
                    add(c["plpf"][slot], L, "simple-pluperfect", tag)
            elif tense == "futperf":
                key = (L, "futperf+e") if e and L in ("it", "fr") else (L, "futperf")
                add(f"{AUX[key][slot]} {pp}", L, "compound", tag)
            if tense in PROG:
                # progressive-preserving periphrases only (no simple tense)
                aux = AUX[(L, tense)][slot]
                inf = VERBS[verb][L]
                if L in GER:
                    add(f"{aux} {GER[L][verb]}", L, "prog-gerund", tag)
                if L == "pt":
                    add(f"{aux} a {inf}", L, "prog-a-inf", tag)
                if L == "fr":
                    de = "d'" if inf[0] in "aeiouéh" else "de "
                    add(f"{aux} en train {de}{inf}", L, "prog-en-train-de", tag)
        # nl
        nl_pres = NL_PRES[verb].split()
        nl_past = NL_PAST[verb].split()
        nl_i = {"1s": 0, "2s": 1, "3s": 1}.get(slot, 2)
        if tense == "pres":
            add(nl_pres[nl_i], "nl", "simple", tag)
        if tense == "past":
            add(nl_past[0 if nl_i < 2 else 1], "nl", "simple", tag)
        if tense in PROG:
            zijn = NL_ZIJN[tense].split()[{"1s": 0, "2s": 1, "3s": 2}.get(slot, 3)]
            tail = " zijn" if tense == "futprog" else ""
            add(f"{zijn} aan het {nl_pres[2]}{tail}", "nl", "prog-aan-het", tag)
        # el aorist
        if tense == "past" and verb in EL_AOR and slot in ("3s", "1p", "3p"):
            add(EL_AOR[verb].split()[("3s", "1p", "3p").index(slot)], "el", "simple", tag)
    seen: set[str] = set()
    uniq = []
    for c in out:
        k = (c["form"], c["lang"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def _existing_sources(t) -> set[str]:
    srcs: set[str] = set()
    for loader in (t.load_es_fr_tense_bank, t.load_pt_el_latin_tense_bank):
        for e in loader()["entries"]:
            for s in e.get("from") or []:
                for v in t._subject_aux_variants(str(s)):
                    srcs.add(v.lower())
    return srcs


def build() -> tuple[dict, dict, str]:
    from tests._helpers import load

    t = load("tessera_talk", "TesseraTalk/tessera_talk.py")
    conj = json.loads(CONJ_PATH.read_text(encoding="utf-8"))["conj"]
    existing = _existing_sources(t)
    tok = t.estimate_tokens
    u8 = lambda s: len(s.encode("utf-8"))  # noqa: E731
    cells: list[dict] = []
    entries: list[dict] = []
    for sub in SUBJECTS:
        label, surf, person, num, keep, kind = sub
        for tense in TENSES:
            for verb in VERBS:
                src = _en(surf, person, tense, verb)
                cell = {"subject": label, "tense": tense, "verb": verb, "src": src}
                cells.append(cell)
                why = _reject_reason(sub, tense, verb)
                if why:
                    cell.update(status="reject", reason=why)
                    continue
                if src.lower() in existing:
                    cell.update(status="existing", reason="already in es_fr_tense / pt_el_latin_tense")
                    continue
                cands = _candidates(conj, person, tense, verb, num)
                if keep:
                    for c in cands:
                        c["form"] = f"{surf} {c['form']}"
                st, su = tok(src), u8(src)
                # English-homograph guard (runtime twin): drop candidates with an
                # EN-spelled token; keep the measured losers for the report.
                head = surf if keep else ""
                homo = [
                    {"form": c["form"], "en": t.en_homograph_tokens(c["form"], keep_head=head)}
                    for c in cands
                    if t.en_homograph_tokens(c["form"], keep_head=head)
                ]
                cands = [c for c in cands if not t.en_homograph_tokens(c["form"], keep_head=head)]
                if homo:
                    cell["homograph_dropped"] = homo
                if person == "2":
                    key = lambda c: (tok(c["form"]), u8(c["form"]), len(c["form"]), c["form"])  # noqa: E731
                    allb = min(cands, key=key)
                    cell["usted_style_best"] = {"form": allb["form"], "number": allb["number"], "tok": tok(allb["form"])}
                    # usted/ustedes are 3rd-person forms: after subject drop they collapse
                    # into he/they, so only genuinely 2nd-person forms (tú / vosotros, vous) compete.
                    cands = [c for c in cands if c["number"] in ("2sg-tú", "2pl-vosotros/vous")]
                if not cands:
                    cell.update(status="reject", reason="EN homograph collision: every candidate spells an English word")
                    continue
                scored = sorted(
                    cands, key=lambda c: (tok(c["form"]), u8(c["form"]), len(c["form"]), c["form"])
                )
                best = scored[0]
                cell.update(
                    best=best["form"], lang=best["lang"], shape=best["shape"], number=best["number"],
                    tok=[st, tok(best["form"])], utf8=[su, u8(best["form"])],
                )
                if tok(best["form"]) < st and u8(best["form"]) < su:
                    keepc = [c for c in scored if tok(c["form"]) < st and u8(c["form"]) < su]
                    cell["status"] = "adopt"
                    entries.append(
                        {
                            "id": f"mx-{verb}-{tense}-{label}",
                            "from": [src],
                            "to": best["form"],
                            "lang": best["lang"],
                            "tense": tense,
                            "subject": label,
                            "candidates": [{"form": c["form"], "lang": c["lang"]} for c in keepc],
                        }
                    )
                elif any(
                    tok(h["form"]) < st and u8(h["form"]) < su for h in homo
                ):
                    cell.update(
                        status="reject",
                        reason="EN homograph collision: every shrinking candidate spells an English word",
                    )
                elif tense in PROG:
                    cell.update(
                        status="reject",
                        reason="no progressive-preserving candidate shrinks both token and utf8 (EN kept)",
                    )
                else:
                    cell.update(status="reject", reason="no candidate shrinks both token and utf8")
    bank = {
        "version": 1,
        "title": "Person × tense matrix bank (generated by scripts/tense_matrix.py)",
        "notes": [
            "Generated — edit scripts/tense_matrix.py, not this file.",
            "Adopted only when token AND utf8 strictly shrink; `to` = runtime cheapest winner.",
            "Personal pronouns dropped (person-marked verb); demonstratives/relatives keep the subject.",
            "Relatives only with number-marking aux (is/are, has/have, was/were); bare 'that' (multi-POS) always stays EN.",
            "EN-homograph guard: candidates with a token spelled like an English word (fixtures/en_wordlist.txt) are dropped; next-cheapest unique form wins.",
            "Progressive: only progressive-preserving periphrases (estar/stare + gerund, estar a + inf, être en train de, aan het); no simple-tense fallback.",
            "you: usted/ustedes measured but excluded (3rd-person forms collapse into he/they after subject drop); tú vs vosotros/vous compete.",
        ],
        "entries": entries,
    }
    report = {"version": 1, "cells": cells}
    return bank, report, _markdown(cells)


def _markdown(cells: list[dict]) -> str:
    st = Counter(c["status"] for c in cells)
    lines = [
        "# Person × tense matrix (B-final short tense)",
        "",
        "Generated by `scripts/tense_matrix.py` — do not edit by hand. Full per-cell data incl. rejects:",
        "`docs/tense_matrix_report.json`. Runtime bank: `TesseraTalk/fixtures/tense_matrix.json`.",
        "",
        f"Cells: {len(cells)} — adopt {st['adopt']}, existing {st['existing']}, reject {st['reject']}.",
        "",
        "Policy: adopt only when token **and** utf8 strictly shrink vs the full EN source.",
        "`to` is the nominal label; runtime cheapest (token→utf8→len) decides.",
        "",
        "- **EN-homograph guard**: a candidate whose any token is spelled like an English word",
        "  (`TesseraTalk/fixtures/en_wordlist.txt`, SCOWL-derived; e.g. es `he visto`, pt `fora`, es `van`, pt `a`)",
        "  is dropped before ranking — the next-cheapest unique form wins, else EN stays (揺らぎ回避).",
        "- **Bare `that`** is multi-POS (dem / rel / complementizer) → every `that` cell stays EN.",
        "- **Progressive** keeps aspect: only es estar+gerundio, pt estar+gerúndio / estar a+inf,",
        "  it stare+gerundio, fr être en train de+inf, nl zijn aan het+inf compete. Simple present /",
        "  imperfect (also habitual) / future and nl simple past are not candidates.",
        "",
        "## Adopted cells per subject × tense (count / dominant lang)",
        "",
        "| subject | " + " | ".join(TENSES) + " |",
        "|---|" + "---|" * len(TENSES),
    ]
    grid: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cells:
        grid[(c["subject"], c["tense"])].append(c)
    for sub in SUBJECTS:
        row = []
        for tense in TENSES:
            cs = grid[(sub[0], tense)]
            ad = [c for c in cs if c["status"] == "adopt"]
            if not ad:
                ex = sum(c["status"] == "existing" for c in cs)
                row.append(f"– ({ex} ex)" if ex else "–")
                continue
            lang = Counter(c["lang"] for c in ad).most_common(1)[0][0]
            row.append(f"{len(ad)} {lang}")
        lines.append(f"| {sub[0]} | " + " | ".join(row) + " |")
    prog = [c for c in cells if c["tense"] in PROG and c["status"] == "adopt"]
    lines += [
        "",
        "## Progressive winners (shape / lang)",
        "",
        ", ".join(f"{k}: {v}" for k, v in sorted(Counter(f"{c['shape']}/{c['lang']}" for c in prog).items()))
        or "(none)",
        "",
        "## EN-homograph guard",
        "",
        f"Cells with ≥1 dropped candidate: {sum('homograph_dropped' in c for c in cells)}; "
        f"most frequent EN-spelled tokens: "
        + ", ".join(
            f"`{w}` {n}"
            for w, n in Counter(w for c in cells for h in c.get("homograph_dropped", []) for w in h["en"]).most_common(15)
        ),
    ]
    lines += ["", "## Reject reasons", ""]
    for why, n in Counter(c["reason"] for c in cells if c["status"] == "reject").most_common():
        lines.append(f"- {n} × {why}")
    two = [c for c in cells if c["subject"] == "2" and c["status"] == "adopt"]
    lines += [
        "",
        "## 2nd person (you) — number of winning form",
        "",
        "Adopted (2nd-person-only forms): "
        + (", ".join(f"{k}: {v}" for k, v in sorted(Counter(c["number"] for c in two).items())) or "(none)"),
        "",
        "If usted/ustedes were allowed, the overall cheapest would be: "
        + ", ".join(
            f"{k}: {v}"
            for k, v in sorted(Counter(c["usted_style_best"]["number"] for c in cells if "usted_style_best" in c).items())
        )
        + " — rejected: after subject drop usted≡él/ella and ustedes≡ellos (person collapse).",
        "",
        "## Shape of winners (compound vs simple)",
        "",
        ", ".join(
            f"{k}: {v}" for k, v in sorted(Counter(c["shape"] for c in cells if c["status"] == "adopt").items())
        ),
        "",
    ]
    return "\n".join(lines)


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def refresh_conj() -> None:  # pragma: no cover - needs mlconjug3
    raise SystemExit("see TesseraTalk/fixtures/tense_conj_table.json notes; regenerate in a scratch venv")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--refresh-conj", action="store_true")
    a = ap.parse_args(argv)
    if a.refresh_conj:
        refresh_conj()
    bank, report, md = build()
    outs = {BANK_PATH: _dump(bank), REPORT_PATH: _dump(report), MD_PATH: md}
    if a.check:
        stale = [str(p) for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        print("stale: " + ", ".join(stale) if stale else "up to date")
        return 1 if stale else 0
    for p, s in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
