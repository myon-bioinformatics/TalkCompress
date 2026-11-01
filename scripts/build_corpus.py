"""TalkCompress テスト用の多言語コーパスを取得・生成し manifest を書く。

使い方:
    uv run --with ftfy python scripts/build_corpus.py

取得物は .cache/corpus_raw/（コミットしない）。seed 固定で再現的に生成する。
AI による原文復元は未測定（mojibake の ftfy 列は機械復元の実測のみ）。
"""
from __future__ import annotations

import bz2, hashlib, json, pathlib, random, re, urllib.request

import ftfy
import tiktoken

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "corpus_raw"
OUT = ROOT / "tests" / "fixtures" / "corpus"
SEED = 20261101
N = 400
enc = tiktoken.get_encoding("o200k_base")

CV_BASE = "https://raw.githubusercontent.com/common-voice/common-voice/main/server/data"
SRC = {
    "cv": {"name": "Common Voice sentence-collector", "url": "https://github.com/common-voice/common-voice/tree/main/server/data", "license": "CC0-1.0", "attribution": None},
    "tatoeba": {"name": "Tatoeba jpn_sentences", "url": "https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2", "license": "CC-BY-2.0-FR",
                "attribution": "Sentences from Tatoeba (https://tatoeba.org), licensed under CC BY 2.0 FR. 各行の id が Tatoeba の文 ID（https://tatoeba.org/sentences/show/<id>）で、寄稿者に帰属。"},
    "emoji": {"name": "Unicode emoji-test.txt", "url": "https://www.unicode.org/Public/emoji/latest/emoji-test.txt", "license": "Unicode-3.0", "attribution": "Copyright (c) Unicode, Inc. Unicode License v3"},
    "own": {"name": "GitHubヘルプ5bot 作成のテンプレート（scripts/build_corpus.py）", "url": None, "license": "CC0-1.0", "attribution": None},
}


def fetch(url: str, name: str) -> pathlib.Path:
    p = RAW / name
    if not p.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as r:
            p.write_bytes(r.read())
    return p


def m(s: str) -> dict:
    return {"o200k": len(enc.encode(s)), "bytes": len(s.encode("utf-8"))}


def lines(p: pathlib.Path) -> list[str]:
    return sorted({l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()})


def write(cat: str, lang: str, rows: list[dict], sources: list[str]) -> dict:
    d = OUT / cat
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{lang}.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return {"path": f"{cat}/{lang}.jsonl", "category": cat, "lang": lang, "count": len(rows),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "o200k_total": sum(r["o200k"] for r in rows), "bytes_total": sum(r["bytes"] for r in rows),
            "sources": [SRC[s] for s in sources], "ai_roundtrip": "未測定"}


def garble(t: str) -> dict[str, str]:
    u = t.encode("utf-8")
    r = {"utf8_as_latin1": u.decode("latin-1"), "utf8_as_cp1252": u.decode("cp1252", "replace")}
    r["double_latin1"] = r["utf8_as_latin1"].encode("utf-8").decode("latin-1")
    try:
        sj = t.encode("cp932")
        r |= {"sjis_as_utf8": sj.decode("utf-8", "replace"), "sjis_as_latin1": sj.decode("latin-1"),
              "utf8_as_sjis": u.decode("cp932", "replace"),
              "eucjp_as_utf8": t.encode("euc_jp").decode("utf-8", "replace"),
              "utf8_as_eucjp": u.decode("euc_jp", "replace")}
    except UnicodeEncodeError:
        pass
    return r


TEMPLATES = {
    "ja": ["会議は {e} {h}:{mi}〜、場所は B-{n} 会議室です", "これマジで最高 {e}{e2} また行こ！", "x² + y² = r²、つまり ∑ᵢ aᵢ ≤ √{n}·max|aᵢ| だよ {e}",
           "エラー出た {e} `TypeError: 'NoneType' object is not subscriptable` って何？", "`uv run pytest -k \"not slow\"` → {n}{n} passed ✅ {e}",
           "価格は ¥{n},980（税込）/ €{n}.50 ±{n}% {e}", "∀ε>0 ∃δ>0: |x−a|<δ ⇒ |f(x)−f(a)|<ε って覚えた {e}", "体温 36.{n}℃、血圧 1{n}0/80 mmHg ♡ {e}",
           "じゃあ {n}/14 (π day) に ⇨ 渋谷で {e}", "`grep -rn 'TODO' src/ | wc -l` で {n}{n} 件 {e}", "ΔG = ΔH − TΔS ってテストに出るらしい {e}{e2}",
           "{s} {e}", "{s}（{h}:{mi} 追記）{e2}", "【メモ】{s} → `print(len(x))` = {n}"],
    "en": ["Meeting at {h}:{mi} in room B-{n} {e}", "omg this is the best {e}{e2} lets go again!", "x² + y² = r², so ∑ᵢ aᵢ ≤ √{n}·max|aᵢ| {e}",
           "got an error {e} `TypeError: 'NoneType' object is not subscriptable` wtf?", "Run `uv run pytest -k \"not slow\"` → {n}{n} passed ✅ {e}",
           "Price: $1{n}.99 / €{n}.50 ±{n}% {e}", "if (a >= b && c != null) {{ return a ?? b; }} // {e}", "∀ε>0 ∃δ>0: |x−a|<δ ⇒ |f(x)−f(a)|<ε {e}",
           "$ grep -rn 'TODO' src/ | wc -l  # => {n}{n} {e}", "E = mc²; ∫₀^∞ e^{{−x²}} dx = √π/2 {e}{e2}", "{s} {e}", "{s} ({h}:{mi} edit) {e2}", "NOTE: {s} -> `len(x) == {n}`"],
}


def main() -> None:
    rng = random.Random(SEED)
    entries = []
    pools = {}
    for lang in ["ja", "en", "vi", "th"]:
        pools[lang] = lines(fetch(f"{CV_BASE}/{lang}/sentence-collector.txt", f"cv_{lang}.txt"))
        rows = [{"text": s, **m(s)} for s in rng.sample(pools[lang], N)]
        entries.append(write("colloquial", lang, rows, ["cv"]))
    tat = bz2.decompress(fetch(SRC["tatoeba"]["url"], "jpn_sentences.tsv.bz2").read_bytes()).decode("utf-8")
    coll = re.compile(r"(よ|ね|な|ぜ|わ|さ|じゃん|っけ|ってば|かな|でしょ|だろ)[。！？!?]?$")
    tl = sorted((int(i), s) for i, _, s in (l.split("\t") for l in tat.split("\n") if l.count("\t") == 2) if coll.search(s))
    rows = [{"id": i, "text": s, **m(s)} for i, s in rng.sample(tl, N)]
    entries.append(write("colloquial-tatoeba", "ja", rows, ["tatoeba"]))
    for lang in ["ja", "vi"]:
        rows = []
        for t in rng.sample(pools[lang], N):
            kinds = garble(t)
            k = rng.choice(sorted(kinds))
            g = kinds[k]
            fx = ftfy.fix_text(g)
            rows.append({"orig": t, "kind": k, "text": g, **m(g), "orig_o200k": len(enc.encode(t)),
                         "ftfy_exact": fx == t, "ftfy_o200k": len(enc.encode(fx))})
        entries.append(write("mojibake", lang, rows, ["cv"]))
    em = [l.split("#")[1].strip().split(" ")[0] for l in fetch(SRC["emoji"]["url"], "emoji-test.txt").read_text(encoding="utf-8").splitlines()
          if "; fully-qualified" in l]
    for lang, tm in TEMPLATES.items():
        rows, seen = [], set()
        while len(rows) < N:
            s = rng.choice(tm).format(e=rng.choice(em), e2=rng.choice(em), n=rng.randint(1, 9), h=rng.randint(9, 23),
                                      mi=f"{rng.randrange(0, 60, 5):02d}", s=rng.choice(pools[lang]))
            if s not in seen:
                seen.add(s)
                rows.append({"text": s, **m(s)})
        entries.append(write("mixed", lang, rows, ["own", "emoji", "cv"]))
    man = {"generator": "scripts/build_corpus.py", "seed": SEED, "tokenizer": "o200k_base",
           "note": "AI が元の文に戻せるかは未測定。mojibake の ftfy_* は ftfy による機械復元の実測。", "files": entries}
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for e in entries:
        print(e["path"], e["count"], e["o200k_total"], e["bytes_total"])


if __name__ == "__main__":
    main()
