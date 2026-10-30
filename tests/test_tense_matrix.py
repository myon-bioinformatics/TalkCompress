"""Person × tense matrix bank (scripts/tense_matrix.py) — runtime + guards."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tense_matrix as tm  # noqa: E402

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))
ENTRIES = BANK["entries"]
CELLS = REPORT["cells"]
_CELL_BY_ID = {f"mx-{c['verb']}-{c['tense']}-{c['subject']}": c for c in CELLS}


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_generator_outputs_up_to_date():
    r = subprocess.run(
        [sys.executable, "scripts/tense_matrix.py", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_matrix_covers_all_subjects_and_tenses():
    subs = {c["subject"] for c in CELLS}
    tenses = {c["tense"] for c in CELLS}
    for s in ("1s", "2", "3s-he", "3s-she", "3s-it", "1p", "3p", "dem-this", "dem-that",
              "dem-these", "dem-those", "rel-who-sg", "rel-who-pl", "rel-which-sg", "rel-which-pl"):
        assert s in subs
    assert tenses == {"pres", "fut", "past", "perf", "futperf", "pluperf", "presprog", "pastprog", "futprog"}
    assert {c["status"] for c in CELLS} <= {"adopt", "existing", "reject"}
    assert all(c.get("reason") for c in CELLS if c["status"] == "reject")
    assert sum(c["status"] == "adopt" for c in CELLS) == len(ENTRIES)


@pytest.mark.parametrize("e", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_matrix_to_is_runtime_winner_and_shrinks(e):
    t = _t()
    for src in e["from"][:1]:
        out = t.apply_es_fr_tense(src)
        assert out == e["to"], (src, out)
        # o200k_base (leading space): strictly beats EN's cheapest spelling
        # (contractions included) on (tokens, utf8).
        en = min(tm.en_baselines(src), key=lambda f: (tm.o200k_tokens(f), len(f.encode())))
        assert (tm.o200k_tokens(out), len(out.encode())) < (tm.o200k_tokens(en), len(en.encode()))
        assert t.apply_es_fr_tense(src) == out  # deterministic
        if e["subject"].startswith(("dem-", "rel-")):
            assert out.split(" ", 1)[0].lower() == src.split(" ", 1)[0].lower()


@pytest.mark.parametrize(
    "s",
    [
        "his will to go", "the will to go is strong", "That said, we left.", "this saw cuts",
        "he does not go", "he had eaten", "he will have eaten", "that is going well",
        "he is going to see", "who will go", "that will go", "which will go",
        "the good will he had", "a will to win", "those saw blades",
    ],
)
def test_negative_no_misfire(s):
    assert _t().apply_es_fr_tense(s) == s


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("This has gone well", "This foi well"),
        # "van" is an EN word → guard drops it; no other progressive form shrinks.
        ("People who are going home", "People who are going home"),
        ("I'm going to buy it", "compraré it"),
    ],
)
def test_subject_kept_and_goingto(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_second_person_only_true_2nd_forms():
    two = [c for c in CELLS if c["subject"] == "2" and c["status"] == "adopt"]
    assert two and all(c["number"] in ("2sg-tú", "2pl-vosotros/vous", "2-neutral") for c in two)
    # usted would win more cells, but collapses into 3sg after subject drop.
    ust = Counter(c["usted_style_best"]["number"] for c in CELLS if "usted_style_best" in c)
    assert ust["2sg-usted"] > ust["2sg-tú"]


def test_no_token_increase_on_sentences():
    t = _t()
    for c in CELLS:
        s = f"{c['src']} today."
        o = t.apply_es_fr_tense(s)
        assert tm.o200k_tokens(o) <= tm.o200k_tokens(s), (s, o)


# --- EN-homograph guard ----------------------------------------------------


def test_en_wordlist_loaded_and_deterministic():
    t = _t()
    wl = t.load_en_wordlist()
    assert isinstance(wl, frozenset) and len(wl) > 50000
    for w in ("he", "fora", "van", "a", "was", "en", "train", "vi", "soy", "sou", "vim", "that"):
        assert w in wl, w
    for w in ("es", "sera", "vas", "di", "sto", "estou", "indo", "dou", "kwam", "vis"):
        assert w not in wl, w
    assert t.load_en_wordlist() is wl


@pytest.mark.parametrize(
    ("form", "want"),
    [("he visto", ["he"]), ("fora", ["fora"]), ("van", ["van"]), ("estava a ir", ["a"]),
     ("estou indo", []), ("He", ["he"])],
)
def test_en_homograph_tokens(form, want):
    assert _t().en_homograph_tokens(form) == want


def test_en_homograph_tokens_keeps_subject_head():
    # Subject-kept rows (This foi …) must not be rejected for their EN head.
    assert _t().en_homograph_tokens("This foi", keep_head="this") == []


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("I give", "dou"),  # "do" (EN) dropped → next-cheapest unique
        ("I came", "kam"),  # vim / vine dropped → matrix de (kam ≺ kwam)
        ("I saw", "sah"),  # vi dropped → matrix de (sah ties vis, form order)
        ("I have seen it", "sah it"),  # de preterite (he visto dropped)
        ("I am", "I am"),  # sou / soy both EN → EN kept
    ],
)
def test_guard_falls_back_or_keeps_en(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_no_winner_spells_an_english_word():
    t = _t()
    for e in ENTRIES:
        head = e["from"][0].split(" ", 1)[0].lower()
        assert not t.en_homograph_tokens(e["to"], keep_head=head), e["id"]
    for src, dst, _lang in t.es_fr_tense_pairs():
        head = src.split(" ", 1)[0].lower()
        if t.apply_es_fr_tense(src) == dst:
            assert not t.en_homograph_tokens(dst, keep_head=head), (src, dst)


def test_runtime_never_emits_new_en_homograph():
    t = _t()
    for c in CELLS:
        out = t.apply_es_fr_tense(c["src"])
        if out == c["src"]:
            continue
        # Any EN word left in the output must come from the source (kept
        # subject / unconverted tail), never from a replacement.
        src_words = set(c["src"].lower().split())
        new = [w for w in t.en_homograph_tokens(out) if w not in src_words]
        assert not new, (c["src"], out, new)


def test_homograph_dropped_recorded_in_report():
    dropped = [c for c in CELLS if c.get("homograph_dropped")]
    assert dropped
    assert all(h["en"] for c in dropped for h in c["homograph_dropped"])


# --- that: multi-POS, never converted --------------------------------------


def test_that_cells_all_rejected():
    that = [c for c in CELLS if c["subject"] == "dem-that"]
    assert that and all(c["status"] == "reject" and "that" in c["reason"] for c in that)


@pytest.mark.parametrize("s", ["that has gone", "that is going well", "that went home", "that will be going"])
def test_that_left_unconverted(s):
    assert _t().apply_es_fr_tense(s) == s


# --- progressive keeps aspect ---------------------------------------------

_PROG_AUX = ("est", "sto", "sta", "ser", "suis", "es ", "ét", "sommes", "sont")  # estar/stare/être (+ zijn aan het)


def test_progressive_winners_are_periphrastic():
    prog = [c for c in CELLS if c["tense"].endswith("prog") and c["status"] == "adopt"]
    assert prog
    for c in prog:
        assert c["shape"].startswith("prog-"), c
        assert c["lang"] != "nl" or c["shape"] == "prog-aan-het", c
        assert " " in c["best"], c  # aux + gerund/inf, never a bare simple form
        body = c["best"].lower()
        if c["subject"].startswith(("dem-", "rel-")):  # subject kept: "this estará indo"
            body = body.split(" ", 1)[1]
            if c["subject"].startswith("rel-"):
                body = body.split(" ", 1)[1] if body.split(" ", 1)[0] in ("who", "which") else body
        assert body.startswith(_PROG_AUX), c


def test_progressive_hand_rows_not_simple_present():
    t = _t()
    for src in ("I'm going now.", "I'm reading now.", "I am coming", "we are going", "he was going"):
        out = t.apply_es_fr_tense(src)
        for simple in ("voy", "vou", "vengo", "leo", "leio", "vamos", "fui", "iba"):
            assert simple not in out.split(), (src, out)


@pytest.mark.parametrize(
    ("s", "want"),
    [("he was going", "estava indo"), ("I will be going", "estarei indo"),
     ("we will be doing", "estaremos fazendo")],
)
def test_progressive_examples(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_no_progressive_no_shrink_reason():
    rej = [c for c in CELLS if c["tense"].endswith("prog") and c["status"] == "reject"]
    assert any("progressive-preserving" in c["reason"] for c in rej)


_PARITY = {  # number-following classes: (pronouns, demonstratives)
    "3sg": (("3s-he", "3s-she", "3s-it"), ("dem-this",)),
    "3pl": (("3p",), ("dem-these", "dem-those")),
}


def _verb_part(c):
    if c["status"] != "adopt":
        return None
    f = c["best"]
    return f.split(" ", 1)[1] if c["subject"].startswith(("dem-", "rel-")) else f


@pytest.mark.parametrize("cls", sorted(_PARITY))
def test_parity_class_same_verb_winner(cls):
    """Same-number subjects share one verb winner: pronouns all-or-EN, demonstratives
    (subject kept) either reuse that verb form or stay EN — never a different form."""
    by = {(c["subject"], c["tense"], c["verb"]): c for c in CELLS}
    prons, dems = _PARITY[cls]
    bad = []
    for tense in sorted({c["tense"] for c in CELLS}):
        for verb in sorted({c["verb"] for c in CELLS}):
            pc = [by[(s, tense, verb)] for s in prons]
            if any(c["status"] == "existing" for c in pc):
                continue
            pv = {_verb_part(c) for c in pc}
            if len(pv) > 1:
                bad.append((tense, verb, "pron", pv))
                continue
            (w,) = pv
            for s in dems:
                dv = _verb_part(by[(s, tense, verb)])
                if dv is not None and dv != w:
                    bad.append((tense, verb, s, dv, w))
    assert not bad, bad


@pytest.mark.parametrize("subj", ["he", "she", "it"])
def test_3sg_is_doing_parity_runtime(subj):
    # o200k: EN "he's doing" (2 tok) is cheapest → EN kept for the whole 3sg class
    assert _t().apply_es_fr_tense(f"{subj} is doing") == f"{subj} is doing"


def test_that_stays_unconverted():
    assert all(c["status"] != "adopt" for c in CELLS if c["subject"] == "dem-that")


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("the man who is going", "the man who is going"),  # who≡que on cost; está indo hits 'indo' guard
        ("people who are going", "people who are going"),
        ("the book which was read", "the book que was read"),  # which (2 tok) → que (1 tok)
        ("people who went", "people who went"),  # number-neutral verb stays EN
        ("the man who has gone", "the man who foi"),  # has → sg
        ("the man that has seen it", "the man que sah it"),  # DET+NOUN+that → que, has → sg
        ("the fact that he left", "the fact that he left"),  # complementizer
        ("the proposition that all men are", "the proposition that all men are"),
        ("Who is going?", "Who is going?"),  # interrogative (no noun before) untouched
        ("that book is mine", "that book is mine"),  # determiner 'that'
    ],
)
def test_relative_que_runtime(src, want):
    assert _t().apply_es_fr_tense(src) == want


@pytest.mark.parametrize("s", ["I think that he left", "I know that is true", "so that we can", "that is it"])
def test_non_relative_that_unconverted(s):
    out = _t().apply_relative_que(s)
    assert out == s


def test_relative_number_from_en_verb():
    """que rows: sg only with is/was/has, pl only with are/were/have; neutral verbs reject."""
    for c in CELLS:
        if not c["subject"].startswith("rel-que") or c["status"] != "adopt":
            continue
        aux = c["src"].split()[1]
        assert c["tense"] in ("pres", "perf", "presprog", "pastprog"), c  # number-marking only
        if c["subject"].endswith("-sg"):
            assert aux in ("is", "was", "has") or (c["tense"] == "pres" and aux.endswith("s")), c
        else:
            assert aux in ("are", "were", "have") or (c["tense"] == "pres" and not aux.endswith("s")), c


def test_relative_connective_single_neutral_form():
    forms = [f for f, _ in _t().REL_QUE_FORMS]
    assert forms == ["que"]


# --- cs / pl (simple future + present perfect only) and tie preference ---------


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("they have gone", "foram"),  # cs/pl gendered past barred for 3pl (parity w/ these/those)
        ("he will take", "prendra"),  # o200k: fr 1 tok beats cs vezme
        ("she will take", "prendra"),  # he/she/it parity
        ("it will take", "prendra"),
        ("we will give", "damy"),  # pl perfective future
        ("you will give", "dasz"),
        ("these will give", "these dají"),
    ],
)
def test_cs_pl_wins(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_cs_pl_only_fut_and_perf_and_no_gendered_3s():
    for e in ENTRIES:
        if e["lang"] in ("cs", "pl"):
            assert e["tense"] in ("fut", "perf"), e["id"]
            if e["tense"] == "perf":
                # gendered l-participle: never he/she/it, demonstratives, relatives
                assert e["subject"] in ("1s", "2", "1p"), e["id"]


def test_no_crossling_homograph_for_slavic():
    # pl "da" (he will give) = es/it/pt "gives" → dropped
    assert _t().apply_es_fr_tense("he will give") != "da"


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("he will have seen", "terá visto"),  # ties it avrà visto → pt
        ("you go", "vas"),  # ties it vai → es
        ("I will be having", "estarei tendo"),
    ],
)
def test_tie_prefers_es_fr_pt_over_it(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_prefer_on_tie_rule():
    t = _t()
    # fixed metric: the rule is about ties, not about any estimator's numbers
    m = lambda f: ({"vezme": 1}.get(f, 2), len(f.encode()))  # noqa: E731
    assert t.prefer_on_tie(("avrà visto", "it"), [("avrà visto", "it"), ("terá visto", "pt")], m) == ("terá visto", "pt")
    assert t.prefer_on_tie(("vezme", "cs"), [("vezme", "cs"), ("tomará", "es")], m) == ("vezme", "cs")  # not a tie
    assert t.prefer_on_tie(("wil", "nl"), [("wil", "nl")], m) == ("wil", "nl")
