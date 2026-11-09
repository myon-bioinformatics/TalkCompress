"""弱支援スクリプトの o200k 実測表を生成する（計測専用。バンクには実装しない）。

出典: Tatoeba (https://tatoeba.org) CC BY 2.0 FR。各行に作者と文 URL を記録。
再現: uv run --no-project --with tiktoken==0.14.0 python docs/o200k-lookup/weak-scripts/probe.py
"""
import json, pathlib, sys, unicodedata
import tiktoken

D = pathlib.Path(__file__).resolve().parent
R = D.parents[2]
sys.path.insert(0, str(R / "SentenceCalibratedMosaic"))
from sentence_calibrated_mosaic import estimate_tokens  # noqa: E402

enc = tiktoken.get_encoding("o200k_base")
O = lambda s: len(enc.encode(s))
SCRIPT = {"ara": "Arab", "urd": "Arab", "hin": "Deva", "ben": "Beng", "tha": "Thai", "kor": "Hang",
          "hye": "Armn", "kat": "Geor", "amh": "Ethi", "bod": "Tibt", "rus": "Cyrl", "ind": "Latn",
          "tur": "Latn", "vie": "Latn"}
ISO1 = {"ara": "ar", "urd": "ur", "hin": "hi", "ben": "bn", "tha": "th", "kor": "ko", "hye": "hy",
        "kat": "ka", "amh": "am", "bod": "bo", "rus": "ru", "ind": "id", "tur": "tr", "vie": "vi"}
GE = set(json.loads((R / "SentenceCalibratedMosaic/fixtures/roundtrip.json").read_text())["ge100m_langs"])
# 実装エージェント（GitHubヘルプ5bot）が英訳を見ずに復元し、後で Tatoeba 英訳と意味照合した判定
HIT = json.loads((D / "roundtrip-judge-5bot.json").read_text())

# 既存登録形（全 fixtures の "to" 値）との衝突確認
reg = set()
def walk(x):
    if isinstance(x, dict):
        if isinstance(x.get("to"), str): reg.add(x["to"])
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
for p in (R / "SentenceCalibratedMosaic/fixtures").glob("*.json"): walk(json.loads(p.read_text()))

raw = json.loads((D / "tatoeba-raw.json").read_text())
blind = json.loads((D / "roundtrip-blind-5bot.json").read_text())
rows = []
for l, rs in raw.items():
    code = ISO1[l]; thr = 0.6 if code in GE else 0.9
    hits = sum(HIT[f"{l}{i}"] for i in range(len(rs)))
    for i, r in enumerate(rs):
        s, en = r["text"], r["en"]["text"]
        o, oe = O(s), O(en)
        rows.append({"lang": code, "tatoeba_lang": l, "script": SCRIPT[l], "id": r["id"],
                     "url": f"https://tatoeba.org/sentences/show/{r['id']}", "owner": r["owner"],
                     "license": r["license"], "s": s, "en_id": r["en"]["id"], "en_owner": r["en"]["owner"],
                     "en_direct": r["en"]["is_direct"], "en": en,
                     "o": o, "e": estimate_tokens(s), "b": len(s.encode()), "ch": len(s),
                     "o_en": oe, "b_en": len(en.encode()), "o_ratio": round(o / oe, 3),
                     "o_per_ch": round(o / len(s), 3), "restored": blind[f"{l}{i}"],
                     "rt_hit": HIT[f"{l}{i}"], "collision": s in reg})
summ = []
for l in raw:
    rr = [x for x in rows if x["tatoeba_lang"] == l]
    code = ISO1[l]; thr = 0.6 if code in GE else 0.9
    o = sum(x["o"] for x in rr); oe = sum(x["o_en"] for x in rr)
    rate = sum(x["rt_hit"] for x in rr) / len(rr)
    cheap = o < oe
    summ.append({"lang": code, "script": SCRIPT[l], "n": len(rr), "o": o, "o_en": oe,
                 "e": sum(x["e"] for x in rr), "b": sum(x["b"] for x in rr), "b_en": sum(x["b_en"] for x in rr),
                 "o_ratio": round(o / oe, 3), "abnormally_cheap": cheap,
                 "collision": any(x["collision"] for x in rr), "tier": "ge100m" if code in GE else "lt100m",
                 "rt": f"{sum(x['rt_hit'] for x in rr)}/{len(rr)}", "rt_rate": round(rate, 3), "threshold": thr,
                 "status": "adopted_in_table" if cheap and rate >= thr and not any(x["collision"] for x in rr)
                 else "examples_not_registered"})
meta = {"_meta": {"source": "Tatoeba api.tatoeba.org/unstable/sentences (CC BY 2.0 FR)", "tiktoken": "0.14.0",
        "enc": "o200k_base", "main": "84e5dca", "keys": {"o": "o200k tokens", "e": "estimate_tokens", "b": "utf8 bytes",
        "o_en": "o200k of Tatoeba English translation", "o_ratio": "o/o_en", "rt_hit": "往復復元が意味一致",
        "collision": "既存 fixtures の to 値と一致"},
        "roundtrip_method": "実装エージェント（GitHubヘルプ5bot）1者が原文のみから英語を復元し、その後 Tatoeba 英訳と意味照合。独立 AI 評価ではない",
        "adopted_in_table": "表上の判定のみ。バンク・estimate_tokens には実装しない", "summary": summ}}
with open(D / "weak-scripts.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    for x in rows: f.write(json.dumps(x, ensure_ascii=False) + "\n")
for x in summ: print(json.dumps(x, ensure_ascii=False))
