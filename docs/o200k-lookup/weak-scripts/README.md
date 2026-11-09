# 弱支援スクリプトの o200k 実測表（計測専用）

- 目的: o200k が弱支援スクリプトを異常に安く数えるか、圧縮の素材として大量投入しやすいかを実文で確認する。
- 出典: [Tatoeba](https://tatoeba.org) の実文と英訳のみ（CC BY 2.0 FR）。各行に作者と `https://tatoeba.org/sentences/show/<id>` を記録。文の自作・言い換えはしていない。
- 計測: tiktoken 0.14.0 / `o200k_base`、`estimate_tokens` は main `84e5dca`。スコアは o200k トークン優先、次にバイト。
- 再現: `uv run --no-project --with tiktoken==0.14.0 python docs/o200k-lookup/weak-scripts/probe.py`
- 対象: ar / ur（Arab）、hi（Deva）、bn（Beng）、th、ko、hy、ka、am（Ethi）、bo（Tibt）、ge100m 勝者 0 件の ru / id / tr / vi。各 3 文。

## 結果（3 文合計、o200k、原文 / Tatoeba 英訳）

| lang | script | o | o_en | 比 | bytes / en | 往復 |
|---|---|---|---|---|---|---|
| ar | Arab | 38 | 36 | 1.06 | 190 / 157 | 3/3 |
| bn | Beng | 23 | 22 | 1.05 | 176 / 82 | 3/3 |
| ur | Arab | 37 | 32 | 1.16 | 204 / 141 | 3/3 |
| ru | Cyrl | 23 | 20 | 1.15 | 169 / 75 | 3/3 |
| tr | Latn | 24 | 19 | 1.26 | 92 / 86 | 3/3 |
| th | Thai | 18 | 14 | 1.29 | 132 / 47 | 3/3 |
| id | Latn | 27 | 20 | 1.35 | 97 / 76 | 3/3 |
| ka | Geor | 23 | 16 | 1.44 | 139 / 62 | 3/3 |
| hi | Deva | 25 | 17 | 1.47 | 150 / 62 | 3/3 |
| vi | Latn | 32 | 21 | 1.52 | 143 / 95 | 3/3 |
| ko | Hang | 42 | 25 | 1.68 | 171 / 125 | 3/3 |
| hy | Armn | 37 | 18 | 2.06 | 183 / 78 | 3/3 |
| am | Ethi | 86 | 17 | 5.06 | 132 / 70 | 3/3 |
| bo | Tibt | 120 | 17 | 7.06 | 243 / 60 | 3/3 |

- 結論: 異常に安いスクリプトは見当たらず。全言語で o200k が英訳以上（最安でも bn 1.05 / ar 1.06）。エチオピア記・チベット記は 5〜7 倍で、文字単位でほぼバイト分解される。大量投入しても圧縮にならないため、全件 `examples_not_registered` 扱い（バンクには何も実装しない）。
- 衝突: 既存 fixtures の `to` 値との一致なし。
- AI 可読性 / 往復: 実装エージェント（GitHubヘルプ5bot）1 者が原文のみから英語を復元し（`roundtrip-blind-5bot.json`）、その後 Tatoeba 英訳と意味照合（`roundtrip-judge-5bot.json`）。全 14 言語 3/3（1.0）で lt100m ≥ 0.9 / ge100m ≥ 0.6 を満たすが、安くないため採用なし。独立 AI・複数モデルでの評価は未測定。
- estimate_tokens の参考: ru は e=29 / o=23 で過大、bo は e=107 / o=120 で過小。th / vi の script-cost 修正は既存の方針メモとして記録のみで、本 PR では estimator を変更しない。
- 注意: hi の英訳は Tatoeba の間接訳（`en_direct: false`）。am の 1 文はラテン転写を含む実文。
