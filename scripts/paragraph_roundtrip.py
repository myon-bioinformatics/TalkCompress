"""Paragraph-level (multi-sentence) round-trip benchmark: how much a paragraph shrinks and how
well a blind AI judge restores it.

Every earlier round-trip (scripts/roundtrip.py and the roundtrip_judge/* studies) put one
sentence in front of the judge per call. Here the judge gets a whole compressed paragraph
(3-6 sentences) and must give back the original paragraph, one sentence per line.

Data (``SentenceCalibratedMosaic/fixtures/paragraph_judge/``, see its README.md)::

    sources.json              60 paragraphs with gold sentence lists (build_paragraph_sources.py)
    <run>_items.json          compressed text + o200k tokens / UTF-8 bytes for every method
    <run>_seed<N>_pack.json   judge input for seed N: 180 items {id, prompt, compressed_text, ...}
    <run>_seed<N>_raw.json    judge answers, written by the helper that ran seed N
    <run>_seed<N>_blind.json  {id: answer}, validated by ``ingest`` (replay source)
    <run>_results.json        scores (``score``)

Methods (DensityFacadeRoute layers, CLI defaults)::

    control  uncompressed text (judged: measures how much the judge itself rewrites)
    C        ShorthandSessionEdge                       (tokens/bytes only)
    E        MorphoGrammarMinimal                       (tokens/bytes only)
    CE       C,E                                        (tokens/bytes only)
    CEF      C,E,B-final-zh-de  (= --auto for Latin-script prose)   (judged)
    BEF      B,E,B-final-zh-de                          (judged)

Scoring is rule-based and offline (stdlib only): sentence exact match under
``roundtrip.norm`` after an order-preserving alignment (difflib similarity, 1-1 / 2-1 / 1-2 /
skip moves), paragraph exact, a looser rule-based "semantic" match, an error taxonomy and a
per-substitution attribution (which source span -> compressed span preceded each error).
AI readability is not measured here (``"未測定"``).

``tiktoken`` (dev group) is imported lazily and only by ``build`` to count tokens.

Usage::

    uv run python scripts/paragraph_roundtrip.py build [--check]
    uv run python scripts/paragraph_roundtrip.py ingest --seed 1
    uv run python scripts/paragraph_roundtrip.py score [--check]
    uv run python scripts/paragraph_roundtrip.py run --seed 1 --cmd 'my-llm'   # optional local judge
    uv run python scripts/paragraph_roundtrip.py status
"""
from __future__ import annotations

import argparse, difflib, hashlib, importlib.util, json, os, random, re, subprocess, sys, unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "SentenceCalibratedMosaic/fixtures/paragraph_judge"
SOURCES = DIR / "sources.json"
RUN = "para20261113"
SEEDS = (1, 2, 3)

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from roundtrip import norm  # noqa: E402  (same normaliser as the sentence round-trips)

# ---------------------------------------------------------------------------------------------
# Official paragraph restore prompt (approved by the owner 2026-11-13, t1203). Changing the text
# is a new prompt version: bump PROMPT_VERSION and rebuild the packs; old answers stay tied to
# the prompt sha256 recorded in each pack item.
PROMPT_VERSION = "paragraph-restore-v1"
PROMPT = (
    "The following paragraph was written in {lang} and may have been compressed: some words may be "
    "abbreviated, replaced by symbols, or swapped for short forms from other languages, and subject "
    "pronouns may be dropped. It may also be unchanged. Rewrite it as the original plain {lang} "
    "paragraph, one sentence per line, in the original order. Reply with the paragraph only.\n\n{c}"
)
LANG_NAMES = {"en": "English", "de": "German", "es": "Spanish", "fr": "French", "pt": "Portuguese",
              "ja": "Japanese", "zh": "Chinese", "it": "Italian", "nl": "Dutch", "el": "Greek",
              "cs": "Czech", "pl": "Polish", "la": "Latin"}

FINAL = "B-final-zh-de"
METHODS = {"control": [], "C": ["C"], "E": ["E"], "CE": ["C", "E"],
           "CEF": ["C", "E", FINAL], "BEF": ["B", "E", FINAL]}
JUDGED = ("control", "CEF", "BEF")
AI_READABILITY = "未測定"
# Labels that do not change meaning; they are reported but never count against a substitution.
BENIGN = {"contraction_or_variant"}


def prompt_for(lang: str, compressed: str) -> str:
    return PROMPT.format(lang=LANG_NAMES[lang], c=compressed)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def dumps(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def path(kind: str, seed: int | None = None, d: Path | None = None) -> Path:
    d = d or DIR
    return d / (f"{RUN}_{kind}.json" if seed is None else f"{RUN}_seed{seed}_{kind}.json")


# --- compression -------------------------------------------------------------------------------

_DZ = None


def density():
    """DensityFacadeRoute with a per-process layer cache (the CLI re-executes each layer per hop)."""
    global _DZ
    if _DZ is None:
        cache: dict[str, object] = {}

        def load(name: str, rel: str):
            if name not in cache:
                spec = importlib.util.spec_from_file_location(name, ROOT / rel)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                spec.loader.exec_module(mod)
                cache[name] = mod
            sys.modules[name] = cache[name]
            return cache[name]

        for p in ("", "shared", "TokenCostHeuristic", "RulePeerCodec", "SentenceCalibratedMosaic",
                  "ShorthandSessionEdge", "DensityFacadeRoute", "MorphoGrammarMinimal"):
            q = str(ROOT / p) if p else str(ROOT)
            if q not in sys.path:
                sys.path.insert(0, q)
        _DZ = load("density_facade_route", "DensityFacadeRoute/density_facade_route.py")
        _DZ._load = load
    return _DZ


def compress(method: str, text: str) -> str:
    layers = METHODS[method]
    if not layers:
        return text
    dz = density()
    return dz.run_pipeline(list(layers), text, dz.build_parser().parse_args([]))


_ENC = None


def o200k(s: str) -> int:
    global _ENC
    if _ENC is None:
        import tiktoken  # dev group only

        _ENC = tiktoken.get_encoding("o200k_base")
    return len(_ENC.encode(s))


def pct(new: int, old: int) -> float:
    return round(100.0 * (new - old) / old, 2) if old else 0.0


def build_items(sources: dict, *, tokens=o200k, comp=compress) -> dict:
    items = []
    for p in sources["paragraphs"]:
        t0, b0 = tokens(p["text"]), len(p["text"].encode("utf-8"))
        methods = {}
        for m in METHODS:
            out = comp(m, p["text"])
            t, b = tokens(out), len(out.encode("utf-8"))
            methods[m] = {"text": out, "o200k": t, "bytes": b, "o200k_delta_pct": pct(t, t0),
                          "bytes_delta_pct": pct(b, b0), "unchanged": out == p["text"],
                          "judged": m in JUDGED}
        items.append({"paragraph": p["id"], "lang": p["lang"], "group": p["group"],
                      "n_sentences": len(p["sentences"]), "o200k": t0, "bytes": b0, "methods": methods})
    summary = {}
    for m in METHODS:
        for scope, rows in [("all", items)] + [(lang, [i for i in items if i["lang"] == lang])
                                               for lang in sorted({i["lang"] for i in items})]:
            t0 = sum(i["o200k"] for i in rows); b0 = sum(i["bytes"] for i in rows)
            t = sum(i["methods"][m]["o200k"] for i in rows); b = sum(i["methods"][m]["bytes"] for i in rows)
            summary.setdefault(m, {})[scope] = {"paragraphs": len(rows), "o200k": [t0, t], "bytes": [b0, b],
                                                "o200k_delta_pct": pct(t, t0), "bytes_delta_pct": pct(b, b0)}
    return {"run": RUN, "methods": {m: ",".join(v) or "identity" for m, v in METHODS.items()},
            "judged_methods": list(JUDGED), "sources_sha256": sha256(dumps(sources)),
            "tokenizer": "o200k_base (tiktoken), whole paragraph, no leading space",
            "items": items, "summary": summary}


def item_id(pid: str, method: str) -> str:
    return f"{pid}|{method}"


def build_pack(items: dict, seed: int) -> list[dict]:
    pack = []
    for it in items["items"]:
        for m in JUDGED:
            c = it["methods"][m]["text"]
            pr = prompt_for(it["lang"], c)
            pack.append({"id": item_id(it["paragraph"], m), "seed": seed, "prompt": pr,
                         "compressed_text": c, "prompt_version": PROMPT_VERSION, "prompt_sha256": sha256(pr)})
    random.Random(f"{RUN}-seed{seed}").shuffle(pack)  # order differs per seed; content does not
    return pack


def build_all(sources: dict | None = None, **kw) -> dict[Path, str]:
    sources = sources or load_json(SOURCES)
    items = build_items(sources, **kw)
    out = {path("items"): dumps(items)}
    for s in SEEDS:
        out[path("pack", s)] = dumps(build_pack(items, s))
    return out


# --- segmentation / alignment ----------------------------------------------------------------

CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
_SENT = re.compile(r"(?<=[.!?;])\s+(?=[“\"‘(\[]?\w)|(?<=[.!?][”\"’])\s+(?=\S)|(?<=[。！？])")
_ABBR = re.compile(r"(?:^|[\s\"“(])(?:Mr|Mrs|Ms|Dr|St|U\.S|[A-Z])\.$")


def split_answer(answer: str, n_gold: int) -> tuple[list[str], bool]:
    """Restored sentences, and whether the one-sentence-per-line format was followed."""
    lines = [ln.strip() for ln in (answer or "").replace("\r\n", "\n").split("\n") if ln.strip()]
    if len(lines) > 1 or n_gold == 1:
        return lines, True
    out: list[str] = []
    for part in _SENT.split(lines[0] if lines else ""):
        part = part.strip()
        if not part:
            continue
        if out and _ABBR.search(out[-1]):
            out[-1] += " " + part
        else:
            out.append(part)
    return out, False


_MOSAIC_TAG = re.compile(r"^(?:[a-z]{2,3}(?:-[A-Za-z]+)?|&):")


def split_compressed(text: str, n_gold: int) -> list[str]:
    """Sentences of a compressed paragraph. SentenceCalibratedMosaic (B) output is a tile mosaic
    ``de:Satz eins.|Satz zwei.|en:...``: split on ``|`` and drop the ``lang:`` tile tags."""
    if _MOSAIC_TAG.match(text):
        tiles = [_MOSAIC_TAG.sub("", t).strip() for t in text.split("|")]
        return [t for t in tiles if t and re.search(r"\w", t)]
    return split_answer(text, n_gold)[0]


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if (a or b) else 1.0


def align(gold: list[str], got: list[str]) -> list[tuple[list[int], list[int]]]:
    """Order-preserving alignment. Moves: 1-1, 2-1 (merge), 1-2 (split), 1-0, 0-1."""
    G = [norm(x) for x in gold]; R = [norm(x) for x in got]
    n, m = len(G), len(R)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back: dict[tuple[int, int], tuple[int, int]] = {}
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c == INF:
                continue
            moves = [(1, 0, 1.0), (0, 1, 1.0)]
            if i < n and j < m:
                moves.append((1, 1, 1 - sim(G[i], R[j])))
            if i + 1 < n and j < m:
                moves.append((2, 1, 1 - sim(G[i] + " " + G[i + 1], R[j]) + 0.15))
            if i < n and j + 1 < m:
                moves.append((1, 2, 1 - sim(G[i], R[j] + " " + R[j + 1]) + 0.15))
            for di, dj, w in moves:
                a, b = i + di, j + dj
                if a <= n and b <= m and c + w < cost[a][b] - 1e-12:
                    cost[a][b] = c + w
                    back[(a, b)] = (di, dj)
    pairs = []
    i, j = n, m
    while (i, j) != (0, 0):
        di, dj = back[(i, j)]
        pairs.append((list(range(i - di, i)), list(range(j - dj, j))))
        i, j = i - di, j - dj
    return pairs[::-1]


# --- tokens and word classes -------------------------------------------------------------------

SYMBOL_PO = set("@&#%*/\\|~^")


def is_symbol(ch: str) -> bool:
    """Compression symbols (○ → & @ …), not ordinary sentence punctuation."""
    return unicodedata.category(ch).startswith("S") or ch in SYMBOL_PO


def tokens(s: str, keep_symbols: bool = False) -> list[str]:
    """Lower-cased word tokens (letters+digits together, so ``b4`` stays one token); CJK split
    per character; punctuation dropped; symbols kept only with ``keep_symbols``."""
    s = unicodedata.normalize("NFC", s).lower()
    out = []
    for t in re.findall(r"[^\W_]+(?:'[^\W_]+)*|[^\w\s]", s):
        if CJK.search(t):
            for part in re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]|[^\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]+", t):
                out.extend(part if CJK.match(part) else [part])
        elif t[0].isalnum():
            out.append(t)
        elif keep_symbols and is_symbol(t):
            out.append(t)
    return out


ARTICLES = {
    "en": "a an the this that these those",
    "de": "der die das den dem des ein eine einen einem einer eines dieser diese dieses diesen diesem",
    "es": "el la los las un una unos unas este esta estos estas ese esa esos esas",
    "fr": "le la les l un une des du ce cet cette ces",
    "pt": "o a os as um uma uns umas este esta estes estas esse essa esses essas",
    "it": "il lo la i gli le l un uno una questo questa questi queste quello quella",
    "nl": "de het een deze dit die dat",
    "el": "ο η το οι τα του της των τον την ένας μια ένα αυτός αυτή αυτό",
    "cs": "ten ta to ty ti tento tato toto",
    "pl": "ten ta to ci te tego tej",
    "la": "hic haec hoc is ea id ille illa illud",
    "ja": "この その あの", "zh": "这 那 这个 那个",
}
PRONOUNS = {
    "en": "i you he she it we they me him her us them my your his its our their one",
    "de": "ich du er sie es wir ihr mich dich ihn uns euch ihm ihnen man",
    "es": "yo tú él ella nosotros ellos ellas lo le les me te se nos",
    "fr": "je tu il elle on nous vous ils elles le lui leur me te se",
    "pt": "eu tu ele ela nós eles elas o lhe lhes me te se nos",
    "it": "io tu lui lei noi voi loro lo gli le mi ti si ci vi",
    "nl": "ik jij je hij zij ze het wij we jullie hen hem haar mij me ons",
    "el": "εγώ εσύ αυτός αυτή αυτό εμείς αυτοί τον την το τους με σε μας",
    "cs": "já ty on ona ono my vy oni ho mu jí je se",
    "pl": "ja ty on ona ono my wy oni one go mu jej ją się",
    "la": "ego tu nos vos se sibi eum eam eos eas ei iis",
    "ja": "私 彼 彼女 我々", "zh": "我 你 他 她 它 我们 他们",
}
AUX_EN = set("have has had 've 'd will would shall should was were is are am be been being do does did".split())
ARTICLES = {k: set(v.split()) for k, v in ARTICLES.items()}
PRONOUNS = {k: set(v.split()) for k, v in PRONOUNS.items()}
CONTRACTIONS = [(r"n't\b", " not"), (r"'ve\b", " have"), (r"'ll\b", " will"), (r"'re\b", " are"),
                (r"'m\b", " am"), (r"'d\b", " would")]


def loose(s: str, lang: str) -> str:
    """norm + English contractions expanded + articles/determiners removed (rule-based semantic)."""
    s = unicodedata.normalize("NFC", s).lower()
    if lang == "en":
        for pat, rep in CONTRACTIONS:
            s = re.sub(pat, rep, s)
    return " ".join(t for t in tokens(s) if t not in ARTICLES.get(lang, ()))


def same_stem(a: str, b: str) -> bool:
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    return a != b and k >= 3 and k >= 0.5 * min(len(a), len(b))


def classify(gold: str, got: str, lang: str) -> list[dict]:
    """Rule-based labels for one aligned pair (word tokens, punctuation ignored)."""
    g, r = tokens(gold), tokens(got)
    arts, prons = ARTICLES.get(lang, set()), PRONOUNS.get(lang, set())
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, g, r, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        a, b = g[i1:i2], r[j1:j2]
        both = a + b
        if both and all(t in arts for t in both):
            lab = "article_demonstrative"
        elif a and b and loose(" ".join(a), lang) == loose(" ".join(b), lang):
            lab = "contraction_or_variant"
        elif lang == "en" and any(t in AUX_EN for t in both) and len(a) <= 3 and len(b) <= 3:
            lab = "tense_swap"
        elif op == "insert" and all(t in prons for t in b):
            lab = "added_subject_object"
        elif op == "delete" and all(t in prons for t in a):
            lab = "dropped_subject_object"
        elif op == "replace" and len(a) == len(b) and all(same_stem(x, y) for x, y in zip(a, b)):
            lab = "tense_swap" if lang == "en" else "inflection_change"
        elif op == "replace" and len(a) <= 3 and len(b) <= 3:
            lab = "synonym_drift"
        elif op == "replace":
            lab = "rewrite"
        elif op == "insert":
            lab = "added_content"
        else:
            lab = "dropped_content"
        out.append({"label": lab, "gold": " ".join(a), "got": " ".join(b), "gold_span": [i1, i2]})
    return out


def leftovers(gold: str, got: str, compressed: str, lang: str) -> list[dict]:
    """Restored tokens absent from the gold paragraph that came straight from the compressed text."""
    gt, ct = set(tokens(gold, True)), set(tokens(compressed, True))
    out = []
    for t in dict.fromkeys(tokens(got, True)):
        if t in gt or t not in ct:
            continue
        if CJK.search(t) and lang not in ("ja", "zh"):
            out.append({"label": "leftover_kanji_symbol", "got": t})
        elif not t[0].isalnum():
            out.append({"label": "leftover_kanji_symbol", "got": t})
        else:
            out.append({"label": "leftover_foreign", "got": t})
    return out


def substitutions(gold: str, compressed: str) -> list[dict]:
    """Source span -> compressed span edits in one aligned sentence (word-token indices of gold)."""
    g, gw = tokens(gold), tokens(compressed, True)  # keep symbols on the compressed side ("&", "○", "→")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, g, gw, autojunk=False).get_opcodes():
        if op != "equal":
            out.append({"rule": f"{' '.join(g[i1:i2]) or '∅'} → {' '.join(gw[j1:j2]) or '∅'}",
                        "gold_span": [i1, max(i2, i1 + 1)]})
    return out


# --- scoring -----------------------------------------------------------------------------------

def score_answer(para: dict, compressed: str, answer: str | None) -> dict:
    gold, lang = para["sentences"], para["lang"]
    if answer is None:
        return {"status": "no_answer", "sentences": len(gold), "exact": 0, "semantic_rule": 0,
                "paragraph_exact": False, "format_followed": False, "labels": {}, "sentence_rows": []}
    got, fmt = split_answer(answer, len(gold))
    comp_sents = split_compressed(compressed, len(gold))
    comp_map: dict[int, str] = {}
    for gi, ci in align(gold, comp_sents):
        for k in gi:
            comp_map[k] = " ".join(comp_sents[x] for x in ci)
    rows, labels = [], Counter()
    for gi, ri in align(gold, got):
        g_txt = " ".join(gold[k] for k in gi); r_txt = " ".join(got[k] for k in ri)
        seg = None
        if not gi:
            seg = "added_sentence"
        elif not ri:
            seg = "dropped_sentence"
        elif len(gi) != len(ri):
            seg = "merge_split"
        exact = bool(gi and ri) and norm(g_txt) == norm(r_txt)
        sem = exact or (bool(gi and ri) and loose(g_txt, lang) == loose(r_txt, lang))
        errs = [] if exact or not gi or not ri else classify(g_txt, r_txt, lang)
        c_txt = " ".join(comp_map.get(k, "") for k in gi)
        lefts = [] if exact or not gi else leftovers(g_txt, r_txt, c_txt, lang)
        subs = substitutions(g_txt, c_txt) if gi else []
        attrib = []
        for s in subs:
            lo, hi = s["gold_span"]
            hit = [e["label"] for e in errs if e["label"] not in BENIGN and e["gold_span"][0] < hi and max(e["gold_span"][1], e["gold_span"][0] + 1) > lo]
            attrib.append({"rule": s["rule"], "restored_ok": not hit, "labels": hit})
        for lab in [e["label"] for e in errs] + [e["label"] for e in lefts] + ([seg] if seg else []):
            labels[lab] += 1
        rows.append({"gold": gi, "got": ri, "exact": exact, "semantic_rule": sem,
                     "segmentation": seg, "errors": errs, "leftovers": lefts, "rules": attrib,
                     "unattributed": [e["label"] for e in errs if e["label"] not in BENIGN and not any(
                         s["gold_span"][0] < max(e["gold_span"][1], e["gold_span"][0] + 1) and s["gold_span"][1] > e["gold_span"][0]
                         for s in subs)]})
    exact_n = sum(len(r["gold"]) for r in rows if r["exact"])
    sem_n = sum(len(r["gold"]) for r in rows if r["semantic_rule"])
    return {"status": "ok", "sentences": len(gold), "restored_sentences": len(got), "exact": exact_n,
            "semantic_rule": sem_n, "paragraph_exact": exact_n == len(gold) and len(got) == len(gold),
            "format_followed": fmt, "labels": dict(sorted(labels.items())), "sentence_rows": rows}


def load_blind(seed: int, d: Path | None = None) -> dict | None:
    p = path("blind", seed, d)
    return load_json(p) if p.is_file() else None


def score_all(items: dict, sources: dict, blinds: dict[int, dict]) -> dict:
    paras = {p["id"]: p for p in sources["paragraphs"]}
    per_item: dict[str, dict] = {}
    for it in items["items"]:
        p = paras[it["paragraph"]]
        for m in JUDGED:
            iid = item_id(p["id"], m)
            comp = it["methods"][m]["text"]
            per_item[iid] = {"paragraph": p["id"], "lang": p["lang"], "method": m,
                             "o200k_delta_pct": it["methods"][m]["o200k_delta_pct"],
                             "bytes_delta_pct": it["methods"][m]["bytes_delta_pct"],
                             "seeds": {str(s): score_answer(p, comp, b["answers"].get(iid)["answer"]
                                                            if b["answers"].get(iid) else None)
                                       for s, b in sorted(blinds.items())}}
    summary: dict[str, dict] = {}
    rules: dict[str, dict] = {}
    for iid, r in per_item.items():
        for scope in ("all", r["lang"]):
            row = summary.setdefault(r["method"], {}).setdefault(scope, Counter())
            for s, sc in r["seeds"].items():
                row["judgements"] += 1
                row["sentences"] += sc["sentences"]
                row["exact"] += sc["exact"]
                row["semantic_rule"] += sc["semantic_rule"]
                row["paragraph_exact"] += int(sc["paragraph_exact"])
                row["format_followed"] += int(sc["format_followed"])
                row["no_answer"] += int(sc["status"] != "ok")
                for k, v in sc["labels"].items():
                    row["label:" + k] += v
        for s, sc in r["seeds"].items():
            for row in sc["sentence_rows"]:
                for a in row["rules"]:
                    rr = rules.setdefault(a["rule"], {"rule": a["rule"], "methods": Counter(), "applied": 0,
                                                       "restored_ok": 0, "labels": Counter(), "examples": []})
                    rr["applied"] += 1
                    rr["methods"][r["method"]] += 1
                    rr["restored_ok"] += int(a["restored_ok"])
                    rr["labels"].update(a["labels"])
                    if not a["restored_ok"] and len(rr["examples"]) < 3 and iid not in rr["examples"]:
                        rr["examples"].append(iid)
    out_summary = {}
    for m, scopes in summary.items():
        out_summary[m] = {}
        for scope, c in sorted(scopes.items(), key=lambda kv: (kv[0] != "all", kv[0])):
            d = dict(sorted(c.items()))
            n = c["sentences"] or 1
            d["exact_rate"] = round(c["exact"] / n, 4)
            d["semantic_rule_rate"] = round(c["semantic_rule"] / n, 4)
            d["paragraph_exact_rate"] = round(c["paragraph_exact"] / (c["judgements"] or 1), 4)
            out_summary[m][scope] = d
    rule_rows = sorted(({**v, "methods": dict(sorted(v["methods"].items())), "labels": dict(sorted(v["labels"].items())),
                         "error_rate": round(1 - v["restored_ok"] / v["applied"], 4)} for v in rules.values()),
                       key=lambda v: (-(v["applied"] - v["restored_ok"]), -v["applied"], v["rule"]))
    return {"run": RUN, "prompt_version": PROMPT_VERSION, "seeds_scored": sorted(int(s) for s in blinds),
            "ai_readability": AI_READABILITY,
            "notes": "exact = norm()-equal content per gold sentence (a split/merge with equal content still counts, "
                     "and is labelled merge_split); semantic_rule = exact or equal after contractions expanded and "
                     "articles/determiners removed (rule-based, not an AI judgement); labels are rule-based.",
            "summary": out_summary, "rules": rule_rows, "items": per_item}


# --- judge answers -----------------------------------------------------------------------------

def validate_raw(raw: dict, pack: list[dict], seed: int) -> list[str]:
    errs = []
    if raw.get("run") != RUN or raw.get("seed") != seed:
        errs.append(f"run/seed must be {RUN}/{seed}")
    judge = raw.get("judge")
    if not isinstance(judge, dict) or not judge.get("type"):
        errs.append("judge.type missing")
    byid = {p["id"]: p for p in pack}
    seen = set()
    for a in raw.get("answers", []):
        iid = a.get("id")
        if iid not in byid:
            errs.append(f"unknown id {iid!r}")
            continue
        if iid in seen:
            errs.append(f"duplicate id {iid!r}")
        seen.add(iid)
        if a.get("prompt_sha256") != byid[iid]["prompt_sha256"]:
            errs.append(f"{iid}: prompt_sha256 does not match the pack")
        st = a.get("status", "ok")
        if st not in ("ok", "timeout", "error"):
            errs.append(f"{iid}: bad status {st!r}")
        if st == "ok" and not isinstance(a.get("answer"), str):
            errs.append(f"{iid}: answer must be a string")
    missing = set(byid) - seen
    if missing:
        errs.append(f"{len(missing)} pack items have no answer record (first: {sorted(missing)[0]})")
    return errs


def ingest(seed: int, d: Path | None = None) -> dict:
    pack = load_json(path("pack", seed, d))
    raw = load_json(path("raw", seed, d))
    errs = validate_raw(raw, pack, seed)
    if errs:
        raise SystemExit("raw answers invalid:\n  " + "\n  ".join(errs[:20]))
    ans = {}
    for a in sorted(raw["answers"], key=lambda a: a["id"]):
        ans[a["id"]] = ({"answer": a["answer"], "prompt_sha256": a["prompt_sha256"]}
                        if a.get("status", "ok") == "ok" else None)
    return {"run": RUN, "seed": seed, "prompt_version": PROMPT_VERSION, "judge": raw["judge"],
            "raw_sha256": sha256(path("raw", seed, d).read_text(encoding="utf-8")),
            "answers": {k: v for k, v in ans.items() if v is not None},
            "no_answer": sorted(k for k, v in ans.items() if v is None)}


def run_cmd(seed: int, cmd: str, workers: int = 4, judge_type: str = "local command") -> dict:
    """Optional: ask a local command (prompt on stdin, PARA_SEED in env) instead of helper bots."""
    pack = load_json(path("pack", seed))
    env = dict(os.environ, PARA_SEED=str(seed))

    def one(p):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            r = subprocess.run(cmd, shell=True, input=p["prompt"], capture_output=True, text=True, env=env, timeout=600)
            ok = r.returncode == 0
            return {"id": p["id"], "prompt_sha256": p["prompt_sha256"], "status": "ok" if ok else "error",
                    "answer": r.stdout.strip() if ok else None, "started_at": started}
        except subprocess.TimeoutExpired:
            return {"id": p["id"], "prompt_sha256": p["prompt_sha256"], "status": "timeout", "answer": None,
                    "started_at": started}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        answers = list(ex.map(one, pack))
    return {"run": RUN, "seed": seed, "judge": {"type": judge_type, "cmd_sha256": sha256(cmd)}, "answers": answers}


def current_results(d: Path | None = None) -> dict:
    blinds = {s: b for s in SEEDS if (b := load_blind(s, d)) is not None}
    return score_all(load_json(path("items", None, d)), load_json(SOURCES), blinds)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="paragraph round-trip benchmark")
    sub = ap.add_subparsers(dest="action", required=True)
    b = sub.add_parser("build"); b.add_argument("--check", action="store_true")
    i = sub.add_parser("ingest"); i.add_argument("--seed", type=int, required=True, choices=SEEDS)
    s = sub.add_parser("score"); s.add_argument("--check", action="store_true")
    r = sub.add_parser("run"); r.add_argument("--seed", type=int, required=True, choices=SEEDS)
    r.add_argument("--cmd", required=True); r.add_argument("--workers", type=int, default=4)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.action == "build":
        files = build_all()
        stale = [p for p, t in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != t]
        if a.check:
            print("items/packs up to date" if not stale else "stale: " + ", ".join(p.name for p in stale))
            return 1 if stale else 0
        for p, t in files.items():
            p.write_text(t, encoding="utf-8")
        print("wrote " + ", ".join(p.name for p in files))
        return 0
    if a.action == "ingest":
        path("blind", a.seed).write_text(dumps(ingest(a.seed)), encoding="utf-8")
        print(f"wrote {path('blind', a.seed).name}")
        return 0
    if a.action == "score":
        text = dumps(current_results())
        if a.check:
            ok = path("results").is_file() and path("results").read_text(encoding="utf-8") == text
            print("results up to date" if ok else "results stale")
            return 0 if ok else 1
        path("results").write_text(text, encoding="utf-8")
        res = json.loads(text)
        for m, sc in res["summary"].items():
            al = sc.get("all", {})
            print(f"{m}: exact {al.get('exact', 0)}/{al.get('sentences', 0)} semantic_rule {al.get('semantic_rule', 0)} "
                  f"paragraph_exact {al.get('paragraph_exact', 0)}/{al.get('judgements', 0)}")
        return 0
    if a.action == "run":
        path("raw", a.seed).write_text(dumps(run_cmd(a.seed, a.cmd, a.workers)), encoding="utf-8")
        print(f"wrote {path('raw', a.seed).name}; next: ingest --seed {a.seed}")
        return 0
    for s_ in SEEDS:
        print(f"seed {s_}: pack={path('pack', s_).is_file()} raw={path('raw', s_).is_file()} blind={path('blind', s_).is_file()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
