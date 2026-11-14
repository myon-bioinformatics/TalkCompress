#!/usr/bin/env python3
"""AI readability of TalkCompress paragraphs, restored by a pinned Qwen GGUF on CPU (stdlib only).

The paragraph benchmark (``paragraph_roundtrip.py``, prompt ``paragraph-restore-v1``) is reused
unchanged: the same pack items (control / CEF / BEF), the same rule scoring (exact, semantic_rule,
notation_tolerant, error labels). Only the restorer is new: a small local model behind llama.cpp
``llama-server`` instead of a knowledgeWork subagent. Every subcommand prints JSON on stdout.

One entry point, callable from uv, olnm, CI or an agent (paths come from ``__file__``)::

    uv run python scripts/qwen_readability.py plan --shards 8 [--per-lang 1] [--judges qwen-0.5b]
    uv run python scripts/qwen_readability.py serve --model qwen-1.5b      # docker, pinned image
    uv run python scripts/qwen_readability.py restore --shard 0 --shards 8 --out out/shard-0.json
    uv run python scripts/qwen_readability.py merge out/shard-*.json --out out/readability.json
    uv run python scripts/qwen_readability.py judge out/readability.json --model qwen-0.5b --out out/judge.json

Central definitions (the one place to change, conftest-style): ``DEFAULTS`` below, the model
catalog ``shared/l3_models.json`` (revision, bytes, SHA-256; shared with the SVG L3 workflow)
and ``JUDGES``. Judges are layered:

* ``rule`` (always, baseline): the offline rule scores of ``paragraph_roundtrip.score_answer``.
* an LLM judge (optional hook): any catalog key. ``judge`` asks it, sentence by sentence, whether
  a restored sentence that *failed* ``notation_tolerant`` still means the same as the gold one
  (prompt ``sentence-equivalence-v1``). It only adds a column (``llm_equivalent``); it never
  changes the rule numbers. Add a model to the catalog and pass its key to ``--judges``.

Determinism: temperature 0 and a fixed seed, so "seeds" are not repeated here (the three-seed
design of the subagent benchmark would give three identical answers). Digits/symbols differences
are not errors (``notation_tolerant``, t1208).
"""
from __future__ import annotations

import argparse, glob, hashlib, json, os, platform, subprocess, sys, time, urllib.error, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import paragraph_roundtrip as pr  # noqa: E402  (pack, prompt, rule scoring: shared, not copied)

CATALOG = ROOT / "shared/l3_models.json"
DEFAULTS = {
    "model": "qwen-1.5b",          # restore model (Qwen2.5-1.5B-Instruct Q4_K_M, quality_gate in the catalog)
    "seed": 1,                     # which pack file supplies the prompts (content is identical across seeds)
    "temperature": 0, "llama_seed": 42, "max_tokens": 1024, "context": 4096, "timeout": 600,
    "url": "http://127.0.0.1:8080/v1/chat/completions",
    # Official llama.cpp b12004 by OCI digest; the same image as svg-l3-matrix.yml and mcp-toolcall-lab.
    "llama_image": "ghcr.io/ggml-org/llama.cpp@sha256:b32890309c1a33a534a01b0b461e953dc2c5a6bac20213abcf48e22847a19c85",
}
JUDGES = {
    "rule": {"type": "rule", "metric": "notation_tolerant"},
    # Any other key is an LLM judge taken from CATALOG, prompted with JUDGE_PROMPT.
}
JUDGE_PROMPT_VERSION = "sentence-equivalence-v1"
JUDGE_PROMPT = ("Two {lang} sentences follow. Sentence B is an attempt to restore sentence A. Ignore spelling of "
                "numbers, symbols and punctuation. Do they mean the same thing? Answer YES or NO only.\n\n"
                "A: {gold}\nB: {got}")


def out(obj) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    return 0


def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --- selection --------------------------------------------------------------------------------

def select(pack: list[dict], per_lang: int = 0, methods: tuple[str, ...] = pr.JUDGED) -> list[dict]:
    """Pack items sorted by id; ``per_lang`` > 0 keeps the first N paragraphs of every language."""
    langs = {p["id"]: p["lang"] for p in pr.load_json(pr.SOURCES)["paragraphs"]}
    keep: dict[str, list[str]] = {}
    for pid in sorted(langs):
        keep.setdefault(langs[pid], []).append(pid)
    allowed = {pid for ids in keep.values() for pid in (ids[:per_lang] if per_lang else ids)}
    return [p for p in sorted(pack, key=lambda p: p["id"])
            if p["id"].split("|")[0] in allowed and p["id"].split("|")[1] in methods]


def shard_of(items: list[dict], shard: int, shards: int) -> list[dict]:
    return items[shard::shards]  # round-robin keeps languages and methods spread over shards


def plan(shards: int, judges: list[str], per_lang: int, model: str = DEFAULTS["model"]) -> dict:
    unknown = [j for j in judges if j not in JUDGES and j not in catalog()]
    if unknown or shards < 1 or model not in catalog():
        raise SystemExit(f"bad plan: model={model} shards={shards} unknown judges={unknown}")
    n = len(select(pr.load_json(pr.path("pack", DEFAULTS["seed"])), per_lang))
    llm = [j for j in judges if j not in JUDGES]
    return {"model": model, "shard": list(range(shards)), "items": n, "per_lang": per_lang,
            "models": json.dumps({"model": list(dict.fromkeys([model, *llm]))}, separators=(",", ":")),
            "matrix": json.dumps({"shard": list(range(shards))}, separators=(",", ":")),
            "judges": json.dumps({"judge": llm}, separators=(",", ":")), "has_llm_judge": bool(llm)}


# --- llama-server -----------------------------------------------------------------------------

def ask(prompt: str, url: str, max_tokens: int) -> dict:
    from llama_cmd import extract_answer  # shared: rejects truncated / reasoning-only answers
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "temperature": DEFAULTS["temperature"],
                       "seed": DEFAULTS["llama_seed"], "max_tokens": max_tokens, "stream": False}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    rec: dict = {"status": "error", "answer": None}
    try:
        with urllib.request.urlopen(req, timeout=DEFAULTS["timeout"]) as r:
            payload = json.loads(r.read().decode("utf-8"))
        rec["usage"] = payload.get("usage")
        rec["finish_reason"] = payload["choices"][0].get("finish_reason")
        rec["answer"] = extract_answer(payload)
        rec["status"] = "ok"
    except TimeoutError:
        rec["status"], rec["error"] = "timeout", "timeout"
    except (urllib.error.URLError, ValueError, KeyError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    return rec


def serve(model: str, models_dir: Path, name: str, port: int) -> dict:
    """Start the pinned image on the verified GGUF (``fetch_l3_model.py``) and wait for /health."""
    entry = catalog()[model]
    gguf = models_dir / "model.gguf"
    if not gguf.is_file():
        raise SystemExit(f"{gguf} missing; run scripts/fetch_l3_model.py {model} {gguf} first")
    threads = str(os.cpu_count() or 2)
    cmd = ["docker", "run", "--detach", "--name", name, "-p", f"127.0.0.1:{port}:8080",
           "-v", f"{models_dir.resolve()}:/models:ro", DEFAULTS["llama_image"], "-m", "/models/model.gguf",
           "--host", "0.0.0.0", "--port", "8080", "-c", str(DEFAULTS["context"]), "-t", threads, "-tb", threads,
           "-ngl", "0", "--parallel", "1", "--jinja", "--reasoning-format", "none", "--reasoning", "off"]
    if entry.get("template"):
        cmd[cmd.index(DEFAULTS["llama_image"]):cmd.index(DEFAULTS["llama_image"])] = ["-v", f"{ROOT / 'shared'}:/lab/shared:ro"]
        cmd += ["--chat-template-file", f"/lab/{entry['template']}"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    for _ in range(150):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                if r.status == 200:
                    return {"model": model, "container": name, "threads": threads, "url": f"http://127.0.0.1:{port}/v1/chat/completions"}
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(2)
    subprocess.run(["docker", "logs", name])
    raise SystemExit("llama-server did not become healthy")


def provenance(model: str) -> dict:
    entry = catalog()[model]
    return {"model": model, "repository": entry["repository"], "revision": entry["revision"],
            "filename": entry["filename"], "sha256": entry["sha256"], "llama_image": DEFAULTS["llama_image"],
            "temperature": DEFAULTS["temperature"], "llama_seed": DEFAULTS["llama_seed"],
            "max_tokens": DEFAULTS["max_tokens"], "context": DEFAULTS["context"],
            "git_sha": os.environ.get("GITHUB_SHA"), "runner": platform.platform(), "cpus": os.cpu_count()}


# --- restore / merge / judge ------------------------------------------------------------------

def restore(shard: int, shards: int, model: str, url: str, per_lang: int, workers: int = 1) -> dict:
    pack = pr.load_json(pr.path("pack", DEFAULTS["seed"]))
    todo = shard_of(select(pack, per_lang), shard, shards)
    t0 = time.monotonic()

    def one(p):
        return {"id": p["id"], "prompt_sha256": p["prompt_sha256"], **ask(p["prompt"], url, DEFAULTS["max_tokens"])}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        answers = list(ex.map(one, todo))
    return {"run": pr.RUN, "prompt_version": pr.PROMPT_VERSION, "restore": provenance(model),
            "shard": shard, "shards": shards, "per_lang": per_lang,
            "elapsed_seconds": round(time.monotonic() - t0, 1), "answers": answers}


def merge(files: list[Path]) -> dict:
    shards = [pr.load_json(f) for f in files]
    if not shards:
        raise SystemExit("no shard files")
    models = {json.dumps(s["restore"]["model"]) for s in shards}
    if len(models) != 1 or {s["prompt_version"] for s in shards} != {pr.PROMPT_VERSION}:
        raise SystemExit("shards disagree on restore model or prompt version")
    pack = {p["id"]: p for p in pr.load_json(pr.path("pack", DEFAULTS["seed"]))}
    paras = {p["id"]: p for p in pr.load_json(pr.SOURCES)["paragraphs"]}
    items = {it["paragraph"]: it for it in pr.load_json(pr.path("items"))["items"]}
    answers = {a["id"]: a for s in shards for a in s["answers"]}
    for iid, a in answers.items():
        if a["prompt_sha256"] != pack[iid]["prompt_sha256"]:
            raise SystemExit(f"{iid}: prompt sha256 does not match the pack")
    expected = {a["id"] for a in select(list(pack.values()), shards[0]["per_lang"])}
    summary: dict[str, dict] = {}
    size: dict[str, Counter] = {}
    failures, per_item = [], {}
    for iid in sorted(expected):
        pid, m = iid.split("|")
        para, meth = paras[pid], items[pid]["methods"][m]
        a = answers.get(iid)
        sc = pr.score_answer(para, meth["text"], a["answer"] if a and a["status"] == "ok" else None)
        per_item[iid] = {"status": a["status"] if a else "missing", "answer": a and a["answer"],
                         "elapsed_seconds": a and a.get("elapsed_seconds"), "usage": a and a.get("usage"),
                         **{k: sc[k] for k in ("sentences", "exact", "semantic_rule", "notation_tolerant",
                                                "paragraph_exact", "format_followed", "labels")}}
        z = size.setdefault(m, Counter())
        z["o200k"] += meth["o200k"]; z["bytes"] += meth["bytes"]
        z["o200k_control"] += items[pid]["methods"]["control"]["o200k"]
        z["bytes_control"] += items[pid]["methods"]["control"]["bytes"]
        for scope in ("all", para["lang"]):
            c = summary.setdefault(m, {}).setdefault(scope, Counter())
            c["judgements"] += 1; c["sentences"] += sc["sentences"]
            for k in ("exact", "semantic_rule", "notation_tolerant"):
                c[k] += sc[k]
            c["paragraph_exact"] += int(sc["paragraph_exact"]); c["no_answer"] += int(sc["status"] != "ok")
            for k, v in sc["labels"].items():
                c["label:" + k] += v
        got, _ = pr.split_answer(a["answer"], len(para["sentences"])) if sc["status"] == "ok" else ([], False)
        for row in sc["sentence_rows"]:
            if row["notation_tolerant"]:
                continue
            reasons = [e["label"] for e in row["errors"]] + [e["label"] for e in row["leftovers"]]
            reasons += [row["segmentation"]] if row["segmentation"] else []
            failures.append({"id": iid, "lang": para["lang"], "method": m, "gold_index": row["gold"],
                             "gold": " ".join(para["sentences"][k] for k in row["gold"]),
                             "restored": " ".join(got[k] for k in row["got"]),
                             "reasons": reasons or ["unlabelled"]})
        if sc["status"] != "ok":
            failures.append({"id": iid, "lang": para["lang"], "method": m, "gold_index": list(range(len(para["sentences"]))),
                             "gold": " ".join(para["sentences"]), "restored": "",
                             "reasons": [f"no_answer:{a['status'] if a else 'missing'}"] + ([a.get("error")] if a and a.get("error") else [])})
    out_summary = {}
    for m, scopes in summary.items():
        out_summary[m] = {}
        for scope, c in sorted(scopes.items(), key=lambda kv: (kv[0] != "all", kv[0])):
            n = c["sentences"] or 1
            d = dict(sorted(c.items()))
            d.update({f"{k}_rate": round(c[k] / n, 4) for k in ("exact", "semantic_rule", "notation_tolerant")})
            d["paragraph_exact_rate"] = round(c["paragraph_exact"] / (c["judgements"] or 1), 4)
            out_summary[m][scope] = d
        z = size[m]
        # o200k first, then bytes (standing rule); totals over the selected paragraphs.
        out_summary[m]["size"] = {"o200k": z["o200k"], "bytes": z["bytes"],
                                  "o200k_delta_pct": pr.pct(z["o200k"], z["o200k_control"]),
                                  "bytes_delta_pct": pr.pct(z["bytes"], z["bytes_control"])}
    elapsed = [s["elapsed_seconds"] for s in shards]
    restore_model = shards[0]["restore"]
    return {"run": pr.RUN, "prompt_version": pr.PROMPT_VERSION,
            "ai_readability": {"status": "measured", "restorer": restore_model["model"], "judge": "rule"},
            "restore": restore_model, "shards": len(shards), "shard_elapsed_seconds": elapsed,
            "items_expected": len(expected), "items_answered": sum(1 for i in expected if i in answers),
            "judges": {"rule": JUDGES["rule"]}, "summary": out_summary, "failures": failures, "items": per_item}


def judge(merged: dict, model: str, url: str) -> dict:
    """LLM judge hook: YES/NO equivalence for each sentence that failed notation_tolerant."""
    rows = [f for f in merged["failures"] if f["restored"]]
    asked = []
    for f in rows:
        prompt = JUDGE_PROMPT.format(lang=pr.LANG_NAMES[f["lang"]], gold=f["gold"], got=f["restored"])
        rec = ask(prompt, url, 8)
        verdict = (rec["answer"] or "").strip().upper()
        asked.append({"id": f["id"], "gold_index": f["gold_index"], "status": rec["status"],
                      "verdict": "yes" if verdict.startswith("YES") else "no" if verdict.startswith("NO") else "unparsed",
                      "raw": rec["answer"], "elapsed_seconds": rec["elapsed_seconds"]})
    table: dict[str, Counter] = {}
    for f, a in zip(rows, asked):
        table.setdefault(f["method"], Counter())[a["verdict"]] += len(f["gold_index"])
    summary = {}
    for m, s in merged["summary"].items():
        base = s["all"]
        yes = table.get(m, Counter())["yes"]
        summary[m] = {"sentences": base["sentences"], "notation_tolerant": base["notation_tolerant"],
                      "llm_equivalent": yes, "notation_tolerant_or_llm_rate": round((base["notation_tolerant"] + yes) / (base["sentences"] or 1), 4),
                      "verdicts": dict(table.get(m, Counter()))}
    return {"run": merged["run"], "judge": {"type": "llm", "prompt_version": JUDGE_PROMPT_VERSION, **provenance(model)},
            "restorer": merged["restore"]["model"], "summary": summary, "verdicts": asked}


def markdown(merged: dict, judged: list[dict] | None = None) -> str:
    r = merged["restore"]
    lines = [f"### AI readability ({r['model']}: {r['repository']}@{r['revision'][:8]}, {merged['prompt_version']})", "",
             f"items {merged['items_answered']}/{merged['items_expected']}, shards {merged['shards']}, "
             f"slowest shard {max(merged['shard_elapsed_seconds'])} s", "",
             "| method | o200k Δ | bytes Δ | exact | notation_tolerant | paragraphs exact | no answer |",
             "|---|---|---|---|---|---|---|"]
    for m, s in merged["summary"].items():
        a, z = s["all"], s["size"]
        lines.append(f"| {m} | {z['o200k_delta_pct']:+.2f}% | {z['bytes_delta_pct']:+.2f}% | "
                     f"{a['exact']}/{a['sentences']} ({a['exact_rate']:.2%}) | "
                     f"{a['notation_tolerant']}/{a['sentences']} ({a['notation_tolerant_rate']:.2%}) | "
                     f"{a['paragraph_exact']}/{a['judgements']} | {a['no_answer']} |")
    reasons = Counter(x for f in merged["failures"] for x in f["reasons"])
    lines += ["", "failure reasons: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common(8))]
    for j in judged or []:
        lines += ["", f"LLM judge {j['judge']['model']} ({j['judge']['prompt_version']}): " + ", ".join(
            f"{m} {s['notation_tolerant_or_llm_rate']:.2%}" for m, s in j["summary"].items())]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="action", required=True)
    p = sub.add_parser("plan"); p.add_argument("--shards", type=int, default=8)
    p.add_argument("--per-lang", type=int, default=0); p.add_argument("--judges", default="")
    p.add_argument("--model", default=DEFAULTS["model"])
    p.add_argument("--github-output", type=Path)
    s = sub.add_parser("serve"); s.add_argument("--model", default=DEFAULTS["model"])
    s.add_argument("--models-dir", type=Path, default=ROOT / "models"); s.add_argument("--name", default="qwen-readability")
    s.add_argument("--port", type=int, default=8080)
    r = sub.add_parser("restore"); r.add_argument("--shard", type=int, default=0); r.add_argument("--shards", type=int, default=1)
    r.add_argument("--model", default=DEFAULTS["model"]); r.add_argument("--url", default=DEFAULTS["url"])
    r.add_argument("--per-lang", type=int, default=0); r.add_argument("--workers", type=int, default=1)
    r.add_argument("--out", type=Path, required=True)
    g = sub.add_parser("merge"); g.add_argument("files", nargs="+"); g.add_argument("--out", type=Path, required=True)
    g.add_argument("--markdown", type=Path)
    j = sub.add_parser("judge"); j.add_argument("merged", type=Path); j.add_argument("--model", required=True)
    j.add_argument("--url", default=DEFAULTS["url"]); j.add_argument("--out", type=Path, required=True)
    j.add_argument("--markdown", type=Path)
    a = ap.parse_args(argv)
    if a.action == "plan":
        res = plan(a.shards, [x.strip() for x in a.judges.split(",") if x.strip()], a.per_lang, a.model)
        if a.github_output:
            with a.github_output.open("a", encoding="utf-8") as fh:
                fh.write(f"matrix={res['matrix']}\nmodels={res['models']}\njudges={res['judges']}\nhas_llm_judge={str(res['has_llm_judge']).lower()}\n")
        return out(res)
    if a.action == "serve":
        return out(serve(a.model, a.models_dir, a.name, a.port))
    if a.action == "restore":
        res = restore(a.shard, a.shards, a.model, a.url, a.per_lang, a.workers)
        write(a.out, res)
        return out({k: res[k] for k in ("shard", "shards", "elapsed_seconds")} |
                   {"answers": len(res["answers"]), "ok": sum(x["status"] == "ok" for x in res["answers"]), "out": str(a.out)})
    if a.action == "merge":
        files = sorted(Path(f) for pat in a.files for f in (glob.glob(pat) or [pat]))
        res = merge(files)
        write(a.out, res)
        if a.markdown:
            a.markdown.write_text(markdown(res), encoding="utf-8")
        return out({"ai_readability": res["ai_readability"], "items_answered": res["items_answered"],
                    "items_expected": res["items_expected"],
                    "summary": {m: {"size": s["size"], **{k: s["all"][k] for k in ("exact_rate", "notation_tolerant_rate", "paragraph_exact", "judgements")}}
                                for m, s in res["summary"].items()}, "out": str(a.out)})
    merged = pr.load_json(a.merged)
    res = judge(merged, a.model, a.url)
    write(a.out, res)
    if a.markdown:
        a.markdown.write_text(markdown(merged, [res]), encoding="utf-8")
    return out({"judge": res["judge"]["model"], "summary": res["summary"], "out": str(a.out)})


if __name__ == "__main__":
    sys.exit(main())
