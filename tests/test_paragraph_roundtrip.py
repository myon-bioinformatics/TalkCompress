"""Paragraph round-trip harness (scripts/paragraph_roundtrip.py): fixtures, packs, scoring. Offline."""
from __future__ import annotations

import json, shutil, sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import paragraph_roundtrip as pr  # noqa: E402
import paragraph_replay as rp  # noqa: E402

SOURCES = pr.load_json(pr.SOURCES)
PARAS = {p["id"]: p for p in SOURCES["paragraphs"]}
ITEMS = pr.load_json(pr.path("items"))
BY_PARA = {i["paragraph"]: i for i in ITEMS["items"]}
LANGS = ["en", "de", "es", "fr", "pt", "ja", "zh", "it", "nl", "el", "cs", "pl", "la"]


# --- sources -----------------------------------------------------------------------------------

def test_sixty_paragraphs_with_planned_language_split():
    c = Counter(p["lang"] for p in SOURCES["paragraphs"])
    assert len(PARAS) == 60
    assert c == Counter({"en": 12, **{l: 4 for l in LANGS if l != "en"}})
    groups = Counter(p["group"] for p in SOURCES["paragraphs"] if p["lang"] == "en")
    assert groups == {"flores-wikinews": 6, "pd-narrative": 6}


@pytest.mark.parametrize("pid", sorted(PARAS))
def test_paragraph_shape_and_licence(pid):
    p = PARAS[pid]
    assert 3 <= len(p["sentences"]) <= 6
    assert len(set(p["sentences"])) == len(p["sentences"])
    assert p["text"] == ("" if p["lang"] in ("ja", "zh") else " ").join(p["sentences"])
    for k in ("source", "license", "author", "url"):
        assert isinstance(p[k], str) and p[k]
    if "-flores-" in pid:
        assert p["license"] == "CC BY-SA 4.0" and p["upstream"]["sha256"] == pr_flores_sha()
    else:
        assert p["license"] == "Public domain"


def pr_flores_sha():
    import build_paragraph_sources as b
    return b.FLORES_SHA256


def test_flores_paragraphs_are_parallel_across_languages():
    for k in range(1, 5):
        urls = {PARAS[f"{l}-flores-{k:02d}"]["url"] for l in LANGS if l != "la"}
        lines = {tuple(PARAS[f"{l}-flores-{k:02d}"]["upstream"]["devtest_lines"]) for l in LANGS if l != "la"}
        assert len(urls) == 1 and len(lines) == 1


def test_latin_is_public_domain_caesar_not_flores():
    la = [p for p in SOURCES["paragraphs"] if p["lang"] == "la"]
    assert all("Gutenberg #218" in p["source"] and p["upstream"]["sha256"] for p in la)


def test_pd_sentences_not_cut_after_mr_mrs():
    for p in SOURCES["paragraphs"]:
        if p["group"] == "pd-narrative":
            assert not any(s.rstrip().endswith(("Mr.", "Mrs.", "(Mrs.")) for s in p["sentences"]), p["id"]


# --- prompt, items, packs ----------------------------------------------------------------------

def test_official_prompt_is_versioned_and_formats():
    assert pr.PROMPT_VERSION == "paragraph-restore-v1"
    out = pr.prompt_for("de", "XYZ")
    assert "written in German" in out and "plain German paragraph" in out
    assert "one sentence per line" in out and "It may also be unchanged" in out
    assert out.endswith("\n\nXYZ")
    assert set(pr.LANG_NAMES) == set(LANGS)


def test_items_cover_every_method_and_bytes_are_measured():
    assert len(ITEMS["items"]) == 60
    for it in ITEMS["items"]:
        p = PARAS[it["paragraph"]]
        assert it["bytes"] == len(p["text"].encode("utf-8"))
        assert set(it["methods"]) == set(pr.METHODS)
        assert it["methods"]["control"]["text"] == p["text"]
        for m, r in it["methods"].items():
            assert r["bytes"] == len(r["text"].encode("utf-8"))
            assert r["judged"] == (m in pr.JUDGED)
            assert r["o200k_delta_pct"] == pr.pct(r["o200k"], it["o200k"])
    assert ITEMS["sources_sha256"] == pr.sha256(pr.dumps(SOURCES))


def test_o200k_counts_match_tiktoken_on_a_sample():
    pytest.importorskip("tiktoken")
    for pid in ("en-pd-01", "ja-flores-01", "la-caesar-01"):
        it = BY_PARA[pid]
        assert it["o200k"] == pr.o200k(PARAS[pid]["text"])
        assert it["methods"]["CEF"]["o200k"] == pr.o200k(it["methods"]["CEF"]["text"])


def test_compression_is_reproducible_on_a_sample():
    for pid in ("en-pd-01", "pt-flores-01"):
        for m in ("CEF", "BEF"):
            assert pr.compress(m, PARAS[pid]["text"]) == BY_PARA[pid]["methods"][m]["text"]


@pytest.mark.parametrize("seed", pr.SEEDS)
def test_pack_has_180_blind_items(seed):
    pack = pr.load_json(pr.path("pack", seed))
    assert len(pack) == 180 and len({p["id"] for p in pack}) == 180
    for p in pack:
        pid, m = p["id"].split("|")
        assert m in pr.JUDGED and p["seed"] == seed
        assert set(p) == {"id", "seed", "prompt", "compressed_text", "prompt_version", "prompt_sha256"}
        assert p["compressed_text"] == BY_PARA[pid]["methods"][m]["text"]
        assert p["prompt"] == pr.prompt_for(PARAS[pid]["lang"], p["compressed_text"])
        assert p["prompt_sha256"] == pr.sha256(p["prompt"])


def test_seeds_share_prompts_but_not_order():
    packs = [pr.load_json(pr.path("pack", s)) for s in pr.SEEDS]
    assert len({json.dumps(sorted((p["id"], p["prompt"]) for p in pk)) for pk in packs}) == 1
    assert len({tuple(p["id"] for p in pk) for pk in packs}) == 3


def test_ai_readability_is_marked_unmeasured():
    assert pr.AI_READABILITY == "未測定"
    assert pr.score_all(ITEMS, SOURCES, {})["ai_readability"] == "未測定"


# --- scoring -----------------------------------------------------------------------------------

def P(sentences, lang="en"):
    return {"id": "t", "lang": lang, "sentences": sentences}


def test_perfect_answer_one_per_line():
    p = P(["I thought so.", "They found it.", "We left."])
    r = pr.score_answer(p, "x", "I thought so.\nThey found it.\nWe left.")
    assert (r["exact"], r["paragraph_exact"], r["format_followed"]) == (3, True, True)


def test_single_line_answer_is_split_and_flagged():
    p = P(["Mr. Smith came.", "He sat down.", "It rained."])
    r = pr.score_answer(p, "x", "Mr. Smith came. He sat down. It rained.")
    assert r["exact"] == 3 and r["format_followed"] is False


def test_cjk_single_line_split():
    p = P(["昨日は雨でした。", "今日は晴れです。", "明日も晴れです。"], "ja")
    r = pr.score_answer(p, "x", "昨日は雨でした。今日は晴れです。明日も晴れです。")
    assert r["exact"] == 3


def test_merge_with_equal_content_counts_exact_but_is_labelled():
    p = P(["He came.", "She left.", "It ended."])
    r = pr.score_answer(p, "x", "He came. She left.\nIt ended.")
    assert r["exact"] == 3 and r["labels"].get("merge_split") == 1 and not r["paragraph_exact"]


def labels(gold, got, lang="en", comp="x"):
    return pr.score_answer(P([gold, "Same.", "Same again."], lang), comp, f"{got}\nSame.\nSame again.")["labels"]


def test_tense_swap():
    assert "tense_swap" in labels("They have found it.", "They found it.")


def test_added_subject():
    assert "added_subject_object" in labels("Went home early.", "He went home early.")


def test_article_demonstrative_change():
    assert "article_demonstrative" in labels("There was no walk that day.", "There was no walk the day.")


def test_synonym_drift_and_leftover_foreign():
    lab = labels("I put forth my speed.", "I pos forth my speed.", comp="I pos forth my speed. Same. Same again.")
    assert "synonym_drift" in lab and "leftover_foreign" in lab


def test_leftover_kanji_and_symbol():
    lab = labels("Is the park let at last?", "Is the park let 遂 ○?", comp="Is park let 遂 ○? Same. Same again.")
    assert lab.get("leftover_kanji_symbol") == 2


def test_inflection_change_non_english():
    assert "inflection_change" in labels("Er machte lange Pause.", "Er macht lange Pause.", "de")


def test_contraction_is_benign_and_semantic():
    r = pr.score_answer(P(["I've won.", "Same.", "Again."]), "I've won. Same. Again.", "I have won.\nSame.\nAgain.")
    assert r["labels"] == {"contraction_or_variant": 1} and r["semantic_rule"] == 3 and r["exact"] == 2


def pair(gold, got, lang="en"):
    return pr.score_answer(P([gold, "Same.", "Same again."], lang), "x", f"{got}\nSame.\nSame again.")


def test_notation_tolerant_number_words_and_percent():
    r = pair("It rose eighteen per cent.", "It rose 18%.")
    assert r["exact"] == 2 and r["semantic_rule"] == 2
    assert r["notation_tolerant"] == 3
    assert r["sentence_rows"][0]["notation_tolerant"] is True
    assert r["labels"] == {}
    r = pair("the eighteenth century", "the 18th century")
    assert r["exact"] == 2 and r["notation_tolerant"] == 3
    assert pr.notation_form("twenty-one") == pr.notation_form("21")
    assert pr.notation_form("one hundred") == pr.notation_form("100")


def test_notation_tolerant_quotes_dashes_and_punctuation():
    r = pair("She said it\u2019s done.", "She said it's done.")
    assert r["exact"] == 2 and r["notation_tolerant"] == 3
    r = pair("He said \u201chello\u201d.", 'He said "hello".')
    assert r["notation_tolerant"] == 3
    r = pair("foo \u2014 bar.", "foo - bar.")
    assert r["notation_tolerant"] == 3


def test_notation_tolerant_rejects_lexical_synonyms_and_added_words():
    r = pair("There were at least four people.", "There were about four people.")
    assert r["notation_tolerant"] == 2
    assert r["sentence_rows"][0]["notation_tolerant"] is False
    r = pair("By failure it stopped.", "By the failure it stopped.")
    assert r["notation_tolerant"] == 2
    r = pair("Die Antwort kam.", "Die Reaktion kam.", "de")
    assert r["notation_tolerant"] == 2
    # contractions are wording, not notation
    r = pair("I've won.", "I have won.")
    assert r["semantic_rule"] == 3 and r["notation_tolerant"] == 2


def test_rule_attribution_marks_unrestored_substitution():
    p = P(["I challenge any one here.", "Same.", "Again."])
    r = pr.score_answer(p, "reto any 1 here. Same. Again.", "I challenge anyone here.\nSame.\nAgain.")
    rules = {a["rule"]: a["restored_ok"] for a in r["sentence_rows"][0]["rules"]}
    assert rules["i challenge → reto"] is True and rules["one → 1"] is False


def test_missing_answer_scores_zero():
    r = pr.score_answer(P(["A b.", "C d.", "E f."]), "x", None)
    assert r["status"] == "no_answer" and r["exact"] == 0
    assert r["semantic_rule"] == 0 and r["notation_tolerant"] == 0


# --- ingest / score / replay round trip in a scratch directory ------------------------------------

@pytest.fixture
def scratch(tmp_path, monkeypatch):
    for name in (pr.path("items").name, pr.path("pack", 1).name):
        shutil.copy(pr.DIR / name, tmp_path / name)
    monkeypatch.setattr(pr, "DIR", tmp_path)
    return tmp_path


def raw_for(pack, answer_of, seed=1):
    return {"run": pr.RUN, "seed": seed, "judge": {"type": "test"},
            "answers": [{"id": p["id"], "prompt_sha256": p["prompt_sha256"], "status": "ok",
                         "answer": answer_of(p)} for p in pack]}


def test_ingest_rejects_wrong_sha_and_missing_items(scratch):
    pack = pr.load_json(pr.path("pack", 1))
    raw = raw_for(pack, lambda p: "x")
    raw["answers"][0]["prompt_sha256"] = "0" * 64
    del raw["answers"][1]
    errs = pr.validate_raw(raw, pack, 1)
    assert any("prompt_sha256" in e for e in errs) and any("no answer record" in e for e in errs)


def test_gold_answers_score_perfectly_and_replay(scratch):
    pack = pr.load_json(pr.path("pack", 1))
    gold = lambda p: "\n".join(PARAS[p["id"].split("|")[0]]["sentences"])  # noqa: E731
    pr.path("raw", 1).write_text(pr.dumps(raw_for(pack, gold)), encoding="utf-8")
    pr.path("blind", 1).write_text(pr.dumps(pr.ingest(1)), encoding="utf-8")
    res = pr.current_results()
    for m in pr.JUDGED:
        a = res["summary"][m]["all"]
        assert a["exact"] == a["sentences"] and a["paragraph_exact"] == 60
        assert a["notation_tolerant"] == a["sentences"] and "notation_tolerant_rate" in a
        assert "en" in res["summary"][m] and "notation_tolerant" in res["summary"][m]["en"]
    pr.path("results").write_text(pr.dumps(res), encoding="utf-8")
    assert rp.check(rebuild=False) == []
    item = pack[0]
    assert rp.replay(1, item["id"]) == gold(item)
    pr.path("results").write_text("{}", encoding="utf-8")
    assert rp.check(rebuild=False) == ["results stale (run paragraph_roundtrip.py score)"]


def test_run_cmd_records_answers_with_seed_env(scratch):
    pack = pr.load_json(pr.path("pack", 1))
    raw = pr.run_cmd(1, 'printf "seed=$PARA_SEED item=$PARA_ITEM"', workers=8)
    byid = {a["id"]: a["answer"] for a in raw["answers"]}
    assert len(raw["answers"]) == 180
    assert all(byid[p["id"]] == f"seed=1 item={p['id']}" for p in pack)
    assert pr.validate_raw(raw, pack, 1) == []


def test_mosaic_tiles_are_split_for_attribution():
    assert pr.split_compressed("de:Er kam.|Sie ging.|en:It ended.|&:\"", 3) == ["Er kam.", "Sie ging.", "It ended."]
    p = P(["Er kam mit Freunden.", "Sie ging.", "Es endete."], "de")
    r = pr.score_answer(p, "de:Er kam with Freunden.|Sie ging.|Es endete.", "Er kam mit Freunden.\nSie ging.\nEs endete.")
    assert [a["rule"] for a in r["sentence_rows"][0]["rules"]] == ["mit → with"]


def test_answer_split_before_a_number():
    assert pr.split_answer("He left. 34 per cent agreed. It rained.", 3)[0] == ["He left.", "34 per cent agreed.", "It rained."]


def test_replay_keys_by_item_id_when_prompts_collide(scratch):
    """control and unchanged-CEF share a prompt sha but have independent answers."""
    pack = pr.load_json(pr.path("pack", 1))
    byid = {p["id"]: p for p in pack}
    control = byid["el-flores-01|control"]
    cef = byid["el-flores-01|CEF"]
    assert control["prompt"] == cef["prompt"]
    assert control["prompt_sha256"] == cef["prompt_sha256"]
    answers = {
        control["id"]: "CONTROL-ONLY ANSWER",
        cef["id"]: "CEF-ONLY ANSWER",
    }
    pr.path("blind", 1).write_text(pr.dumps({
        "run": pr.RUN, "seed": 1, "prompt_version": pr.PROMPT_VERSION,
        "judge": {"type": "test"}, "no_answer": [],
        "answers": {iid: {"answer": ans, "prompt_sha256": byid[iid]["prompt_sha256"]}
                    for iid, ans in answers.items()},
    }), encoding="utf-8")
    pr.path("results").write_text(pr.dumps(pr.current_results()), encoding="utf-8")
    assert rp.check(rebuild=False) == []
    assert rp.replay(1, control["id"]) == "CONTROL-ONLY ANSWER"
    assert rp.replay(1, cef["id"]) == "CEF-ONLY ANSWER"
    # stdin/prompt sha is also accepted when it matches this id's pack prompt
    assert rp.replay(1, control["id"], prompt=control["prompt"]) == "CONTROL-ONLY ANSWER"
    assert rp.replay(1, cef["id"], prompt=cef["prompt"]) == "CEF-ONLY ANSWER"

    blind = pr.load_blind(1)
    blind["answers"][control["id"]]["prompt_sha256"] = "0" * 64
    pr.path("blind", 1).write_text(pr.dumps(blind), encoding="utf-8")
    problems = rp.check(rebuild=False)
    assert any("el-flores-01|control" in p and "different prompt" in p for p in problems)
    assert not any("el-flores-01|CEF" in p for p in problems)
    assert rp.replay(1, control["id"]) is None
    assert rp.replay(1, cef["id"]) == "CEF-ONLY ANSWER"

