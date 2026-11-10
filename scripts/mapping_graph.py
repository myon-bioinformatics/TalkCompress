"""Read-only knowledge graph over the SentenceCalibratedMosaic mapping tables (docs/ontology/).

Builds an in-memory graph (stdlib only, no tiktoken) from the committed data:

* bank fixtures: ``tense_matrix.json``, ``es_fr_tense.json``, ``pt_el_latin_tense.json``,
  ``pt_el_latin_phrases.json``, ``zh_de_phrases.json`` (entries + examples_not_registered)
* ``docs/tense_matrix_report.json`` (per-cell candidates, reversals, parity follows)
* ``SentenceCalibratedMosaic/fixtures/roundtrip.json`` (AI round-trip records / cohorts)
* the ``ROUNDTRIP_*`` settings in ``scripts/tense_matrix.py`` (read with ``ast``,
  the module is not imported, so nothing is rebuilt or scored)

It never writes any file and never changes adoption behaviour; it only answers
questions about what the data already says.

Usage::

    uv run python scripts/mapping_graph.py --check                  # summary + integrity
    uv run python scripts/mapping_graph.py --untested [--lang pt]   # adopted forms with no record
    uv run python scripts/mapping_graph.py --source "I will take"   # every language for one EN source
    uv run python scripts/mapping_graph.py --parity-reversed        # parity followers of reversed bases
    uv run python scripts/mapping_graph.py --collisions             # same form, other lang / meaning
    uv run python scripts/mapping_graph.py --collisions --markdown  # tense_merge report (docs/ontology/)
    uv run python scripts/mapping_graph.py --node form:pt:foi       # one node and its edges

Add ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse, ast, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
REPORT_PATH = ROOT / "docs/tense_matrix_report.json"
TM_PATH = ROOT / "scripts/tense_matrix.py"
BANKS = ("tense_matrix", "es_fr_tense", "pt_el_latin_tense", "pt_el_latin_phrases", "zh_de_phrases")
PHRASE_BANKS = ("pt_el_latin_phrases", "zh_de_phrases")
SETTINGS = (
    "ROUNDTRIP_ENFORCED_LANGS",
    "ROUNDTRIP_REVERSED",
    "ROUNDTRIP_REVERSED_SOURCES",
    "ROUNDTRIP_REVERSED_ANY_CANDIDATE_LANGS",
    "ROUNDTRIP_REVERSED_DROP_CANDIDATE_LANGS",
    "ROUNDTRIP_REVERSED_TIE_WINNER_LANGS",  # #174 (de); absent on older bases -> empty
)
# Status vocabulary. pass/fail/never/unverified come from scripts/roundtrip.py
# status(); untested (no record at all) and not_applicable are graph-only.
STATUSES = ("pass", "fail", "never", "unverified", "untested", "not_applicable")
TENSE_ALIASES = {"future": "fut", "present": "pres", "conditional": "cond"}

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import roundtrip as rt  # noqa: E402  (stdlib only; status() is the single source of truth)
from shared.kgraph import CycleError, Graph, GraphError, aggregate, dependency_order  # noqa: E402


def norm_en(s: str) -> str:
    """Stable English-source key: lowercased, whitespace collapsed."""
    return " ".join(s.lower().split())


def form_id(lang: str, form: str) -> str:
    return f"form:{lang}:{form}"  # == roundtrip.json record key with a "form:" prefix


def read_settings(path: Path = TM_PATH) -> dict[str, frozenset]:
    """Literal ``frozenset({...})`` constants from tense_matrix.py, without importing it."""
    out = {name: frozenset() for name in SETTINGS}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name in out and isinstance(node.value, ast.Call) and node.value.args:
            out[name] = frozenset(ast.literal_eval(node.value.args[0]))
    return out


def reversal_strategy(lang: str, s: dict) -> str:
    if lang in s["ROUNDTRIP_REVERSED_ANY_CANDIDATE_LANGS"]:
        return "any_candidate_empties_cell"
    if lang in s["ROUNDTRIP_REVERSED_DROP_CANDIDATE_LANGS"]:
        return "drop_candidate_before_ranking"
    if lang in s["ROUNDTRIP_REVERSED_TIE_WINNER_LANGS"]:
        return "tie_winner_empties_else_drop"
    return "adopted_winner_only"


def meaning_key(bank: str, entry: dict) -> str:
    """Coarse meaning of an entry: verb+tense for tense banks, the EN phrase otherwise."""
    if bank in PHRASE_BANKS:
        return "phrase:" + norm_en(entry["from"][0])
    eid = entry["id"]
    if bank == "tense_matrix":
        _, verb, tense, _ = eid.split("-", 3)
        return f"{verb}:{tense}"
    tense = TENSE_ALIASES.get(entry.get("tense", ""), entry.get("tense", ""))
    parts = eid.split("-")
    idx = next((i for i, p in enumerate(parts) if TENSE_ALIASES.get(p, p) in (tense, "fut", "pres", "past", "cond")), len(parts))
    return f"{'-'.join(parts[:idx]) or eid}:{tense}"


def run_provenance(cohort: dict, history_entry: dict | None) -> dict:
    """``origin_main_sha`` / ``timestamp`` written by ``roundtrip.run`` (cohort first, then run_history).

    Only well-formed values (``rt.valid_provenance``) are read; older cohorts have none.
    """
    for p in (cohort.get("provenance"), (history_entry or {}).get("provenance")):
        if rt.valid_provenance(p):
            return p
    return {"origin_main_sha": None, "timestamp": None}


def measured_sources(cohort: dict) -> list[str]:
    """English sources a cohort actually asked the restorer to recover (template slot ``{s}``)."""
    pats = []
    # most literal text first, so "{s}." does not swallow "Maybe {s} today."
    templates = [t for t in cohort.get("config", {}).get("templates", []) if isinstance(t, str)]
    for t in sorted(templates, key=lambda t: (-len(t), t)):
        if t.count("{s}") == 1:
            head, tail = t.split("{s}")
            pats.append(re.compile(re.escape(head) + "(.+?)" + re.escape(tail), re.IGNORECASE | re.DOTALL))
    out = set()
    for target in cohort.get("targets", []):
        src = target.get("source")
        for pat in pats if isinstance(src, str) else ():
            m = pat.fullmatch(src)
            if m:
                out.add(norm_en(m.group(1)))
                break
    return sorted(out)


def _record_nodes(g: Graph, rtd: dict, lang: str, form: str, fid: str) -> None:
    rec = rtd["records"].get(rt.key(lang, form))
    if not rec:
        return
    hist = {h["run_id"]: h for h in rtd.get("run_history", [])}
    cohorts = rec.get("cohorts") or []
    if not cohorts:  # legacy (pre-v4) aggregate record
        rid = g.add(f"rt:{lang}:{form}:legacy", "RoundtripRecord", run_id=None, evaluator=None,
                    measured_at_main=None, run_origin_main_sha=None, timestamp=None, completed=rec.get("trials", 0),
                    restored=rec.get("restored", 0), measured_sources=[], latest=True)
        g.link(rid, "verifies", fid)
        return
    for i, c in enumerate(cohorts):
        prov = (hist.get(c["run_id"]) or {}).get("judge_provenance") or {}
        run_prov = run_provenance(c, hist.get(c["run_id"]))
        done = [t for t in c.get("targets", []) if t.get("status") == "completed"]
        # a judge's own snapshot SHA (pt) wins over the run-time origin/main SHA
        rid = g.add(f"rt:{lang}:{form}:{c['run_id']}", "RoundtripRecord", run_id=c["run_id"],
                    evaluator=prov.get("kind") or "cmd:" + c["config"]["command_sha256"][:12],
                    measured_at_main=prov.get("origin_main_sha") or run_prov["origin_main_sha"],
                    run_origin_main_sha=run_prov["origin_main_sha"], timestamp=run_prov["timestamp"],
                    completed=len(done), restored=sum(1 for t in done if t.get("restored")),
                    measured_sources=measured_sources(c), latest=i == len(cohorts) - 1)
        g.link(rid, "verifies", fid)


def build(root: Path = ROOT) -> Graph:
    g = Graph()
    s = read_settings(root / "scripts/tense_matrix.py")
    rtd = rt.load(root / "SentenceCalibratedMosaic/fixtures/roundtrip.json")

    def lang_node(lang: str) -> str:
        return g.add(f"lang:{lang}", "Language", code=lang, ge100m=lang in rtd["ge100m_langs"],
                     roundtrip_enforced=lang in s["ROUNDTRIP_ENFORCED_LANGS"],
                     reversal_strategy=reversal_strategy(lang, s))

    def en_node(src: str) -> str:
        return g.add(f"en:{norm_en(src)}", "EnglishSource", text=norm_en(src))

    def form_node(lang: str, form: str) -> str:
        fid = form_id(lang, form)
        if fid not in g.nodes:
            na = lang == "en"
            st = "not_applicable" if na else (rt.status(rtd, lang, form)
                                              if rt.key(lang, form) in rtd["records"] else "untested")
            g.add(fid, "Form", lang=lang, form=form, status=st)
            g.link(fid, "inLanguage", lang_node(lang))
            if not na:
                _record_nodes(g, rtd, lang, form, fid)
        return fid

    def candidate(lang: str, form: str, src: str, origin: str, **props) -> str:
        fid, eid = form_node(lang, form), en_node(src)
        cid = g.add(f"cand:{lang}:{form}:{norm_en(src)}", "Candidate", lang=lang, form=form, origin=origin, **props)
        g.link(cid, "proposesForm", fid)
        g.link(cid, "forSource", eid)
        return cid

    # 1. bank entries = adopted forms (Form adopted for an English source)
    for bank in BANKS:
        data = json.loads((root / f"SentenceCalibratedMosaic/fixtures/{bank}.json").read_text(encoding="utf-8"))
        for e in data.get("entries", []):
            lang, to, src = e["lang"], e["to"], e["from"][0]
            same = norm_en(to) == norm_en(src)  # EN kept in place (es_fr_tense "I will want")
            fid = form_node(lang, to)
            aid = g.add(f"adopt:{lang}:{to}:{norm_en(src)}", "Adoption", lang=lang, form=to, source=norm_en(src),
                        bank=bank, entry_id=e["id"], meaning=meaning_key(bank, e), en_kept=same)
            g.link(aid, "usesForm", fid)
            g.link(aid, "replaces", en_node(src))
            for alt in e["from"][1:]:
                g.link(aid, "alsoReplaces", en_node(alt))
            for c in e.get("candidates") or []:
                if isinstance(c, dict) and c.get("lang") and c.get("form"):
                    candidate(c["lang"], c["form"], src, f"{bank}#{e['id']}")
        for e in data.get("examples_not_registered", []):
            if not e.get("to") or not e.get("from"):
                continue
            cid = candidate(e["lang"], e["to"], e["from"][0], f"{bank}#{e['id']}", not_registered=True,
                            why_dropped=e.get("why_dropped"))
            if e.get("roundtrip_reversed"):
                rid = g.add(f"rev:{e['lang']}:{e['to']}", "ReversalDecision", lang=e["lang"], form=e["to"],
                            strategy="fixture_not_registered", setting=f"{bank}.examples_not_registered")
                g.link(rid, "reverses", form_id(e["lang"], e["to"]))
                g.link(cid, "rejectedBy", rid)

    # every round-trip record is knowledge even when its form is no longer in a bank
    for rec in rtd["records"].values():
        form_node(rec["lang"], rec["form"])

    # 2. reversals from settings (union across languages)
    for lang, form in sorted(s["ROUNDTRIP_REVERSED"]):
        fid = form_node(lang, form)
        rid = g.add(f"rev:{lang}:{form}", "ReversalDecision", lang=lang, form=form,
                    strategy=reversal_strategy(lang, s), setting="ROUNDTRIP_REVERSED")
        g.link(rid, "reverses", fid)
        for rec in g.inc(fid, "verifies"):
            g.link(rid, "basedOn", rec)
    for src in sorted(s["ROUNDTRIP_REVERSED_SOURCES"]):
        rid = g.add(f"revsrc:{norm_en(src)}", "ReversalDecision", source=norm_en(src),
                    strategy="source_keeps_english", setting="ROUNDTRIP_REVERSED_SOURCES")
        g.link(rid, "keepsEnglish", en_node(src))

    # 3. tense-matrix report cells: losing candidates and parity follows
    report = json.loads((root / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    rev = s["ROUNDTRIP_REVERSED"]
    for c in report:
        src = c["src"]
        if c.get("best") and c.get("lang"):
            candidate(c["lang"], c["best"], src, "tense_matrix_report", cell_status=c["status"])
        for f in c.get("roundtrip_reversed", []):
            for lang in sorted(lg for lg, fm in rev if fm == f):
                cid = candidate(lang, f, src, "tense_matrix_report")
                g.link(cid, "rejectedBy", f"rev:{lang}:{f}")
        for f in c.get("roundtrip_gated", []):
            for lang in sorted(s["ROUNDTRIP_ENFORCED_LANGS"]):
                candidate(lang, f, src, "tense_matrix_report", gated=True)
        if c.get("parity_verb") and c.get("lang"):
            lang, vw = c["lang"], c["parity_verb"]
            pid = g.add(f"parity:{c['subject']}:{c['tense']}:{c['verb']}", "ParityFollow",
                        subject=c["subject"], tense=c["tense"], verb=c["verb"], lang=lang,
                        follower_form=c.get("best"), base_form=vw, cell_status=c["status"],
                        base_reversed=(lang, vw) in rev, follower_reversed=(lang, c.get("best")) in rev)
            g.link(pid, "follower", en_node(src))
            g.link(pid, "followsVerbOf", form_node(lang, vw))
            if c["status"] == "adopt":
                g.link(pid, "derivesForm", form_node(lang, c["best"]))
    g.validate()  # dangling targets (e.g. rejectedBy rev:...) must exist
    parity_order(g)  # follows must be acyclic (graphlib CycleError otherwise)
    return g


def parity_order(g: Graph) -> list[str]:
    """Judging order for parity follows: base forms before their followers.

    A follower (ParityFollow) depends on the Form it follows and, once adopted, the
    Form it derives depends on the follow. A cycle (a form following itself through
    another follow) raises ``GraphError`` from graphlib's ``CycleError``.
    """
    deps: dict[str, set[str]] = defaultdict(set)
    for p in g.of_type("ParityFollow"):
        deps[p["id"]].update(g.out(p["id"], "followsVerbOf"))
        for f in g.out(p["id"], "derivesForm"):
            deps[f].add(p["id"])
    try:
        return dependency_order(deps)
    except CycleError as exc:
        raise GraphError(f"parity follow cycle: {' -> '.join(exc.args[1])}") from exc


# ---------------------------------------------------------------- queries
def adopted_forms(g: Graph) -> dict[str, dict]:
    """Unique adopted Form nodes (not EN-kept rows), keyed by form id."""
    out = {}
    for a in g.of_type("Adoption"):
        if a["en_kept"]:
            continue
        fid = form_id(a["lang"], a["form"])
        out[fid] = g.nodes[fid]
    return out


def status_summary(g: Graph) -> dict[str, Counter]:
    return aggregate(adopted_forms(g).values(), "lang", "status")


def untested(g: Graph, lang: str | None = None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for f in adopted_forms(g).values():
        if f["status"] == "untested" and (lang is None or f["lang"] == lang):
            out[f["lang"]].append(f["form"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def by_source(g: Graph, src: str) -> list[dict]:
    eid = f"en:{norm_en(src)}"
    by_src = g.reverse_index("forSource")
    rows = []
    for nid in g.inc(eid, "replaces"):
        a = g.nodes[nid]
        rows.append({"role": "adopted", "lang": a["lang"], "form": a["form"], "bank": a["bank"],
                     "status": g.nodes[form_id(a["lang"], a["form"])]["status"]})
    for nid in by_src.get(eid, []):
        c = g.nodes[nid]
        role = "reversed" if g.out(nid, "rejectedBy") else ("not_registered" if c.get("not_registered")
                                                             else "gated" if c.get("gated") else "candidate")
        rows.append({"role": role, "lang": c["lang"], "form": c["form"], "origin": c["origin"],
                     "status": g.nodes[form_id(c["lang"], c["form"])]["status"]})
    if g.inc(eid, "keepsEnglish"):
        rows.append({"role": "source_keeps_english", "lang": "en", "form": norm_en(src), "status": "not_applicable"})
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r["role"] != "adopted", r["lang"], r["form"], r["role"])):
        k = (r["role"], r["lang"], r["form"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def parity_reversed(g: Graph) -> list[dict]:
    return sorted(({k: p[k] for k in ("id", "lang", "follower_form", "base_form", "cell_status", "follower_reversed")}
                   for p in g.of_type("ParityFollow") if p["base_reversed"]), key=lambda r: r["id"])


def collisions(g: Graph) -> dict[str, list[dict]]:
    """Adopted surface forms shared across languages, or one (lang, form) with several meanings."""
    by_surface: dict[str, set[str]] = defaultdict(set)
    by_form: dict[str, set[str]] = defaultdict(set)
    for a in g.of_type("Adoption"):
        if a["en_kept"]:
            continue
        by_surface[a["form"].casefold()].add(a["lang"])
        by_form[form_id(a["lang"], a["form"])].add(a["meaning"])
    cross = [{"form": f, "langs": sorted(ls)} for f, ls in sorted(by_surface.items()) if len(ls) > 1]
    # an adopted row whose own candidate list spells the same form under another
    # language: the ``lang`` label and the candidate disagree (e.g. es_fr_tense
    # take-fut-1s: to ``tomaré`` labelled el, candidate ``tomaré`` labelled es)
    mislabel = []
    for a in g.of_type("Adoption"):

        for cid in g.inc(f"en:{a['source']}", "forSource"):
            c = g.nodes[cid]
            if c["form"] == a["form"] and c["lang"] != a["lang"] and c["origin"].endswith("#" + a["entry_id"]):
                mislabel.append({"id": a["id"], "label": a["lang"], "candidate_lang": c["lang"], "entry": c["origin"]})
    lexical, tense_merge = [], []
    for fid, ms in sorted(by_form.items()):
        if len(ms) < 2:
            continue
        heads = {m.rsplit(":", 1)[0] for m in ms}
        (lexical if len(heads) > 1 else tense_merge).append({"id": fid, "meanings": sorted(ms)})
    mislabel = sorted(mislabel, key=lambda r: r["id"])
    return {"cross_language": cross, "lang_label_mismatch": mislabel, "multi_meaning": lexical, "tense_merge": tense_merge}


TENSE_LABELS = {"past": "過去", "perf": "現在完了", "pluperf": "過去完了", "pres": "現在", "fut": "未来"}
TENSE_ORDER = ("pres", "past", "perf", "pluperf", "fut")


def _tense_rank(t: str) -> tuple[int, str]:
    return (TENSE_ORDER.index(t) if t in TENSE_ORDER else len(TENSE_ORDER), t)


def _tenses(meanings: list[str]) -> tuple[str, ...]:
    return tuple(sorted({m.rsplit(":", 1)[1] for m in meanings}, key=_tense_rank))


def tense_merge_rows(g: Graph) -> list[dict]:
    """One row per ``tense_merge`` form: adopted EN sources and what its latest round-trip measured."""
    rows = []
    for item in collisions(g)["tense_merge"]:
        fid = item["id"]
        f = g.nodes[fid]
        adoptions = sorted((g.nodes[a] for a in g.inc(fid, "usesForm")),
                           key=lambda a: (_tense_rank(a["meaning"].rsplit(":", 1)[1]), a["entry_id"]))
        latest = next((g.nodes[r] for r in g.inc(fid, "verifies") if g.nodes[r]["latest"]), None)
        measured = set(latest["measured_sources"]) if latest else set()
        rows.append({
            "id": fid, "lang": f["lang"], "form": f["form"], "meanings": item["meanings"],
            "tenses": list(_tenses(item["meanings"])), "status": f["status"],
            "sources": [{"source": a["source"], "meaning": a["meaning"], "entry_id": a["entry_id"],
                         "measured": a["source"] in measured} for a in adoptions],
            "measured_sources": sorted(measured),
            "latest": None if latest is None else {"run_id": latest["run_id"], "completed": latest["completed"],
                                                   "restored": latest["restored"]},
        })
    return rows


def tense_merge_doc(g: Graph) -> str:
    """Markdown report for docs/ontology/tense-merge-collisions.md (printed, never written here)."""
    rows = tense_merge_rows(g)
    col = {k: len(v) for k, v in collisions(g).items()}
    by_lang = Counter(r["lang"] for r in rows)
    by_tenses = Counter(tuple(r["tenses"]) for r in rows)
    label = lambda ts: "＋".join(TENSE_LABELS.get(t, t) for t in ts)  # noqa: E731
    n_src = sum(len(r["sources"]) for r in rows)
    n_measured = sum(s["measured"] for r in rows for s in r["sources"])
    unmeasured_meaning = sum(1 for r in rows
                             if {s["meaning"] for s in r["sources"] if not s["measured"]}
                             - {s["meaning"] for s in r["sources"] if s["measured"]})
    out = [
        "# 時制を統合した採用形（`--collisions` の `tense_merge`）", "",
        "生成: `uv run python scripts/mapping_graph.py --collisions --markdown > docs/ontology/tense-merge-collisions.md`。",
        "手で直さず再生成する（`tests/test_mapping_graph.py` が生成結果との一致を確認する）。", "",
        "`tense_merge` は、同じ `lang:form` が同じ動詞の別時制の英語にも採用されている形。"
        "グラフは報告するだけで、採用は変えない（[mapping-ontology.md](mapping-ontology.md) 6 節）。", "",
        "## 件数", "",
        f"`tense_merge`: {len(rows)} 形（"
        + " / ".join(f"{lang} {n}" for lang, n in sorted(by_lang.items(), key=lambda kv: (-kv[1], kv[0]))) + "）。", "",
        "| lang | 形の数 |", "|---|---|",
        *[f"| {lang} | {n} |" for lang, n in sorted(by_lang.items())], "",
        "統合している時制の組み合わせ:", "",
        "| 時制 | 形の数 | 形 |", "|---|---|---|",
        *[f"| {label(ts)} | {n} | " + "、".join(f"`{r['lang']}:{r['form']}`" for r in rows if tuple(r["tenses"]) == ts) + " |"
          for ts, n in sorted(by_tenses.items(), key=lambda kv: (-kv[1], kv[0]))], "",
        "同じ `--collisions` の他の分類（参考）: "
        + "、".join(f"`{k}` {col[k]}" for k in ("cross_language", "lang_label_mismatch", "multi_meaning")) + "。", "",
        "## 往復で確かめた読み", "",
        "往復の判定は形ごとの最新コホートで行い、復元させた英語はコホートの `targets[].source` に残る。",
        f"上の {len(rows)} 形が採用されている英語は計 {n_src} 行で、そのうち最新コホートで復元対象だったのは {n_measured} 行。",
        f"最新コホートが測っていない時制を含む形は {unmeasured_meaning} 形ある。"
        "その時制の英語へ AI が戻せるかは、往復ではまだ確かめていない。", "",
        "## 一覧", "",
        "| lang:form | 時制 | 採用している英語 | 最新コホートで復元させた英語 | status | 最新 restored/completed |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        srcs = "<br>".join(f"{s['source']}（{s['entry_id']}）" + ("" if s["measured"] else " ※未測定") for s in r["sources"])
        latest = "記録なし" if r["latest"] is None else f"{r['latest']['restored']}/{r['latest']['completed']}"
        measured = "、".join(r["measured_sources"]) or "—"
        out.append(f"| `{r['lang']}:{r['form']}` | {label(r['tenses'])} | {srcs} | {measured} | {r['status']} | {latest} |")
    out += ["", "※未測定: その英語を復元対象にしたコホートが最新記録に無い行。", ""]
    return "\n".join(out)


def check(g: Graph) -> dict:
    s = read_settings()
    rtd = rt.load()
    adopted = adopted_forms(g)
    reversed_adopted = sorted(f"{lang}:{form}" for lang, form in s["ROUNDTRIP_REVERSED"]
                              if form_id(lang, form) in adopted)
    return {
        "nodes": dict(sorted(Counter(n["type"] for n in g.nodes.values()).items())),
        "edges": len(g.edges),
        "settings": {k: len(v) for k, v in s.items()},
        "enforced_langs": sorted(s["ROUNDTRIP_ENFORCED_LANGS"]),
        "roundtrip_records": dict(sorted(Counter(r["lang"] for r in rtd["records"].values()).items())),
        "status_by_lang": {k: dict(v) for k, v in status_summary(g).items()},
        "reversed_still_adopted": reversed_adopted,
        "parity_followers_of_reversed_base": len(parity_reversed(g)),
        "parity_followers_of_reversed_base_adopted": sorted(
            p["follower_form"] for p in parity_reversed(g) if p["cell_status"] == "adopt"),
        "collisions": {k: len(v) for k, v in collisions(g).items()},
        "records_without_main_sha": sum(1 for n in g.of_type("RoundtripRecord") if not n["measured_at_main"]),
        "records_without_timestamp": sum(1 for n in g.of_type("RoundtripRecord") if not n["timestamp"]),
    }


def _print_check(r: dict) -> None:
    print(f"nodes: {r['nodes']}  edges: {r['edges']}")
    print(f"settings: {r['settings']}  enforced: {r['enforced_langs']}")
    print(f"roundtrip records: {r['roundtrip_records']}")
    print("adopted forms by status (unique lang:form):")
    print("  lang " + " ".join(f"{s:>14}" for s in STATUSES) + "   total")
    for lang, c in r["status_by_lang"].items():
        print(f"  {lang:<4} " + " ".join(f"{c.get(s, 0):>14}" for s in STATUSES) + f"   {sum(c.values()):>5}")
    print(f"reversed forms still adopted somewhere: {len(r['reversed_still_adopted'])} {r['reversed_still_adopted']}")
    print(f"parity followers whose base is reversed: {r['parity_followers_of_reversed_base']}"
          f" (still adopted: {r['parity_followers_of_reversed_base_adopted']})")
    print(f"collisions: {r['collisions']}")
    print(f"records without main sha: {r['records_without_main_sha']}, without timestamp: {r['records_without_timestamp']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    q = ap.add_mutually_exclusive_group(required=True)
    q.add_argument("--check", action="store_true", help="summary + integrity (exit 1 only if the graph is inconsistent)")
    q.add_argument("--untested", action="store_true")
    q.add_argument("--source", metavar="EN")
    q.add_argument("--parity-reversed", action="store_true")
    q.add_argument("--collisions", action="store_true")
    q.add_argument("--node", metavar="ID")
    ap.add_argument("--lang")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true",
                    help="with --collisions: print the tense_merge report (docs/ontology/tense-merge-collisions.md)")
    a = ap.parse_args(argv)
    if a.markdown and not a.collisions:
        ap.error("--markdown needs --collisions")
    try:
        g = build()
    except GraphError as exc:
        print(f"graph inconsistent: {exc}", file=sys.stderr)
        return 1
    if a.check:
        res = check(g)
        if not a.json:
            _print_check(res)
            return 0
    elif a.untested:
        res = untested(g, a.lang)
    elif a.source:
        res = by_source(g, a.source)
    elif a.parity_reversed:
        res = parity_reversed(g)
    elif a.collisions:
        if a.markdown:
            sys.stdout.write(tense_merge_doc(g))
            return 0
        res = collisions(g)
    else:
        if a.node not in g.nodes:
            print(f"no node {a.node}", file=sys.stderr)
            return 1
        res = {"node": g.nodes[a.node], "out": g.out_edges(a.node),
               "in": [(s, p) for p, s in g.in_edges(a.node)]}
    print(json.dumps(res, ensure_ascii=False, indent=None if a.json else 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
