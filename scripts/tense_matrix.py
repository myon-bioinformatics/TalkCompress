"""Person × tense coverage matrix for the B-final short-tense bank.

Builds every (subject, tense, verb) cell for the existing high-frequency verb
set, scores live-language candidates (es/fr/pt/it/nl/de/el/cs/pl) with
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

German (de) competes Präsens / Präteritum with du / ihr for you (never Sie).
Tie rule: where de ties nl on (tokens, utf8) de wins; nl stays only when strictly
cheaper. On an exact (tokens, utf8) tie es/fr/pt also beat it/cs/pl.
Otherwise the plain token → utf8 → len → form order applies.

Czech / Polish compete only in simple future and present perfect (see tables).

Cross-language collision guard (all languages): a candidate whose lexical-verb
token is already registered (``form_registry``) with another verb / function
word, or in another language with a tense class its own language lacks, is
dropped (it ``sa``/sv ``sa``, nl ``kom`` vs Nordic ``kom``, de ``das`` vs es ``das``).

Progressive (be + -ing) only competes progressive-preserving periphrases —
es estar + gerundio, pt estar + gerúndio / estar a + inf, it stare +
gerundio, fr être en train de + inf, nl zijn aan het + inf. Simple present /
imperfect / future and nl simple past are not candidates (aspect loss; the
Romance imperfect is also habitual).
"""

from __future__ import annotations

import argparse
import json
import re
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
# de: P6 order (1s ich, 2s du, 3s er/sie/es, 1p wir, 2p ihr, 3p sie). Never Sie
# (formal = 3p form → collapses into they after subject drop, like usted).
DE_PRES = {
    "go": "gehe gehst geht gehen geht gehen", "come": "komme kommst kommt kommen kommt kommen",
    "do": "tue tust tut tun tut tun", "see": "sehe siehst sieht sehen seht sehen",
    "take": "nehme nimmst nimmt nehmen nehmt nehmen", "find": "finde findest findet finden findet finden",
    "want": "will willst will wollen wollt wollen", "have": "habe hast hat haben habt haben",
    "think": "denke denkst denkt denken denkt denken", "say": "sage sagst sagt sagen sagt sagen",
    "know": "weiß weißt weiß wissen wisst wissen", "give": "gebe gibst gibt geben gebt geben",
}
DE_PAST = {
    "go": "ging gingst ging gingen gingt gingen", "come": "kam kamst kam kamen kamt kamen",
    "do": "tat tatest tat taten tatet taten", "see": "sah sahst sah sahen saht sahen",
    "take": "nahm nahmst nahm nahmen nahmt nahmen", "find": "fand fandest fand fanden fandet fanden",
    "want": "wollte wolltest wollte wollten wolltet wollten",
    "have": "hatte hattest hatte hatten hattet hatten",
    "think": "dachte dachtest dachte dachten dachtet dachten",
    "say": "sagte sagtest sagte sagten sagtet sagten",
    "know": "wusste wusstest wusste wussten wusstet wussten", "give": "gab gabst gab gaben gabt gaben",
}
# el aorist (simple past): 3s, 1p, 3p — single words; future needs θα (multiword).
EL_AOR = {
    "go": "πήγε πήγαμε πήγαν", "come": "ήρθε ήρθαμε ήρθαν", "do": "έκανε κάναμε έκαναν",
    "see": "είδε είδαμε είδαν", "take": "πήρε πήραμε πήραν", "find": "βρήκε βρήκαμε βρήκαν",
    "say": "είπε είπαμε είπαν", "give": "έδωσε δώσαμε έδωσαν",
}

# cs / pl: ONLY simple future (fut) and present perfect (perf). No aspect-based
# stand-ins for futperf / pluperf / progressive. P6 order (2p = vy / wy).
# fut: perfective future (single word) or budu / będę + infinitive where the
# perfective is not a plain future (want / know / have …). Gender-neutral.
CS_FUT = {
    "go": "půjdu půjdeš půjde půjdeme půjdete půjdou",
    "come": "přijdu přijdeš přijde přijdeme přijdete přijdou",
    "do": "udělám uděláš udělá uděláme uděláte udělají",
    "see": "uvidím uvidíš uvidí uvidíme uvidíte uvidí",
    "take": "vezmu vezmeš vezme vezmeme vezmete vezmou",
    "find": "najdu najdeš najde najdeme najdete najdou",
    "say": "řeknu řekneš řekne řekneme řeknete řeknou",
    "give": "dám dáš dá dáme dáte dají",
}
CS_INF = {"want": "chtít", "have": "mít", "think": "myslet", "know": "vědět"}
CS_BUDU = _p6("budu budeš bude budeme budete budou")
PL_FUT = {
    "go": "pójdę pójdziesz pójdzie pójdziemy pójdziecie pójdą",
    "come": "przyjdę przyjdziesz przyjdzie przyjdziemy przyjdziecie przyjdą",
    "do": "zrobię zrobisz zrobi zrobimy zrobicie zrobią",
    "see": "zobaczę zobaczysz zobaczy zobaczymy zobaczycie zobaczą",
    "take": "wezmę weźmiesz weźmie weźmiemy weźmiecie wezmą",
    "find": "znajdę znajdziesz znajdzie znajdziemy znajdziecie znajdą",
    "think": "pomyślę pomyślisz pomyśli pomyślimy pomyślicie pomyślą",
    "say": "powiem powiesz powie powiemy powiecie powiedzą",
    "give": "dam dasz da damy dacie dadzą",
}
PL_INF = {"want": "chcieć", "have": "mieć", "know": "wiedzieć"}
PL_BEDE = _p6("będę będziesz będzie będziemy będziecie będą")
# perf: l-participle past (masc. sg, masc.-personal pl) — the Slavic past
# carries GENDER. Used only for gender-unspecified pronoun subjects
# (I / you / we / they, generic masculine); never for he/she/it (forms diverge
# across the parity class: šel/šla/šlo), demonstratives or relatives (referent
# gender / animacy unknown). pl person endings -łem/-łeś/-liśmy/-liście;
# cs aux jsem/jsi/jsme/jste (3p bare).
CS_LPART = {
    "go": "šel šli", "come": "přišel přišli", "do": "udělal udělali", "see": "viděl viděli",
    "take": "vzal vzali", "find": "našel našli", "want": "chtěl chtěli", "have": "měl měli",
    "think": "myslel mysleli", "say": "řekl řekli", "know": "věděl věděli", "give": "dal dali",
}
CS_JSEM = {"1s": "jsem", "2s": "jsi", "1p": "jsme", "2p": "jste", "3p": ""}
PL_LPART = {
    "go": "poszedł poszli", "come": "przyszedł przyszli", "do": "zrobił zrobili",
    "see": "zobaczył zobaczyli", "take": "wziął wzięli", "find": "znalazł znaleźli",
    "want": "chciał chcieli", "have": "miał mieli", "think": "pomyślał pomyśleli",
    "say": "powiedział powiedzieli", "know": "wiedział wiedzieli", "give": "dał dali",
}
SLAVIC_GENDERED = "gendered-past"


def _slavic(verb: str, tense: str, slot: str) -> list[tuple[str, str, str]]:
    """(form, lang, shape) cs/pl candidates for fut / perf at a P6 slot."""
    out: list[tuple[str, str, str]] = []
    i = P6.index(slot)
    if tense == "fut":
        if verb in CS_FUT:
            out.append((CS_FUT[verb].split()[i], "cs", "pf-future"))
        else:
            out.append((f"{CS_BUDU[slot]} {CS_INF[verb]}", "cs", "budu-inf"))
        if verb in PL_FUT:
            out.append((PL_FUT[verb].split()[i], "pl", "pf-future"))
        else:
            out.append((f"{PL_BEDE[slot]} {PL_INF[verb]}", "pl", "bede-inf"))
    elif tense == "perf" and slot not in ("3s", "3p"):
        sg, pl = CS_LPART[verb].split()
        part = pl if slot.endswith("p") else sg
        aux = CS_JSEM[slot]
        out.append((f"{part} {aux}".strip(), "cs", SLAVIC_GENDERED))
        sg, pl = PL_LPART[verb].split()
        end = {"1s": "em", "2s": "eś", "1p": "śmy", "2p": "ście", "3p": ""}[slot]
        out.append(((pl if slot.endswith("p") else sg) + end, "pl", SLAVIC_GENDERED))
    return out


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
    # after apply_relative_que: relative slot rewritten to neutral 'que';
    # the EN verb still marks number (is/was/has → sg, are/were/have → pl).
    ("rel-que-sg", "que", "3s", "sg", True, "rel"),
    ("rel-que-pl", "que", "3p", "pl", True, "rel"),
]
# Parity classes: subjects sharing one conjugation slot (same person key, kind,
# subject handling). The verb winner is decided once per class so he/she/it
# (or these/those, who/which) never diverge on subject-length tie-breaks.
def _parity_class(sub: tuple) -> tuple:
    label, _surf, person, num, _keep, kind = sub
    # number-following classes: 3sg = he/she/it/this, 3pl = they/these/those.
    # Relatives keep their own (number-gated) handling; 'that' never converts.
    if kind == "pron" and person in ("3s", "3p"):
        return (person, num)
    return (label,)


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
        # de / nl: EN `you` uses only the singular du / jij slot; plural ihr /
        # jullie forms (denkt, deden, hadden, wisten) break singular-you parity.
        dn = not (person == "2" and slot != "2s")
        # nl
        nl_pres = NL_PRES[verb].split()
        nl_past = NL_PAST[verb].split()
        nl_i = {"1s": 0, "2s": 1, "3s": 1}.get(slot, 2)
        if dn and tense == "pres":
            add(nl_pres[nl_i], "nl", "simple", tag)
        if dn and tense == "past":
            add(nl_past[0 if nl_i < 2 else 1], "nl", "simple", tag)
        if dn and tense == "perf":
            # nl preterite for EN present perfect (same policy as es/pt preterite)
            add(nl_past[0 if nl_i < 2 else 1], "nl", "simple-preterite", tag)
        if dn and tense in PROG:
            zijn = NL_ZIJN[tense].split()[{"1s": 0, "2s": 1, "3s": 2}.get(slot, 3)]
            tail = " zijn" if tense == "futprog" else ""
            add(f"{zijn} aan het {nl_pres[2]}{tail}", "nl", "prog-aan-het", tag)
        # de (Präsens / Präteritum; slot 2s = du, 2p = ihr, usted-slot 3s/3p = er/sie)
        if dn and tense in ("pres", "past"):
            de = (DE_PRES if tense == "pres" else DE_PAST)[verb].split()[P6.index(slot)]
            add(de, "de", "simple", tag)
        if dn and tense == "perf":
            # de Präteritum for EN present perfect (same policy as es/pt preterite)
            add(DE_PAST[verb].split()[P6.index(slot)], "de", "simple-preterite", tag)
        # cs / pl (fut, perf only)
        if tense in ("fut", "perf"):
            for f, L, shape in _slavic(verb, tense, slot):
                add(f, L, shape, tag)
        # el aorist
        if tense == "past" and verb in EL_AOR and slot in ("3s", "1p", "3p"):
            add(EL_AOR[verb].split()[("3s", "1p", "3p").index(slot)], "el", "simple", tag)
    seen: set[str] = set()
    uniq = []
    for c in out:
        # de 2p (ihr) often equals 3s (er): keep the genuine 2nd-person copy too,
        # so the usted filter below does not drop the ihr form with its 3s twin.
        k = (c["form"], c["lang"], c["number"] if c["lang"] == "de" else "")
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


# Function words that occupy a spelling in a candidate language (article /
# pronoun / preposition). A verb candidate spelled like one would read as that
# word (de ``das`` article vs es ``das`` "you give").
FUNCTION_WORDS: dict[str, str] = {
    "de": "der die das dem den des ein eine einen einem einer es sie er wir ihr ich du",
    "nl": "de het een ik jij je hij zij ze wij we jullie",
    "es": "el la los las un una yo tú él ella nosotros que de en",
    "pt": "o a os as um uma eu tu ele ela nós que de em",
    "it": "il lo la gli le un una io tu lui lei noi che di in",
    "fr": "le la les un une je tu il elle nous vous ils elles que de en",
}

_CONJ_CLS = {"pres": "pres", "imperf": "past", "pret": "past", "plpf": "plpf", "fut": "fut"}


def form_registry(conj: dict) -> dict[str, set[tuple[str, str, str]]]:
    """Map lowercased spelling → {(lang, meaning-verb, tense-class)} across every table.

    Generalizes the old cs/pl-only look-alike check: any language's candidate is
    tested against everything already registered for every language.
    """
    reg: dict[str, set[tuple[str, str, str]]] = defaultdict(set)

    def put(form: str, lang: str, verb: str, cls: str) -> None:
        reg[form.lower()].add((lang, verb, cls))

    for L in ("es", "pt", "it", "fr"):
        by_inf = {VERBS[v][L]: v for v in VERBS}
        for inf, tenses in conj[L].items():
            v = by_inf.get(inf, f"?{inf}")
            put(inf, L, v, "inf")
            for tk, slots in tenses.items():
                for f in slots.values():
                    put(f, L, v, _CONJ_CLS.get(tk, tk))
        for v, f in PP[L].items():
            put(f, L, v, "pp")
    for L, g in GER.items():
        for v, f in g.items():
            put(f, L, v, "ger")
    for L, tab, cls in (("nl", NL_PRES, "pres"), ("nl", NL_PAST, "past"),
                        ("de", DE_PRES, "pres"), ("de", DE_PAST, "past"),
                        ("el", EL_AOR, "past"), ("cs", CS_FUT, "fut"), ("pl", PL_FUT, "fut"),
                        ("cs", CS_INF, "inf"), ("pl", PL_INF, "inf"),
                        ("cs", CS_LPART, "lpart"), ("pl", PL_LPART, "lpart")):
        for v, forms in tab.items():
            for f in forms.split():
                put(f, L, v, cls)
    for (L, key), slots in AUX.items():
        for f in slots.values():
            put(f, L, _aux_meaning(L, key), "aux")
    for key, forms in NL_ZIJN.items():
        for f in forms.split():
            put(f, "nl", _aux_meaning("nl", key), "aux")
    for L, slots in (("cs", CS_BUDU), ("pl", PL_BEDE), ("cs", CS_JSEM)):
        for f in slots.values():
            if f:
                put(f, L, "will" if slots is not CS_JSEM else "be", "aux")
    for L, ws in FUNCTION_WORDS.items():
        for w in ws.split():
            put(w, L, "<func>", "func")
    return reg


def _aux_meaning(lang: str, key: str) -> str:
    """Meaning of an auxiliary table: have (perfect aux), be (essere / être / estar /
    stare / zijn), will (nl zal / zullen)."""
    if lang == "nl" and key == "futprog":
        return "will"
    if key.endswith("+e") or key in PROG:
        return "be"
    return "have"


_SHAPE_CLS = {
    "simple-preterite": "past", "simple-pluperfect": "plpf", "compound": "pp",
    "prog-gerund": "ger", "prog-a-inf": "inf", "prog-en-train-de": "inf",
    "prog-aan-het": "inf", "budu-inf": "inf", "bede-inf": "inf",
    "pf-future": "fut", SLAVIC_GENDERED: "lpart",
}


def candidate_head(c: dict, tense: str) -> tuple[str, str]:
    """(lexical-verb token, tense-class) of a candidate before subject keeping."""
    toks = c["form"].split()
    shape = c["shape"]
    if shape == SLAVIC_GENDERED:
        head = toks[0]
    elif shape == "prog-aan-het":
        head = toks[toks.index("het") + 1]
    elif shape == "prog-en-train-de":
        head = toks[-1].split("'")[-1]
    else:
        head = toks[-1]
    cls = _SHAPE_CLS.get(shape) or {"pres": "pres", "fut": "fut", "past": "past"}.get(tense, tense)
    return head.lower(), cls


def collision(c: dict, tense: str, verb: str, reg: dict) -> list[tuple[str, str, str]]:
    """Registered readings of the candidate's head token that clash with its meaning.

    Clash = a different verb / function word (any language), or a different
    language with a different tense class (nl ``kom`` 'I come' vs Nordic past
    ``kom`` 'came'), unless the candidate's own language already has that
    reading for the spelling. Same-language same-verb syncretism (es
    ``tomamos`` present = preterite) and cross-language same-meaning twins
    (es/pt ``tomamos``) are not clashes.
    """
    head, cls = candidate_head(c, tense)
    readings = reg.get(head, set())
    # tense classes the candidate's own language already gives this spelling
    # (es ``tomamos`` = present AND preterite): a foreign twin adds no new ambiguity.
    own = {k for lang, v, k in readings if lang == c["lang"] and v == verb} | {cls}
    # a head that follows an auxiliary / periphrasis (``aurai eu``, ``estoy yendo``)
    # is a participle / gerund / infinitive slot, never a standalone article or
    # pronoun: function-word readings only clash for single-word forms.
    bound = len(c["form"].split()) > 1
    out = []
    for lang, v, k in sorted(readings):
        if bound and v == "<func>":
            continue
        if v != verb or (lang != c["lang"] and k not in own):
            out.append((lang, v, k))
    for tok in candidate_aux(c):
        out.extend(aux_collision(tok, c["lang"], reg))
    return out


# fixed periphrasis particles per shape (pt estar a, fr en train de, nl aan het):
# function words by construction, not auxiliaries. Only stripped for their own
# shape (fr aux ``a`` in ``a vu`` is an auxiliary and is checked).
_PERIPHRASIS_PARTICLES = {
    "prog-a-inf": frozenset({"a"}),
    "prog-en-train-de": frozenset({"en", "train", "de", "d"}),
    "prog-aan-het": frozenset({"aan", "het"}),
}


def candidate_aux(c: dict) -> list[str]:
    """Auxiliary tokens of a multi-word candidate (everything but the head and
    the fixed periphrasis particles), lowercased."""
    toks = [t.lower() for t in re.split(r"[ ']", c["form"]) if t]
    if len(toks) < 2:
        return []
    head, _ = candidate_head(c, "pres")
    rest = list(toks)
    rest.remove(head)
    skip = _PERIPHRASIS_PARTICLES.get(c.get("shape", ""), frozenset())
    return [t for t in rest if t not in skip]


def aux_collision(tok: str, lang: str, reg: dict) -> list[tuple[str, str, str]]:
    """Readings that clash with an auxiliary token of ``lang``.

    The auxiliary's meanings are those its own language registers for the
    spelling (it ``ho`` = have aux and lexical have). Another language's reading
    clashes when it means something else: a function word (fr aux ``a`` vs pt
    article ``a``) or a different verb (es aux ``está`` is fine everywhere it
    means be). Same-meaning twins across languages / classes are not clashes.
    """
    readings = reg.get(tok, set())
    own = {v for L, v, _k in readings if L == lang}
    if not own:
        return []
    return [(L, v, k) for L, v, k in sorted(readings) if L != lang and v not in own]


# Conversion-time banks audited with the same registry (bank name → loader name).
AUDITED_BANKS = {
    "es_fr_tense": "load_es_fr_tense_bank",
    "pt_el_latin_tense": "load_pt_el_latin_tense_bank",
    "zh_de_phrases": "load_zh_de_phrase_bank",
    "pt_el_latin_phrases": "load_pt_el_latin_phrase_bank",
}
_BANK_TENSE_CLS = {"present": "pres", "future": "fut", "past": "past", "conditional": "cond"}


def bank_form_collision(form: str, lang: str, meanings: set[str], cls: str,
                        reg: dict) -> list[tuple[str, str, str]]:
    """Registry clashes of a conversion-time bank form (every token checked).

    ``meanings`` = verbs named by the entry id (``want-go-pres-1s`` → want, go);
    phrase banks pass ``{"<phrase>"}``. A token clashes with a reading of another
    meaning (different verb / function word) or, for the same meaning in another
    language, a tense class its own language lacks (same rule as ``collision``).
    The token's own-language readings count as its meanings, so a form whose
    auxiliary / particle is a native function word (pt ``de novo``) is fine.
    Single-word forms also clash with an own-language reading of another verb
    (pt ``via`` = ``ver`` imperfect). Multi-word forms skip function-word
    readings (same exemption as the matrix: a bound token is never a standalone
    article / pronoun).
    """
    toks = [w for w in re.split(r"[ ']", form.lower()) if w]
    bound = len(toks) > 1
    out: list[tuple[str, str, str]] = []
    for tok in toks:
        readings = reg.get(tok, set())
        own_v = {v for L, v, _k in readings if L == lang} | meanings
        own_k = {k for L, _v, k in readings if L == lang} | {cls}
        for L, v, k in sorted(readings):
            if bound and v == "<func>":
                continue
            if L == lang:
                if not bound and v not in meanings and v != "<func>":
                    out.append((L, v, k))
                continue
            if v not in own_v or (v in meanings and k not in own_k):
                out.append((L, v, k))
    return out


def audit_banks(t, reg: dict) -> list[dict]:
    """Conversion-time bank candidates that collide (generated into the matrix bank
    as ``collision_blocked``; runtime ``_bank_phrase_pairs`` skips them)."""
    out: list[dict] = []
    for bank, loader in AUDITED_BANKS.items():
        for e in getattr(t, loader)()["entries"]:
            eid = str(e.get("id") or "")
            if bank.endswith("_tense"):
                meanings = {w for w in eid.split("-") if w in VERBS} or {eid.split("-")[0]}
                cls = _BANK_TENSE_CLS.get(str(e.get("tense") or ""), "pres")
            else:
                meanings, cls = {"<phrase>"}, "phrase"
            srcs = {str(x).lower() for x in e.get("from") or []}
            for form, lang in t._entry_candidate_forms(e):
                if form.lower() in srcs:  # EN kept as-is (identity row), nothing to read
                    continue
                hit = bank_form_collision(form, lang, meanings, cls, reg)
                if hit:
                    out.append({"bank": bank, "id": eid, "form": form, "lang": lang,
                                "readings": [list(r) for r in hit]})
    return out


def _existing_sources(t) -> set[str]:
    srcs: set[str] = set()
    for loader in (t.load_es_fr_tense_bank, t.load_pt_el_latin_tense_bank):
        for e in loader()["entries"]:
            for s in e.get("from") or []:
                for v in t._subject_aux_variants(str(s)):
                    srcs.add(v.lower())
    return srcs


_ENC = None


def o200k_tokens(s: str) -> int:
    """Real o200k_base token count, scored mid-sentence (leading space).
    Build-time only (uv dev group); runtime tessera_talk never imports tiktoken."""
    global _ENC
    if _ENC is None:
        import tiktoken

        _ENC = tiktoken.get_encoding("o200k_base")
    return len(_ENC.encode(" " + s))


_EN_CONTRACT = [
    (r"\b(I|you|we|they|who) have\b", r"\1've"), (r"\b(he|she|it|who|that) has\b", r"\1's"),
    (r"\b(I|you|we|they|he|she|it|who|that) will\b", r"\1'll"),
    (r"\b(I|you|we|they|he|she|it|who) had\b", r"\1'd"),
    (r"\bI am\b", "I'm"), (r"\b(you|we|they|who) are\b", r"\1're"),
    (r"\b(he|she|it|who|that) is\b", r"\1's"),
]


def en_baselines(src: str) -> list[str]:
    """EN source plus its contracted spellings (we've, they're, I'll ...)."""
    out = [src]
    for pat, rep in _EN_CONTRACT:
        v = re.sub(pat, rep, out[0], count=1)
        if v != out[0]:
            out.append(v)
    return out


ROUNDTRIP_ENFORCED_LANGS = frozenset({"nl"})
_RT_DATA: dict = {}


def _rt_ok(form: str, lang: str, gate=None) -> bool:
    if lang in ROUNDTRIP_ENFORCED_LANGS:
        sys.path.insert(0, str(ROOT / "scripts"))
        import roundtrip as rt

        if rt.status(_RT_DATA.setdefault("d", rt.load()), lang, form) != "pass":
            return False
    return gate is None or gate(form, lang)


def build(gate=None) -> tuple[dict, dict, str]:
    """Rebuild bank / report / md. ``gate(form, lang) -> bool`` (optional) drops
    candidates before ranking — used by scripts/roundtrip.py impact reports only;
    the committed bank is always built with ``gate=None`` (report-only).

    Exception (#29): languages in ``ROUNDTRIP_ENFORCED_LANGS`` (nl, <100M speakers)
    are always gated — a form is adopted only when its recorded AI round-trip status
    is ``pass`` (restore rate >= lt100m threshold 0.9); unverified forms are dropped."""
    from tests._helpers import load

    _RT_DATA.clear()
    t = load("tessera_talk", "TesseraTalk/tessera_talk.py")
    conj = json.loads(CONJ_PATH.read_text(encoding="utf-8"))["conj"]
    existing = _existing_sources(t)
    reg = form_registry(conj)
    tok = o200k_tokens
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
                if keep or person in ("3s", "3p"):
                    # gendered Slavic past: only for gender-unspecified pronouns
                    cands = [c for c in cands if c["shape"] != SLAVIC_GENDERED]
                # cross-language collision guard (all languages): a candidate whose
                # lexical-verb token is already registered with another meaning
                # (pl ``da`` = es/it/pt "gives", de ``das`` article) is dropped (揺らぎ回避).
                xl = {c["form"]: collision(c, tense, verb, reg) for c in cands}
                xl = {f: v for f, v in xl.items() if v}
                if xl:
                    cell["crossling_dropped"] = sorted(xl)
                    cands = [c for c in cands if c["form"] not in xl]
                if keep:
                    for c in cands:
                        c["form"] = f"{surf} {c['form']}"
                if True:  # nl always gated (#29); others only with an explicit gate
                    # gate per (form, lang): nl ``denkt`` failing must not drop de ``denkt``
                    gated = [c for c in cands if not _rt_ok(c["form"], c["lang"], gate)]
                    if gated:
                        cell["roundtrip_gated"] = [c["form"] for c in gated]
                        cands = [c for c in cands if c not in gated]
                en_best = min(en_baselines(src), key=lambda f: (tok(f), u8(f)))
                st, su = tok(en_best), u8(en_best)
                cell["en_best"] = en_best
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
                if person == "2" and cands:
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
                    cands,
                    key=lambda c: (tok(c["form"]), u8(c["form"]), len(c["form"]), c["form"]),
                )
                # exact (token, utf8) tie rules (runtime twin: tessera_talk.prefer_on_tie):
                # de over nl; es/fr/pt over it/cs/pl.
                pick = t.prefer_on_tie(
                    (scored[0]["form"], scored[0]["lang"]),
                    [(c["form"], c["lang"]) for c in scored],
                    lambda f: (tok(f), u8(f)),
                )
                if pick != (scored[0]["form"], scored[0]["lang"]):
                    w = next(c for c in scored if (c["form"], c["lang"]) == pick)
                    scored.remove(w)
                    scored.insert(0, w)
                best = scored[0]
                cell.update(
                    best=best["form"], lang=best["lang"], shape=best["shape"], number=best["number"],
                    tok=[st, tok(best["form"])], utf8=[su, u8(best["form"])],
                )
                shrink = [c for c in scored if (tok(c["form"]), u8(c["form"])) < (st, su)]
                cell["_pending"] = {
                    "src": src, "label": label, "best": best, "scored": scored, "kind": kind,
                    "num_key": (person, num), "keepc": shrink, "st": st, "su": su,
                    "homo_shrinks": any((tok(h["form"]), u8(h["form"])) < (st, su) for h in homo),
                    "cls": _parity_class(sub),
                }
    # class-level decision: adopt iff for EVERY member token strictly shrinks and
    # utf8 never grows, and utf8 strictly shrinks for at least one member
    # (singleton class == the plain strict token AND utf8 rule).
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in cells:
        if "_pending" in c:
            groups[(c["_pending"]["cls"], c["tense"], c["verb"])].append(c)
    # pronoun classes first; demonstratives (this / these, those) then reuse the
    # number-matched pronoun verb winner with their subject kept.
    order = sorted(groups.items(), key=lambda kv: kv[1][0]["_pending"]["kind"] == "dem")
    class_verb: dict[tuple, str | None] = {}
    for (_cls, tense, verb), members in order:
        p0 = members[0]["_pending"]
        if p0["kind"] == "dem" and (p0["num_key"], tense, verb) in class_verb:
            c = members[0]
            p = c.pop("_pending")
            vw = class_verb[(p0["num_key"], tense, verb)]
            head = p["src"].split(" ", 1)[0]
            hit = [k for k in p["scored"] if vw and k["form"] == f"{head} {vw}"]
            if hit and (tok(hit[0]["form"]), u8(hit[0]["form"])) < (p["st"], p["su"]):
                b = hit[0]
                c.update(status="adopt", best=b["form"], lang=b["lang"], shape=b["shape"], number=b["number"],
                         tok=[p["st"], tok(b["form"])], utf8=[p["su"], u8(b["form"])], parity_verb=vw)
                c["_entry"] = {
                    "id": f"mx-{verb}-{tense}-{p['label']}", "from": [p["src"]], "to": b["form"],
                    "lang": b["lang"], "tense": tense, "subject": p["label"],
                    "candidates": [{"form": b["form"], "lang": b["lang"]}], "scored_by": "o200k_base",
                }
            elif vw:
                c.update(status="reject", parity_verb=vw,
                         reason="parity: number-matched pronoun verb winner does not shrink with subject kept (EN kept)")
            else:
                c.update(status="reject", reason="parity: number-matched pronouns stay EN (EN kept)")
            continue
        def ok(c):
            p = c["_pending"]
            return (tok(p["best"]["form"]), u8(p["best"]["form"])) < (p["st"], p["su"])
        oks = [ok(c) for c in members]
        adopt = all(oks)
        if p0["kind"] == "pron" and p0["num_key"][0] in ("3s", "3p"):
            class_verb[(p0["num_key"], tense, verb)] = p0["best"]["form"] if adopt else None
        for c in members:
            p = c.pop("_pending")
            best = p["best"]
            if adopt:
                c["status"] = "adopt"
                if len(members) > 1:
                    c["parity_class"] = [m["subject"] for m in members]
                c["_entry"] = (
                    {
                        "id": f"mx-{verb}-{tense}-{p['label']}",
                        "from": [p["src"]],
                        "to": best["form"],
                        "lang": best["lang"],
                        "tense": tense,
                        "subject": p["label"],
                        "candidates": [{"form": best["form"], "lang": best["lang"]}],
                        "scored_by": "o200k_base",
                    }
                )
            elif p["homo_shrinks"]:
                c.update(status="reject", reason="EN homograph collision: every shrinking candidate spells an English word")
            elif len(members) > 1 and any(oks) and not all(oks):
                c.update(status="reject", reason="parity class: not every subject in the class shrinks (EN kept for all)")
            elif tense in PROG:
                c.update(status="reject", reason="no progressive-preserving candidate shrinks both token and utf8 (EN kept)")
            else:
                c.update(status="reject", reason="no candidate shrinks both token and utf8")
    entries.extend(c.pop("_entry") for c in cells if "_entry" in c)
    bank = {
        "version": 1,
        "title": "Person × tense matrix bank (generated by scripts/tense_matrix.py)",
        "notes": [
            "Generated — edit scripts/tense_matrix.py, not this file.",
            "Adopted only when token AND utf8 strictly shrink; `to` = runtime cheapest winner.",
            "Parity by number (3sg: he/she/it/this, 3pl: they/these/those): he/she/it decided as one class; this/these/those reuse the number-matched pronoun verb winner with subject kept, or stay EN; relatives/that unchanged: decided once per class — every member token-shrinks, utf8 never grows, ≥1 member utf8-shrinks; same verb winner for all.",
            "Personal pronouns dropped (person-marked verb); demonstratives/relatives keep the subject.",
            "Relatives only with number-marking aux (is/are, has/have, was/were); bare 'that' (multi-POS) always stays EN.",
            "EN-homograph guard: candidates with a token spelled like an English word (fixtures/en_wordlist.txt) are dropped; next-cheapest unique form wins.",
            "Progressive: only progressive-preserving periphrases (estar/stare + gerund, estar a + inf, être en train de, aan het); no simple-tense fallback.",
            "de (Präsens/Präteritum, du/ihr, never Sie) competes; de wins (tokens, utf8) ties against nl, nl kept only when strictly cheaper.",
            "cs/pl: simple future (perfective or budu/będę + inf) and present perfect only (l-participle, generic masculine, pronouns I/you/we only — never he/she/it, they, demonstratives, relatives); no aspect stand-ins for futperf/pluperf/progressive.",
            "Exact (token, utf8) tie: es/fr/pt preferred over it/cs/pl (wider readership).",
            "you: usted/ustedes measured but excluded (3rd-person forms collapse into he/they after subject drop); tú vs vosotros/vous compete.",
            "Collision guard also checks auxiliary tokens (fr a/as, es/it sei …; participle after an aux still exempt from article/pronoun readings) and audits the conversion-time banks (es_fr_tense, pt_el_latin_tense, zh_de_phrases, pt_el_latin_phrases): `collision_blocked` rows are skipped at runtime, next-cheapest candidate wins.",
            "you → U at runtime (tessera_talk.apply_you_u, after these rows): same tokens, utf8 3→1. A matrix row strictly drops tokens so it always beats U + EN chain; guarded / rejected cells become U + EN chain (your/yours/yourself, you'X excluded).",
        ],
        "entries": entries,
        "collision_blocked": audit_banks(t, reg),
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
