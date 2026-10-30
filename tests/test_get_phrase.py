"""Backlog: get+following unit, mid-sentence of course, look at symbol (o200k)."""
import re

import pytest

from tests._helpers import load, ns

tiktoken = pytest.importorskip("tiktoken")
ENC = tiktoken.get_encoding("o200k_base")


def score(text: str) -> tuple[int, int]:
    return len(ENC.encode(text)), len(text.encode("utf-8"))


def wins(new: str, old: str) -> bool:
    """o200k: fewer tokens; tie only with strictly fewer bytes."""
    (nt, nb), (ot, ob) = score(new), score(old)
    return nt < ot or (nt == ot and nb < ob)


m = load("morpho_zip", "MorphoZip/morpho_zip.py")
dz = load("density_zip", "DensityZip/density_zip.py")


def _literal(pat: re.Pattern[str]) -> str:
    return re.match(r"\\b([a-z ]+)\\b", pat.pattern).group(1)


def test_verb_units_measured_table_size():
    assert len(m.GET_PHRASES) == sum(len(f) for _, f, _ in m._VERB_UNITS) == 45


@pytest.mark.parametrize("pat,repl", m.GET_PHRASES)
def test_every_get_phrase_wins_on_o200k(pat, repl):
    src = _literal(pat)
    for ctx in (" {}", "We {} it.", "They {} soon."):
        assert wins(ctx.format(repl), ctx.format(src)), (src, repl, ctx)


def test_get_phrases_are_in_phrase_grammar_in_order():
    pg = m._PHRASE_GRAMMAR
    idx = [pg.index(r) for r in m.GET_PHRASES]
    assert idx == list(range(idx[0], idx[0] + len(idx)))


@pytest.mark.parametrize(
    "src,out",
    [
        ("Please get rid of the old logs.", "remove"),
        ("I will get in touch with him.", "contact him"),
        ("You will get used to it.", "adapt to it"),
        ("Let's get started.", "start."),
        ("They get married soon.", "marry soon"),
        ("It will get better.", "improve."),
        ("It will get better", "improve"),
        ("It will get better now", "improve now"),
        ("It might get worse and fail.", "worsen"),
        ("GET STARTED", "start"),
        ("We got rid of it.", "removed it"),
        ("She is getting better.", "improving."),
        ("It went wrong.", "failed."),
        ("We went back to the lab.", "returned to"),
        ("He has gone back home.", "returned home"),
        ("Things got worse", "worsened"),
    ],
)
def test_get_phrase_applied(src, out):
    assert out in m.apply_phrase_grammar(src)


@pytest.mark.parametrize(
    "src",
    [
        "Did you get better results?",  # get + adj + noun = obtain
        "It may get worse results.",
        "They get married to us.",  # marry to ≠ get married to
        "We went back on our word.",  # back on = renege
        "We got back in time.",
        "going on",  # ambiguous (happen/continue) → keep
        "went up",
        "get going",  # existing decision: keep get
        "get tired",
        "forget better",  # word boundary
    ],
)
def test_get_phrase_not_applied(src):
    assert m.apply_phrase_grammar(src) == src


def test_get_phrase_end_to_end_saves_tokens():
    for src in ("Please get rid of the old logs.", "It will get better."):
        out = dz.run_pipeline(["C", "E"], src, ns())
        assert score(out)[0] < score(src)[0], out


# --- of course mid-sentence: join (CamelCase etc.) vs paraphrase -------------
OC_CTX = ("He was, {}, late.", "It is {} fine.", "We {} agree.", "and {} it works")


def _total(form: str) -> tuple[int, int]:
    t = [score(c.format(form)) for c in OC_CTX]
    return sum(x for x, _ in t), sum(y for _, y in t)


def test_of_course_join_loses_to_paraphrase():
    sure = _total("sure")
    for joined in ("OfCourse", "ofCourse", "of_course", "of-course",
                   m.protect_join(("of", "course"))):
        assert _total(joined) > sure or _total(joined)[0] >= sure[0], joined
        assert not (_total(joined)[0] < sure[0])


def test_of_course_mid_sentence_paraphrased():
    out = m.apply_phrase_grammar("He was, of course, late.")
    assert out == "He was, sure, late."


# --- look at: symbol vs see -------------------------------------------------
LA_CTX = ("{} the logs", "Please {} this.", "{} me", "I will {} it later.")


@pytest.mark.parametrize("sym", ["👀", "👁", "👁️", "→", "⌕", "🔍"])
def test_look_at_symbol_does_not_beat_see(sym):
    for c in LA_CTX:
        assert not wins(c.format(sym), c.format("see")), (sym, c)


def test_look_at_at_sign_rejected_registered():
    # "@" ties/wins on bytes but is already registered for at/bei (PREP) → reject.
    assert m.PREP_CANONICAL.count("@") == 1
    assert "@" in m.PREP_CANONICAL


EXPECTED = {
    "rid of": ["remove", "removes", "removed", "removed", "removing"],
    "in touch with": ["contact", "contacts", "contacted", "contacted", "contacting"],
    "used to": ["adapt to", "adapts to", "adapted to", "adapted to", "adapting to"],
    "started": ["start", "starts", "started", "started", "starting"],
    "married": ["marry", "marries", "married", "married", "marrying"],
    "better": ["improve", "improves", "improved", "improved", "improving"],
    "worse": ["worsen", "worsens", "worsened", "worsened", "worsening"],
    "back": ["return", "returns", "returned", "returned", "returning"],
    "wrong": ["fail", "fails", "failed", "failed", "failing"],
}
GET_FORMS = ["get", "gets", "got", "gotten", "getting"]
GO_FORMS = ["go", "goes", "went", "gone", "going"]


@pytest.mark.parametrize("tail", list(EXPECTED))
def test_verb_unit_exact_table(tail):
    forms = GO_FORMS if tail in ("back", "wrong") else GET_FORMS
    for verb, want in zip(forms, EXPECTED[tail]):
        assert m.apply_phrase_grammar(f"we {verb} {tail}.") == f"we {want}.", verb
        assert wins(f" {want}", f" {verb} {tail}"), (verb, tail)


@pytest.mark.parametrize("w", ["and", "but", "or", "soon", "now", "again", "today", "quickly", "fast"])
def test_get_end_words(w):
    assert m.apply_phrase_grammar(f"it will get better {w} x") == f"it will improve {w} x"
    assert m.apply_phrase_grammar(f"it will get better {w}x") == f"it will get better {w}x"
