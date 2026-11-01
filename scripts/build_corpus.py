"""TalkCompress テスト用の多言語コーパス（口語・文字化け・混在文）を取得・生成する。

使い方:
    uv run --with ftfy python scripts/build_corpus.py

- 取得物は .cache/corpus_raw/（git 管理外）。seed 固定で再現的に生成する。
- 形式は docs/corpus.md（#134）に従う。1 ファイル = 1 manifest エントリ = 1 source。
- manifest の数値（count/bytes/o200k_tokens/sha256）は最後に scripts/corpus_manifest.py の
  update で計算する。retrieved_at は取得物ファイルの更新日（JST）。
- AI が元の文に戻せるかは未測定。mojibake の ftfy_* は ftfy による機械復元の実測。
"""
from __future__ import annotations

import bz2
import datetime as dt
import hashlib
import json
import pathlib
import random
import re
import sys
import urllib.request

import ftfy
import tiktoken

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import corpus_manifest as cm  # noqa: E402

RAW = ROOT / ".cache" / "corpus_raw"
OUT = cm.CORPUS_DIR
SEED = 20261101
N = 400
N_TATOEBA = 300
JST = dt.timezone(dt.timedelta(hours=9))
enc = tiktoken.get_encoding("o200k_base")

CV_BASE = "https://raw.githubusercontent.com/common-voice/common-voice/main/server/data"
CV_BLOB = "https://github.com/common-voice/common-voice/blob/main/server/data"
TATOEBA_DETAILED = "https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences_detailed.tsv.bz2"
SELF_URL = "https://github.com/myon-bioinformatics/TalkCompress/blob/main/scripts/build_corpus.py"
CC0 = ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/")
CCBY = ("CC BY 2.0 FR", "https://creativecommons.org/licenses/by/2.0/fr/")
UNMEASURED_NOTE = "AI が元の文に戻せるかは未測定"


def fetch(url: str, name: str) -> pathlib.Path:
    p = RAW / name
    if not p.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as r:
            p.write_bytes(r.read())
    return p


def day(p: pathlib.Path) -> str:
    return dt.datetime.fromtimestamp(p.stat().st_mtime, JST).date().isoformat()


def m(s: str) -> dict:
    return {"o200k": len(enc.encode(s)), "bytes": len(s.encode("utf-8"))}


def lines(p: pathlib.Path) -> list[str]:
    return sorted({l.strip() for l in p.read_text(encoding="utf-8").split("\n") if l.strip()})


def dumps(r: dict) -> str:
    # validate_records は str.splitlines() で行を分けるので、行区切り扱いの文字は必ずエスケープする
    s = json.dumps(r, ensure_ascii=False)
    for ch in "\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029":
        s = s.replace(ch, f"\\u{ord(ch):04x}")
    return s


def cv_row(lang: str, t: str) -> dict:
    return {"id": f"cv-{lang}-{hashlib.sha1(t.encode()).hexdigest()[:12]}", "text": t, "lang": lang, "tier": "short",
            "source": "common-voice", "license": CC0[0], "author": "Common Voice contributors",
            "url": f"{CV_BLOB}/{lang}/sentence-collector.txt", "register": "read"}


# 絵文字はデータファイルを使わず、コードポイントの範囲から自作で組み立てる（CC0、Unicode 由来のデータファイルは不使用）
_BASE = [chr(c) for c in list(range(0x1F600, 0x1F64F)) + list(range(0x1F680, 0x1F6C5))]
_HANDS = [chr(c) for c in range(0x1F44A, 0x1F451)]
_SKIN = [chr(c) for c in range(0x1F3FB, 0x1F400)]
_ZWJ = ["\U0001F469\u200D\U0001F4BB", "\U0001F468\u200D\U0001F373", "\U0001F469\u200D\U0001F680",
        "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466", "\U0001F3F3\uFE0F\u200D\U0001F308"]


def emoji(rng: random.Random) -> str:
    k = rng.randrange(3)
    if k == 0:
        return rng.choice(_BASE)
    if k == 1:
        return rng.choice(_HANDS) + rng.choice(_SKIN)
    return rng.choice(_ZWJ)


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


def write(cat: str, lang: str, rows: list[dict]) -> None:
    d = OUT / cat
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{lang}.jsonl").write_text("".join(dumps(r) + "\n" for r in rows), encoding="utf-8")


def entry(cat, lang, source, url, lic, retrieved, attribution) -> dict:
    return {"id": f"{cat}-{lang}-{source}", "category": cat, "lang": lang, "source": source, "url": url,
            "license": lic[0], "license_url": lic[1], "path": f"{cat}/{lang}.jsonl", "count": 0, "bytes": 0,
            "o200k_tokens": 0, "sha256": "0" * 64, "retrieved_at": retrieved, "ai_roundtrip": cm.UNMEASURED,
            "attribution": attribution, "generator": "scripts/build_corpus.py", "seed": SEED}


def main() -> None:
    rng = random.Random(SEED)
    entries, pools, cv_day = [], {}, {}
    for lang in ["ja", "en", "vi", "th"]:
        p = fetch(f"{CV_BASE}/{lang}/sentence-collector.txt", f"cv_{lang}.txt")
        pools[lang], cv_day[lang] = lines(p), day(p)
        write("colloquial", lang, [{**cv_row(lang, s), **m(s)} for s in rng.sample(pools[lang], N)])
        entries.append(entry("colloquial", lang, "common-voice", f"{CV_BLOB}/{lang}/sentence-collector.txt", CC0, cv_day[lang],
                             "Common Voice sentence-collector（CC0、表示不要）。読み上げ用の文で自発発話ではない（register=read）"))

    # Tatoeba の口語文は #134 の 1 ファイル 1 source に合わせ、既存の sentence/ja.jsonl（source=tatoeba）に追記する
    tp = fetch(TATOEBA_DETAILED, "jpn_sentences_detailed.tsv.bz2")
    coll = re.compile(r"(よ|ね|な|ぜ|わ|さ|じゃん|っけ|ってば|かな|でしょ|だろ)[。！？!?]?$")
    tl = []
    for l in bz2.decompress(tp.read_bytes()).decode("utf-8").split("\n"):
        f = l.split("\t")
        if len(f) >= 4 and f[3] not in ("", "\\N") and coll.search(f[2]):
            tl.append((int(f[0]), f[2], f[3]))
    tl.sort()
    sj = OUT / "sentence" / "ja.jsonl"
    keep = [json.loads(x) for x in sj.read_text(encoding="utf-8").splitlines() if x.strip()]
    keep = [r for r in keep if "register" not in r]  # #134 の手選び分は残す
    have = {r["text"] for r in keep} | {r["id"] for r in keep}
    add = [{"id": f"tatoeba:{i}", "text": s, "lang": "ja", "source": "tatoeba", "license": CCBY[0], "author": a,
            "url": f"https://tatoeba.org/sentences/show/{i}", "tier": "short", "register": "colloquial", **m(s)}
           for i, s, a in rng.sample(tl, N_TATOEBA + 20) if s not in have and f"tatoeba:{i}" not in have][:N_TATOEBA]
    sj.write_text("".join(dumps(r) + "\n" for r in keep + add), encoding="utf-8")

    for lang in ["ja", "vi"]:
        rows = []
        for t in rng.sample(pools[lang], N):
            kinds = garble(t)
            k = rng.choice(sorted(kinds))
            g = kinds[k]
            fx = ftfy.fix_text(g)
            base = cv_row(lang, t)
            rows.append({**base, "id": f"moji-{lang}-{len(rows):04d}", "text": g, "register": None, "orig": t, "orig_id": base["id"],
                         "kind": k, **m(g), "orig_o200k": len(enc.encode(t)), "ftfy_exact": fx == t, "ftfy_o200k": len(enc.encode(fx))})
        write("mojibake", lang, rows)
        entries.append(entry("mojibake", lang, "common-voice", f"{CV_BLOB}/{lang}/sentence-collector.txt", CC0, cv_day[lang],
                             "Common Voice の文（CC0）を latin-1/cp1252/SJIS/EUC-JP で誤読させて生成。orig が原文。" + UNMEASURED_NOTE))

    for lang, tm in TEMPLATES.items():
        rows, seen = [], set()
        while len(rows) < N:
            base = rng.choice(pools[lang])
            t = rng.choice(tm)
            s = t.format(e=emoji(rng), e2=emoji(rng), n=rng.randint(1, 9), h=rng.randint(9, 23),
                         mi=f"{rng.randrange(0, 60, 5):02d}", s=base)
            if s in seen:
                continue
            seen.add(s)
            r = {"id": f"mixed-{lang}-{len(rows):04d}", "text": s, "lang": lang, "tier": "short", "source": "talkcompress-own",
                 "license": CC0[0], "author": "GitHubヘルプ5bot", "url": SELF_URL, "register": None, "embedded_id": None}
            if "{s}" in t:
                r |= {"embedded_id": cv_row(lang, base)["id"], "embedded_url": cv_row(lang, base)["url"]}
            rows.append({**r, **m(s)})
        write("mixed", lang, rows)
        entries.append(entry("mixed", lang, "talkcompress-own", SELF_URL, CC0, cv_day[lang],
                             "自作テンプレート（CC0）。絵文字はコードポイント範囲から自作で組み立て。一部に Common Voice の文（CC0、embedded_id）を埋め込む"))

    mp = cm.MANIFEST
    man = json.loads(mp.read_text(encoding="utf-8"))
    mine = {e["path"] for e in entries}
    man["entries"] = [e for e in man["entries"] if e.get("path") not in mine] + entries
    for e in man["entries"]:
        if e.get("path") == "sentence/ja.jsonl":
            e["retrieved_at"] = max(e["retrieved_at"], day(tp))
            e["attribution"] = ("各行の author / url を参照（Tatoeba 投稿者）。tier は行ごと。register=colloquial の行は "
                                "scripts/build_corpus.py が jpn_sentences_detailed から口語文末で抽出")
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cm.update(mp)
    for e in man["entries"]:
        pass
    print("\n".join(f"{e['path']} {e['count']} {e['o200k_tokens']} {e['bytes']}" for e in json.loads(mp.read_text(encoding='utf-8'))["entries"]))


if __name__ == "__main__":
    main()
