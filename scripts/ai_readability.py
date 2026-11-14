#!/usr/bin/env python3
"""AI readability of TalkCompress paragraphs: a pinned small GGUF restores, rules and an LLM judge score.

The paragraph benchmark (``paragraph_roundtrip.py``, prompt ``paragraph-restore-v1``) is reused
unchanged: the same pack items (control / CEF / BEF) and the same rule scores (exact,
semantic_rule, notation_tolerant, error labels). New here: the restorer is a local model behind
llama.cpp ``llama-server`` on CPU, and an LLM judge re-reads every aligned sentence pair, reported
next to the rules with its agreement. Models are catalog keys (``shared/l3_models.json``), so the
restorer and the judge can be swapped without code changes. Every subcommand prints JSON.

One entry point for uv, olnm, CI or an agent (paths come from ``__file__``)::

    uv run python scripts/ai_readability.py plan --preset pr-smoke [--restorers KEY,..] [--judges KEY,..]
    uv run python scripts/ai_readability.py build-llama --dest llama-bin      # optional, pinned commit
    uv run python scripts/ai_readability.py serve --model KEY [--llama-bin llama-bin/llama-server]
    uv run python scripts/ai_readability.py restore --shard 0 --shards 8 --out out/shard-0.json
    uv run python scripts/ai_readability.py merge 'out/shard-*.json' --out out/readability.json
    uv run python scripts/ai_readability.py judge out/readability.json --model KEY --out out/judge-KEY-0.json
    uv run python scripts/ai_readability.py report out/readability.json 'out/judge-*.json' --out out/report.json
    uv run python scripts/ai_readability.py stop --log out/llama-server.log

Central definitions (the one place to change, conftest-style): ``DEFAULTS`` below and the model
catalog. Traceability: shard files keep every prompt, compressed text, raw server response and
the pins (model revision + SHA-256, llama image digest or build commit, git SHA, sha256 of the
pack / items / sources files); ``merge``, ``judge`` and ``report`` are pure functions of those
files, so any number in ``report.json`` can be re-derived from the artifacts.

Determinism: temperature 0 and a fixed seed, so seeds are not repeated (greedy decoding would give
identical answers). Digits/symbols differences are not errors (``notation_tolerant``, t1208).
"""
from __future__ import annotations

import argparse, glob, hashlib, json, os, platform, shutil, subprocess, sys, time, urllib.error, urllib.request
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
    # 暫定 (provisional) judge: LiquidAI LFM2.5-1.2B, not Qwen-family, already pinned and run by SVG L3.
    # The judge choice is still open (non-Qwen candidates under evaluation); swap the key here or per run.
    "judges": ["lfm2.5-1.2b-qad"],
    "seed": 1,                          # pack file that supplies the prompts (content is identical across seeds)
    "temperature": 0, "llama_seed": 42, "max_tokens": 1024, "judge_max_tokens": 8, "context": 4096,
    "timeout": 600, "port": 8080, "name": "ai-readability",
    # llama.cpp, two pinned ways: official image b12004 by OCI digest (same as svg-l3-matrix / mcp-toolcall-lab),
    # or a build from a pinned commit (b12381, the build 2bot's restorer bench used for Qwen3) for newer models.
    "llama_image": "ghcr.io/ggml-org/llama.cpp@sha256:b32890309c1a33a534a01b0b461e953dc2c5a6bac20213abcf48e22847a19c85",
    "llama_image_commit": "3c809f44383bcebc318b8cddd8c6d11aaa861e9b",
    "llama_commit": "9d925e7c02eb4e2e0da5be64a982cf79f9103fc7",
}
# Named presets: models per purpose (t1234u). The restorer default is 暫定 (myon has not decided):
# Qwen3-0.6B Q8_0, recommended by 2bot's restorer bench; Qwen2.5-1.5B paraphrased even the control.
# per_lang = paragraphs per language (0 = all 60 paragraphs = 180 items). Every field can be overridden per run.
PRESETS = {
    "pr-smoke": {"restorers": ["qwen3-0.6b"], "per_lang": 1, "shards": 4, "llama": "image"},
    "accuracy": {"restorers": ["qwen3-1.7b"], "per_lang": 2, "shards": 8, "llama": "build"},
    "full": {"restorers": ["qwen3-0.6b"], "per_lang": 0, "shards": 8, "llama": "build"},
    "full-pair": {"restorers": ["qwen3-0.6b", "qwen3-1.7b"], "per_lang": 0, "shards": 8, "llama": "build"},
}
DEFAULT_PRESET = "pr-smoke"
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


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def expand(patterns: list[str]) -> list[Path]:
    return sorted({Path(f) for pat in patterns for f in (glob.glob(pat) or [pat])})


# --- selection --------------------------------------------------------------------------------

def select(pack: list[dict], per_lang: int = 0, methods: tuple[str, ...] = pr.JUDGED) -> list[dict]:
    """Pack items sorted by id; ``per_lang`` > 0 keeps the first N paragraphs of every language."""
    keep: dict[str, list[str]] = {}
    for p in sorted(pr.load_json(pr.SOURCES)["paragraphs"], key=lambda p: p["id"]):
        keep.setdefault(p["lang"], []).append(p["id"])
    allowed = {pid for ids in keep.values() for pid in (ids[:per_lang] if per_lang else ids)}
    return [p for p in sorted(pack, key=lambda p: p["id"])
            if p["id"].split("|")[0] in allowed and p["id"].split("|")[1] in methods]


def shard_of(items: list, shard: int, shards: int) -> list:
    return items[shard::shards]  # round-robin keeps languages and methods spread over shards


def plan(preset: str = DEFAULT_PRESET, *, restorers: list[str] | None = None, judges: list[str] | None = None,
         per_lang: int | None = None, shards: int | None = None, llama: str | None = None) -> dict:
    """Resolve a preset (+ overrides) into GitHub matrices; cache keys use each model's SHA-256."""
    if preset not in PRESETS:
        raise SystemExit(f"unknown preset {preset!r}; choose from {', '.join(PRESETS)}")
    cfg = {**PRESETS[preset], "judges": DEFAULTS["judges"]}
    for k, v in {"restorers": restorers, "judges": judges, "per_lang": per_lang, "shards": shards, "llama": llama}.items():
        if v not in (None, [], ""):
            cfg[k] = v
    cat = catalog()
    unknown = [k for k in [*cfg["restorers"], *cfg["judges"]] if k not in cat]
    if unknown or cfg["shards"] < 1 or not cfg["judges"] or not cfg["restorers"] or cfg["llama"] not in ("image", "build"):
        raise SystemExit(f"bad plan {cfg}; unknown catalog keys={unknown}")
    n = len(select(pr.load_json(pr.path("pack", DEFAULTS["seed"])), cfg["per_lang"]))
    c = lambda o: json.dumps(o, separators=(",", ":"))  # noqa: E731
    sha = lambda k: cat[k]["sha256"]  # noqa: E731
    shard_ids = range(cfg["shards"])
    return {"preset": preset, **cfg, "llama_commit": DEFAULTS["llama_commit"], "items_per_restorer": n,
            "models": c({"include": [{"model": k, "sha256": sha(k)} for k in dict.fromkeys([*cfg["restorers"], *cfg["judges"]])]}),
            "restore_matrix": c({"include": [{"restorer": r, "sha256": sha(r), "shard": s} for r in cfg["restorers"] for s in shard_ids]}),
            "restorer_matrix": c({"restorer": cfg["restorers"]}),
            "judge_matrix": c({"include": [{"restorer": r, "judge": j, "sha256": sha(j), "shard": s}
                                           for r in cfg["restorers"] for j in cfg["judges"] for s in shard_ids]})}


# --- llama.cpp ------------------------------------------------------------------------------------

def build_llama(dest: Path, commit: str = DEFAULTS["llama_commit"]) -> dict:
    """Build ``llama-server`` (CPU, portable AVX2) from a pinned commit; git checks the commit hash."""
    src = dest.parent / f"llama.cpp-{commit[:12]}"
    if not (dest / "llama-server").is_file():
        src.mkdir(parents=True, exist_ok=True)
        run = lambda *a: subprocess.run(a, cwd=src, check=True)  # noqa: E731
        run("git", "init", "-q"); run("git", "fetch", "-q", "--depth", "1", "https://github.com/ggml-org/llama.cpp", commit)
        run("git", "checkout", "-q", "FETCH_HEAD")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, check=True, capture_output=True, text=True).stdout.strip()
        if head != commit:
            raise SystemExit(f"fetched {head}, expected {commit}")
        run("cmake", "-S", ".", "-B", "build", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF",
            "-DGGML_NATIVE=OFF", "-DGGML_AVX2=ON", "-DGGML_FMA=ON", "-DGGML_F16C=ON", "-DLLAMA_CURL=OFF",
            "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF")
        run("cmake", "--build", "build", "--target", "llama-server", "-j", str(os.cpu_count() or 2))
        dest.mkdir(parents=True, exist_ok=True)
        for f in (src / "build/bin").iterdir():
            shutil.copy2(f, dest / f.name)
        shutil.rmtree(src)
    receipt = {"llama": "build", "llama_commit": commit, "binary": str(dest / "llama-server"),
               "binary_sha256": file_sha(dest / "llama-server")}
    write(dest / "provenance.json", receipt)
    return receipt


def llama_pin(llama_bin: Path | None) -> dict:
    if llama_bin:
        rec = pr.load_json(llama_bin.parent / "provenance.json")
        return {"llama": "build", "llama_commit": rec["llama_commit"], "binary_sha256": rec["binary_sha256"]}
    return {"llama": "image", "llama_image": DEFAULTS["llama_image"], "llama_commit": DEFAULTS["llama_image_commit"]}


def serve(model: str, models_dir: Path, llama_bin: Path | None, log: Path) -> dict:
    """Start llama-server on the verified GGUF (``fetch_l3_model.py``) and wait for /health."""
    entry, gguf = catalog()[model], models_dir / "model.gguf"
    if not gguf.is_file():
        raise SystemExit(f"{gguf} missing; run scripts/fetch_l3_model.py {model} {gguf} first")
    threads, port = str(os.cpu_count() or 2), DEFAULTS["port"]
    args = ["-c", str(DEFAULTS["context"]), "-t", threads, "-tb", threads, "-ngl", "0", "--parallel", "1",
            "--jinja", "--reasoning-format", "none", "--reasoning", "off"]
    template = entry.get("template")
    if llama_bin:
        args = ["-m", str(gguf.resolve()), "--host", "127.0.0.1", "--port", str(port), *args]
        if template:
            args += ["--chat-template-file", str(ROOT / template)]
        log.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([str(llama_bin.resolve()), *args], stdout=log.open("wb"), stderr=subprocess.STDOUT,
                                start_new_session=True)
        (log.parent / "llama-server.pid").write_text(str(proc.pid))
    else:
        cmd = ["docker", "run", "--detach", "--name", DEFAULTS["name"], "-p", f"127.0.0.1:{port}:8080",
               "-v", f"{models_dir.resolve()}:/models:ro", "-v", f"{ROOT / 'shared'}:/lab/shared:ro", DEFAULTS["llama_image"],
               "-m", "/models/model.gguf", "--host", "0.0.0.0", "--port", "8080", *args]
        if template:
            cmd += ["--chat-template-file", f"/lab/{template}"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    for _ in range(150):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                if r.status == 200:
                    return {"model": model, "threads": threads, **llama_pin(llama_bin),
                            "url": f"http://127.0.0.1:{port}/v1/chat/completions"}
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(2)
    stop(log)
    raise SystemExit(f"llama-server did not become healthy; see {log}")


def stop(log: Path) -> dict:
    pid = log.parent / "llama-server.pid"
    if pid.is_file():
        try:
            os.kill(int(pid.read_text()), 15)
        except ProcessLookupError:
            pass
        pid.unlink()
        return {"stopped": "process", "log": str(log)}
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as fh:
        subprocess.run(["docker", "logs", DEFAULTS["name"]], stdout=fh, stderr=subprocess.STDOUT)
    subprocess.run(["docker", "rm", "-f", DEFAULTS["name"]], capture_output=True)
    return {"stopped": "container", "log": str(log)}


def ask(prompt: str, url: str, max_tokens: int) -> dict:
    from llama_cmd import extract_answer  # shared: rejects truncated / reasoning-only answers
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "temperature": DEFAULTS["temperature"],
                       "seed": DEFAULTS["llama_seed"], "max_tokens": max_tokens, "stream": False,
                       # Thinking off for Qwen3-style templates (the server also runs with --reasoning off).
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    rec: dict = {"status": "error", "answer": None}
    try:
        with urllib.request.urlopen(req, timeout=DEFAULTS["timeout"]) as r:
            payload = json.loads(r.read().decode("utf-8"))
        rec["response"] = payload  # raw server response, kept for re-derivation
        rec["answer"] = extract_answer(payload)
        rec["status"] = "ok"
    except TimeoutError:
        rec["status"], rec["error"] = "timeout", "timeout"
    except (urllib.error.URLError, ValueError, KeyError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    return rec


def provenance(model: str, llama: dict) -> dict:
    entry = catalog()[model]
    inputs = {p.name: file_sha(p) for p in (pr.SOURCES, pr.path("items"), pr.path("pack", DEFAULTS["seed"]))}
    return {"model": model, **{k: entry[k] for k in ("repository", "revision", "filename", "bytes", "sha256")},
            **{k: llama[k] for k in llama if k.startswith(("llama", "binary"))},
            **{k: DEFAULTS[k] for k in ("temperature", "llama_seed", "context")},
            "inputs_sha256": inputs, "git_sha": os.environ.get("GITHUB_SHA"),
            "run_url": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                        if os.environ.get("GITHUB_RUN_ID") else None),
            "runner": platform.platform(), "cpus": os.cpu_count()}


# --- restore / merge / judge / report ---------------------------------------------------------

def restore(shard: int, shards: int, model: str, url: str, per_lang: int, llama: dict, workers: int = 1) -> dict:
    todo = shard_of(select(pr.load_json(pr.path("pack", DEFAULTS["seed"])), per_lang), shard, shards)
    t0 = time.monotonic()

    def one(p):
        return {"id": p["id"], "prompt_sha256": p["prompt_sha256"], "compressed_text": p["compressed_text"],
                "prompt": p["prompt"], **ask(p["prompt"], url, DEFAULTS["max_tokens"])}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        answers = list(ex.map(one, todo))
    return {"run": pr.RUN, "prompt_version": pr.PROMPT_VERSION, "restore": provenance(model, llama),
            "max_tokens": DEFAULTS["max_tokens"], "shard": shard, "shards": shards, "per_lang": per_lang,
            "elapsed_seconds": round(time.monotonic() - t0, 1), "answers": answers}


def _rates(c: Counter) -> dict:
    n = c["sentences"] or 1
    d = dict(sorted(c.items()))
    d.update({f"{k}_rate": round(c[k] / n, 4) for k in ("exact", "semantic_rule", "notation_tolerant")})
    d["paragraph_exact_rate"] = round(c["paragraph_exact"] / (c["judgements"] or 1), 4)
    return d


def merge(files: list[Path]) -> dict:
    shards = [pr.load_json(f) for f in files]
    if not shards:
        raise SystemExit("no shard files")
    pins = {json.dumps({k: v for k, v in s["restore"].items() if k not in ("runner", "cpus")}, sort_keys=True) for s in shards}
    if len(pins) != 1 or {s["prompt_version"] for s in shards} != {pr.PROMPT_VERSION}:
        raise SystemExit("shards disagree on restore pins or prompt version")
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
    pairs, failures, per_item = [], [], {}
    for iid in sorted(expected):
        pid, m = iid.split("|")
        para, meth = paras[pid], items[pid]["methods"][m]
        a = answers.get(iid)
        ok = bool(a and a["status"] == "ok")
        sc = pr.score_answer(para, meth["text"], a["answer"] if ok else None)
        per_item[iid] = {"status": a["status"] if a else "missing", "answer": a["answer"] if a else None,
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
            c["paragraph_exact"] += int(sc["paragraph_exact"]); c["no_answer"] += int(not ok)
            for k, v in sc["labels"].items():
                c["label:" + k] += v
        got = pr.split_answer(a["answer"], len(para["sentences"]))[0] if ok else []
        for row in sc["sentence_rows"]:
            reasons = [e["label"] for e in row["errors"]] + [e["label"] for e in row["leftovers"]]
            reasons += [row["segmentation"]] if row["segmentation"] else []
            pair = {"id": iid, "lang": para["lang"], "method": m, "gold_index": row["gold"], "got_index": row["got"],
                    "gold": " ".join(para["sentences"][k] for k in row["gold"]),
                    "restored": " ".join(got[k] for k in row["got"]),
                    "exact": row["exact"], "notation_tolerant": row["notation_tolerant"], "reasons": reasons}
            pairs.append(pair)
            if not row["notation_tolerant"] and row["gold"]:
                failures.append({**pair, "reasons": reasons or ["unlabelled"]})
        if not ok:
            failures.append({"id": iid, "lang": para["lang"], "method": m, "gold_index": list(range(len(para["sentences"]))),
                             "got_index": [], "gold": " ".join(para["sentences"]), "restored": "", "exact": False,
                             "notation_tolerant": False,
                             "reasons": [f"no_answer:{a['status'] if a else 'missing'}"] + ([a["error"]] if a and a.get("error") else [])})
    out_summary = {}
    for m, scopes in summary.items():
        out_summary[m] = {scope: _rates(c) for scope, c in sorted(scopes.items(), key=lambda kv: (kv[0] != "all", kv[0]))}
        z = size[m]  # o200k first, then bytes (standing rule); totals over the selected paragraphs
        out_summary[m]["size"] = {"o200k": z["o200k"], "bytes": z["bytes"],
                                  "o200k_delta_pct": pr.pct(z["o200k"], z["o200k_control"]),
                                  "bytes_delta_pct": pr.pct(z["bytes"], z["bytes_control"])}
    return {"run": pr.RUN, "prompt_version": pr.PROMPT_VERSION, "restore": shards[0]["restore"],
            "shard_files": {f.name: file_sha(f) for f in files}, "per_lang": shards[0]["per_lang"],
            "shards": len(shards), "shard_elapsed_seconds": [s["elapsed_seconds"] for s in shards],
            "items_expected": len(expected), "items_answered": sum(1 for i in expected if i in answers),
            "summary": out_summary, "pairs": pairs, "failures": failures, "items": per_item}


def judge(merged: dict, model: str, url: str, llama: dict, shard: int = 0, shards: int = 1) -> dict:
    """Ask the judge, for every aligned (gold, restored) sentence pair, whether the meaning is kept."""
    todo = shard_of([p for p in merged["pairs"] if p["gold_index"] and p["got_index"]], shard, shards)
    t0, verdicts = time.monotonic(), []
    for p in todo:
        prompt = JUDGE_PROMPT.format(lang=pr.LANG_NAMES[p["lang"]], gold=p["gold"], got=p["restored"])
        rec = ask(prompt, url, DEFAULTS["judge_max_tokens"])
        text = (rec["answer"] or "").strip().upper()
        verdicts.append({"id": p["id"], "gold_index": p["gold_index"], "prompt_sha256": pr.sha256(prompt),
                         "verdict": "yes" if text.startswith("YES") else "no" if text.startswith("NO") else "unparsed",
                         **rec})
    return {"run": merged["run"], "judge": {"prompt_version": JUDGE_PROMPT_VERSION, "prompt": JUDGE_PROMPT,
                                            "max_tokens": DEFAULTS["judge_max_tokens"], **provenance(model, llama)},
            "restorer": merged["restore"]["model"], "readability_sha256": pr.sha256(json.dumps(merged, sort_keys=True)),
            "shard": shard, "shards": shards, "elapsed_seconds": round(time.monotonic() - t0, 1), "verdicts": verdicts}


def report(merged: dict, judge_files: list[Path]) -> dict:
    """Rules (baseline) and every judge side by side, with judge-vs-notation_tolerant agreement."""
    by_judge: dict[str, list[dict]] = {}
    for f in judge_files:
        j = pr.load_json(f)
        by_judge.setdefault(j["judge"]["model"], []).append(j)
    judges = {}
    for key, parts in by_judge.items():
        verdict = {(v["id"], tuple(v["gold_index"])): v["verdict"] for j in parts for v in j["verdicts"]}
        table: dict[str, Counter] = {}
        for p in merged["pairs"]:
            if not p["gold_index"]:
                continue
            n, c = len(p["gold_index"]), table.setdefault(p["method"], Counter())
            v = verdict.get((p["id"], tuple(p["gold_index"])), "no" if not p["got_index"] else "missing")
            rule = "pass" if p["notation_tolerant"] else "fail"
            c["sentences"] += n; c[f"judge_{v}"] += n; c[f"rule_{rule}_judge_{v}"] += n
        for f in merged["failures"]:  # no answer at all: both the rules and the judge count it as lost
            if f["reasons"][0].startswith("no_answer"):
                c, n = table.setdefault(f["method"], Counter()), len(f["gold_index"])
                c["sentences"] += n; c["judge_no"] += n; c["rule_fail_judge_no"] += n
        summ = {}
        for m, c in table.items():
            n = c["sentences"] or 1
            agree = c["rule_pass_judge_yes"] + c["rule_fail_judge_no"]
            summ[m] = {**dict(sorted(c.items())), "judge_equivalent_rate": round(c["judge_yes"] / n, 4),
                       "agreement_rate": round(agree / n, 4),
                       "rule_pass_judge_no": c["rule_pass_judge_no"], "rule_fail_judge_yes": c["rule_fail_judge_yes"]}
        judges[key] = {"pins": {k: v for k, v in parts[0]["judge"].items() if k not in ("runner", "cpus", "prompt")},
                       "shards": len(parts), "shard_elapsed_seconds": [j["elapsed_seconds"] for j in parts],
                       "judge_files": {f.name: file_sha(f) for f in judge_files if pr.load_json(f)["judge"]["model"] == key},
                       "summary": summ}
    return {"run": merged["run"], "prompt_version": merged["prompt_version"],
            "ai_readability": {"status": "measured", "restorer": merged["restore"]["model"],
                               "judges": ["rule", *judges]},
            "restore": merged["restore"], "readability_sha256": pr.sha256(json.dumps(merged, sort_keys=True)),
            "items_expected": merged["items_expected"], "items_answered": merged["items_answered"],
            "shard_elapsed_seconds": merged["shard_elapsed_seconds"],
            "rule": {m: {"size": s["size"], **s["all"]} for m, s in merged["summary"].items()},
            "judges": judges, "failure_reasons": dict(Counter(x for f in merged["failures"] for x in f["reasons"]).most_common())}


def markdown(rep: dict) -> str:
    r = rep["restore"]
    pin = r.get("llama_image") or f"llama.cpp build {r['llama_commit'][:12]}"
    lines = [f"### AI readability: restorer {r['model']} ({r['repository']}@{r['revision'][:8]}), {rep['prompt_version']}", "",
             f"items {rep['items_answered']}/{rep['items_expected']}, slowest restore shard {max(rep['shard_elapsed_seconds'])} s, {pin}", "",
             "| method | o200k Δ | bytes Δ | exact | notation_tolerant | paragraphs exact | no answer |", "|---|---|---|---|---|---|---|"]
    for m, a in rep["rule"].items():
        z = a["size"]
        lines.append(f"| {m} | {z['o200k_delta_pct']:+.2f}% | {z['bytes_delta_pct']:+.2f}% | "
                     f"{a['exact']}/{a['sentences']} ({a['exact_rate']:.2%}) | "
                     f"{a['notation_tolerant']}/{a['sentences']} ({a['notation_tolerant_rate']:.2%}) | "
                     f"{a['paragraph_exact']}/{a['judgements']} | {a['no_answer']} |")
    for key, j in rep["judges"].items():
        lines += ["", f"judge {key} ({j['pins']['prompt_version']}, slowest shard {max(j['shard_elapsed_seconds'])} s)", "",
                  "| method | judge equivalent | agreement with notation_tolerant | rule pass / judge no | rule fail / judge yes | unparsed |",
                  "|---|---|---|---|---|---|"]
        for m, s in j["summary"].items():
            lines.append(f"| {m} | {s['judge_yes']}/{s['sentences']} ({s['judge_equivalent_rate']:.2%}) | {s['agreement_rate']:.2%} | "
                         f"{s['rule_pass_judge_no']} | {s['rule_fail_judge_yes']} | {s.get('judge_unparsed', 0) + s.get('judge_missing', 0)} |")
    lines += ["", "failure reasons (rule): " + ", ".join(f"{k} {v}" for k, v in list(rep["failure_reasons"].items())[:8])]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="action", required=True)
    p = sub.add_parser("plan"); p.add_argument("--preset", default=DEFAULT_PRESET, choices=list(PRESETS))
    p.add_argument("--restorers", default="", help="comma list of catalog keys (overrides the preset)")
    p.add_argument("--judges", default="", help="comma list of catalog keys (default: DEFAULTS judges)")
    p.add_argument("--shards", type=int); p.add_argument("--per-lang", type=int)
    p.add_argument("--llama", choices=["image", "build"]); p.add_argument("--github-output", type=Path)
    b = sub.add_parser("build-llama"); b.add_argument("--dest", type=Path, default=ROOT / "llama-bin")
    b.add_argument("--commit", default=DEFAULTS["llama_commit"])
    llama = argparse.ArgumentParser(add_help=False)
    llama.add_argument("--llama-bin", type=Path, help="built llama-server (default: the pinned docker image)")
    s = sub.add_parser("serve", parents=[llama]); s.add_argument("--model", default=PRESETS[DEFAULT_PRESET]["restorers"][0])
    s.add_argument("--models-dir", type=Path); s.add_argument("--log", type=Path, default=Path("out/llama-server.log"))
    t = sub.add_parser("stop"); t.add_argument("--log", type=Path, default=Path("out/llama-server.log"))
    r = sub.add_parser("restore", parents=[llama]); r.add_argument("--shard", type=int, default=0)
    r.add_argument("--shards", type=int, default=1); r.add_argument("--model", default=PRESETS[DEFAULT_PRESET]["restorers"][0])
    r.add_argument("--url", default=f"http://127.0.0.1:{DEFAULTS['port']}/v1/chat/completions")
    r.add_argument("--per-lang", type=int, default=0); r.add_argument("--workers", type=int, default=1)
    r.add_argument("--out", type=Path, required=True)
    g = sub.add_parser("merge"); g.add_argument("files", nargs="+"); g.add_argument("--out", type=Path, required=True)
    j = sub.add_parser("judge", parents=[llama]); j.add_argument("merged", type=Path); j.add_argument("--model", required=True)
    j.add_argument("--url", default=f"http://127.0.0.1:{DEFAULTS['port']}/v1/chat/completions")
    j.add_argument("--shard", type=int, default=0); j.add_argument("--shards", type=int, default=1)
    j.add_argument("--out", type=Path, required=True)
    e = sub.add_parser("report"); e.add_argument("merged", type=Path); e.add_argument("judge_files", nargs="*")
    e.add_argument("--out", type=Path, required=True); e.add_argument("--markdown", type=Path)
    a = ap.parse_args(argv)
    if a.action == "plan":
        keys = lambda v: [x.strip() for x in v.split(",") if x.strip()]  # noqa: E731
        res = plan(a.preset, restorers=keys(a.restorers), judges=keys(a.judges), per_lang=a.per_lang,
                   shards=a.shards, llama=a.llama)
        if a.github_output:
            with a.github_output.open("a", encoding="utf-8") as fh:
                for k in ("preset", "llama", "llama_commit", "per_lang", "shards", "models", "restore_matrix",
                          "restorer_matrix", "judge_matrix"):
                    fh.write(f"{k}={res[k]}\n")
        return out(res)
    if a.action == "build-llama":
        return out(build_llama(a.dest, a.commit))
    if a.action == "serve":
        return out(serve(a.model, a.models_dir or ROOT / "models" / a.model, a.llama_bin, a.log))
    if a.action == "stop":
        return out(stop(a.log))
    if a.action == "restore":
        res = restore(a.shard, a.shards, a.model, a.url, a.per_lang, llama_pin(a.llama_bin), a.workers)
        write(a.out, res)
        return out({k: res[k] for k in ("shard", "shards", "elapsed_seconds")} |
                   {"answers": len(res["answers"]), "ok": sum(x["status"] == "ok" for x in res["answers"]), "out": str(a.out)})
    if a.action == "merge":
        res = merge(expand(a.files))
        write(a.out, res)
        return out({k: res[k] for k in ("items_answered", "items_expected")} | {"restorer": res["restore"]["model"], "out": str(a.out)})
    if a.action == "judge":
        res = judge(pr.load_json(a.merged), a.model, a.url, llama_pin(a.llama_bin), a.shard, a.shards)
        write(a.out, res)
        return out({"judge": a.model, "shard": a.shard, "verdicts": dict(Counter(v["verdict"] for v in res["verdicts"])),
                    "elapsed_seconds": res["elapsed_seconds"], "out": str(a.out)})
    res = report(pr.load_json(a.merged), [f for f in expand(a.judge_files) if f.is_file()])
    write(a.out, res)
    if a.markdown:
        a.markdown.write_text(markdown(res), encoding="utf-8")
    return out({k: res[k] for k in ("ai_readability", "rule")} |
               {"judges": {k: v["summary"] for k, v in res["judges"].items()}, "out": str(a.out)})


if __name__ == "__main__":
    sys.exit(main())
