"""Scoped Chinese (zh) round-trip evidence for the 62 labelled zh_de_phrases winners."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import roundtrip
from tests._helpers import load

# (form, entry id, restored, completed, runtime_pair_loaded on main 84e5dca)
RESULTS = [
    ('多谢', 'thanks-zh', 0, 9, True),
    ('早', 'morning-zh', 9, 9, False),
    ('再见', 'later-zh', 0, 9, False),
    ('晚安', 'night-zh', 9, 9, False),
    ('稍等', 'wait-zh', 0, 9, False),
    ('明白', 'understand-zh', 0, 9, False),
    ('几点', 'time-zh', 0, 9, True),
    ('明天见', 'tomorrow-zh', 9, 9, False),
    ('当然', 'course-zh', 9, 9, False),
    ('高速', 'high-speed-zh', 9, 9, True),  # re-score: another official source of the form
    ('短期', 'short-term-zh', 9, 9, False),  # re-score: another official source of the form
    ('绿茶', 'green-tea-zh', 9, 9, False),
    ('红茶', 'black-tea-zh', 9, 9, False),
    ('驾照', 'fuehrerschein', 0, 9, False),
    ('警局', 'polizeiwache', 9, 9, False),
    ('邮局', 'postamt', 9, 9, False),
    ('血压', 'blutdruck', 9, 9, False),
    ('心脏病', 'herzinfarkt', 0, 9, False),
    ('操作系统', 'betriebssystem', 9, 9, False),
    ('餐厅', 'eetkamer', 0, 9, False),
    ('高中', 'high-school-zh', 9, 9, False),
    ('初中', 'middle-school-zh', 9, 9, False),
    ('小学', 'primary-school-zh', 9, 9, False),  # re-score: another official source of the form
    ('地铁站', 'subway-zh', 9, 9, False),
    ('客厅', 'living-room-zh', 9, 9, False),
    ('限速', 'speed-limit-zh', 9, 9, False),
    ('人权', 'human-rights-zh', 9, 9, False),
    ('社媒', 'social-media-zh', 9, 9, False),
    ('开源', 'open-source-zh', 9, 9, True),
    ('酱油', 'soy-sauce-zh', 9, 9, False),
    ('炒饭', 'fried-rice-zh', 9, 9, False),
    ('高铁', 'hsr-zh', 9, 9, True),  # re-score: another official source of the form
    ('便利店', 'convenience-zh', 9, 9, False),
    ('商场', 'mall-zh', 9, 9, False),
    ('百货', 'dept-store-zh', 9, 9, False),
    ('书店', 'bookstore-zh', 0, 9, False),
    ('药店', 'drugstore-zh', 0, 9, False),
    ('超市', 'supermarket-zh', 0, 9, False),
    ('名片', 'biz-card-zh', 9, 9, False),
    ('出差', 'biz-trip-zh', 9, 9, False),
    ('邮箱', 'email-zh', 0, 9, False),
    ('电话', 'phone-zh', 0, 9, True),
    ('U盘', 'flash-drive-zh', 0, 9, False),
    ('源码', 'source-code-zh', 9, 9, False),
    ('界面', 'ui-zh', 0, 9, False),
    ('前端', 'frontend-zh', 0, 9, False),
    ('全栈', 'fullstack-zh', 9, 9, True),
    ('知识库', 'kb-zh', 9, 9, False),
    ('向量库', 'vecdb-zh', 0, 9, False),
    ('大模型', 'llm-zh', 0, 9, True),
    ('思维链', 'cot-zh', 9, 9, True),
    ('微调', 'finetune-zh', 9, 9, True),  # re-score: another official source of the form
    ('限流', 'ratelimit-zh', 0, 9, False),
    ('高可用', 'ha-zh', 9, 9, False),
    ('灾备', 'dr-zh', 9, 9, False),
    ('技术债', 'techdebt-zh', 9, 9, False),
    ('持续集成', 'ci-zh', 9, 9, False),
    ('往返', 'roundtrip-zh', 9, 9, False),
    ('邮编', 'postal-zh', 9, 9, False),
    ('截图', 'screenshot-zh', 0, 9, False),
    ('黑箱', 'blackbox-zh', 9, 9, False),
    ('白皮书', 'whitepaper-zh', 9, 9, False),
]


def fixture(name):
    return json.loads((ROOT / "SentenceCalibratedMosaic/fixtures" / name).read_text(encoding="utf-8"))


def test_parent_judge_table_is_unchanged():
    path = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/zh_blind.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "bd799e8beb775359b3c85ef109996aa0e4d98c51bf4b671b3aa90722814464a8"
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 186


def test_counts():
    assert len(RESULTS) == len({r[0] for r in RESULTS}) == 62
    assert sum(r[3] for r in RESULTS) == 558
    # 37 → 42 / 3 → 6 after the accepted-sources re-score (docs/roundtrip_rescore_20261110.md)
    assert sum(r[2] == r[3] for r in RESULTS) == 42
    assert sum(r[4] for r in RESULTS) == 10
    assert sum(r[4] and r[2] == r[3] for r in RESULTS) == 6


@pytest.mark.parametrize("form,eid,restored,completed,loaded", RESULTS)
def test_scoped_zh_evidence(form, eid, restored, completed, loaded):
    data = roundtrip.load()
    rec = data["records"]["zh:" + form]
    cohort = roundtrip.latest_cohort(rec)
    assert cohort["complete"]
    assert (cohort["restored"], cohort["completed"]) == (restored, completed)
    assert cohort["timeouts"] == cohort["execution_errors"] == 0
    assert cohort["config"]["templates"] == ["{s}.", "Maybe {s} today.", "She told me that {s}."]
    assert cohort["config"]["seeds"] == [1, 2, 3]
    assert cohort["config"]["normalization"] == "norm-nfc-v1"
    assert cohort["config"]["evaluation_policy"]["min_trials"] == 9
    assert cohort["config"]["evaluation_policy"]["thresholds"]["ge100m"] == 0.6
    assert "zh" in cohort["config"]["evaluation_policy"]["ge100m_langs"]
    assert roundtrip.status(data, "zh", form) == ("pass" if restored / completed >= 0.6 else "never")
    answers = fixture("roundtrip_judge/zh_blind.json")
    for target in cohort["targets"]:
        # the latest cohort is the accepted-sources re-score: any official source of the form counts
        accepted = target.get("accepted_sources", [target["source"]]) + target.get("equivalent_sources", [])
        assert target["restored"] == any(roundtrip.norm(answers[target["converted"]]) == roundtrip.norm(s) for s in accepted)
    assert set(Counter(t["source"] for t in cohort["targets"]).values()) == {3}
    bank = fixture("zh_de_phrases.json")
    live = {e["id"]: e for e in bank["entries"]}
    dropped = {e["id"]: e for e in bank.get("examples_not_registered", [])}
    if restored == completed:
        assert live[eid]["to"] == form and live[eid]["lang"] == "zh"
    else:
        assert eid not in live
        assert dropped[eid]["to"] == form and "restored as" in dropped[eid]["why_dropped"]


def test_runtime_pairs_after_gate():
    t = load("mosaic_zh_gate", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    zh_entry_forms = {e["to"] for e in fixture("zh_de_phrases.json")["entries"] if e["lang"] == "zh"}
    loaded = {r for _, r, lg in t.zh_de_phrase_pairs() if lg == "zh"} & zh_entry_forms
    # + 高速 / 高铁 / 微调 restored by the accepted-sources re-score (短期 / 小学 are not loaded at runtime)
    assert loaded == {"开源", "全栈", "思维链", "高速", "高铁", "微调"}


def test_non_zh_entries_unchanged():
    """de / en / nl entries (incl. those carrying losing zh candidates) are byte-identical to main 84e5dca,
    minus the three de entries reversed by the de round-trip (#174: Tankstelle, Parkplatz, wenn)."""
    n = [e for e in fixture("zh_de_phrases.json")["entries"] if e["lang"] != "zh"]
    assert len(n) == 22
    blob = json.dumps(n, ensure_ascii=False, sort_keys=True).encode()
    assert hashlib.sha256(blob).hexdigest() == "8b00a966355899c7633af1af5fe4f91be11d5e86a2cb72a7d5acc2ff78b9def9"
