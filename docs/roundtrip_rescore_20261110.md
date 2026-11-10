# 往復ゲート再採点（accepted sources + 先頭 que≡that, 2026-11-10 JST）

新しい判定は行っていない。各言語の不変ジャッジ `roundtrip_judge/<lang>_blind.json` に記録済みの回答を、
公式の `roundtrip.run()` 決定的リプレイ（言語ごとに記録済みの command sha256 と同一コマンド）で採点し直し、
各レコードに新しい cohort を追記した（旧 cohort は履歴に残る）。手でスコアを書き換えた箇所はない。

## ルール

* ゲートは引き続き完全一致（`norm-nfc-v1`）。`source_acceptance: any-official-source-v1`。
* **accepted sources**：測定した first source に加え、スナップショットのいずれかで、採用済みの (lang, to) が
  まさにこの形になっている bank エントリの英語 `from` をすべて含める。勝たなかった候補は公式ではない。
  スナップショットは 84e5dca（it/nl/zh）、cdb8953（es/fr/de/pt）、b722a8c（cs/pl）、a2f5dd1（el）、
  1602fce（la）、2e5312a（main）。対象 bank は tense_matrix / es_fr_tense / pt_el_latin_tense /
  pt_el_latin_phrases / zh_de_phrases。結果は `roundtrip_judge/accepted_sources_v1.json` に固定した
  （470 形。pt は #171 の `pt_sources.json` をそのまま使う）。
* **`leading-que-that-v1`**（myon の承認：「que と that は同一視して再採点していいよ」）：テンプレート内の
  句が `que ` で**始まる**場合に限り、その `que` を `that` に置き換えた文も一致とみなす。各ターゲットには
  `equivalent_sources` と `matched_via_marker_equivalence` を、cohort には `config.marker_equivalence` を
  記録し、バリデータで再計算する。文中や末尾の que、`Queen` のような語、その他の差異は一致にならない。
* 再生成：`uv run python scripts/rescore_accepted_sources.py --run`。スナップショットの再作成は `--freeze`。
  ターゲット ID（first source、converted、seed）と first-source の結果が再現されることを assert している。

## 形ごとの結果

| lang | 形 | 旧 | 新 | 一致した公式ソース | 扱い |
|---|---|---|---|---|---|
| de | fand | 0/9 | 9/9 | I found（find-past-1s） | 復元 |
| fr | pris | 0/9 | 9/9 | I took（take-past-1s） | 復元 |
| fr | ont su | 0/9 | 9/9 | they have known（mx-know-perf-3p） | 復元（過剰反転の疑い → 確認済み） |
| es | fue | 0/9 | 9/9 | he went（go-past-3s の from[1]） | 復元 |
| zh | 高速 | 0/9 | 9/9 | high-speed | 復元 |
| zh | 短期 | 0/9 | 9/9 | short-term | 復元 |
| zh | 小学 | 0/9 | 9/9 | elementary school | 復元 |
| zh | 高铁 | 0/9 | 9/9 | high-speed rail | 復元 |
| zh | 微调 | 0/9 | 9/9 | fine-tuning | 復元 |
| es | que dan | 0/9 | 9/9 | que give → that give | 復元（que≡that） |
| es | que toma | 0/9 | 9/9 | que takes → that takes | 復元（que≡that） |
| es | que va | 0/9 | 9/9 | que goes → that goes | 復元（que≡that） |
| es | que ve | 0/9 | 9/9 | que sees → that sees | 復元（que≡that） |
| fr | que dit | 0/9 | 9/9 | que says → that says | 復元（que≡that） |
| fr | que ont voulu | 0/9 | 9/9 | que have wanted → that … | 復元（que≡that） |
| fr | que ont eu | 0/9 | 9/9 | que have had → that … | 復元（que≡that） |
| fr | que ont su | 0/9 | 9/9 | que have known → that … | 復元（que≡that） |
| it | que sa | 0/9 | 9/9 | que knows → that knows | 復元（que≡that） |
| it | que dà | 0/9 | 9/9 | que gives → that gives | 復元（que≡that） |
| pt | que acha | 0/9 | 9/9 | que finds → that finds | 復元（que≡that） |
| pt | que vem | 0/9 | 9/9 | que comes → that comes | 復元（que≡that） |
| de | que denkt | 0/9 | 9/9 | que thinks → that thinks | 復元（que≡that） |
| es | dijo | 0/9 | 0/9 | 回答 “he said”。公式は he/she/it has said のみ | 反転のまま |
| es | dijiste | 0/9 | 0/9 | 回答 “you said”。公式は you have said のみ | 反転のまま |
| es | pensamos | 0/9 | 0/9 | 回答 “we think”。公式は we thought / we have thought | 反転のまま |
| la | inter alia（among others） | 9/9 | 9/9 | 形のレコードが 9/9（among other things で測定）。among others はこの形の公式ソース | 復元（形単位ルール、myon 承認） |
| la | quotidie | — | — | レコードなし、la_blind.json にも文なし | 反転のまま・untested |

* 付随して、cdb8953 で採用されていた parity follower（fr these / those ont su）が tense_matrix に戻った。
  レコードは以前から pass。昇格ではなく元に戻しただけ。
* zh 書店 / 超市 / 前端 / 截图 は回答の綴りが公式 `from` にないため 0/9 のまま。
* その他の que 形（es que hizo / que dijo / que dijeron、pt que deram 等、de que kam 等、nl que nam 等）は
  equivalence を適用しても 0/9 のまま。
* **la inter alia**：myon の承認（「la inter alia は戻していい」）を受け、形単位の any-official-source
  ルールで `among-others-la` を採用に戻した（1602fce のエントリそのまま、examples_not_registered の行は削除）。
  `inter alia` のレコードは among other things で 9/9 pass しており、among others は同じ形の公式ソースである。
  ただし「among others」と「inter alia」は stdlib の推定でも o200k でも 2 = 2 の同点で、厳密に削減する
  ルールによりランタイムでは英語のまま残る（生成物にも差分なし）。quotidie は untested・反転のまま。

## 言語別集計（latest cohort、再採点後）

| lang | 旧 pass / never | 新 pass / never |
|---|---|---|
| de | 32 / 53 | 34 / 51 |
| es | 105 / 24 | 110 / 19 |
| fr | 96 / 17 | 102 / 11 |
| it | 28 / 3 | 30 / 1 |
| pt | 210 / 60 | 212 / 58 |
| zh | 37 / 25 | 42 / 20 |
| cs / el / la / nl / pl | 変化なし | 変化なし |

復元数の合計は 4848/6678 から 5046/6678 になった。状態が変わったのは上記の 22 形だけ。

## 制約

`ROUNDTRIP_ENFORCED_LANGS` は {nl} のまま。新しい env、候補の追加、ほかの言語の勝者の変更はない。
Issue #29 と C 層には触れていない。PR #179（`fix/es-pt-remaining-roundtrip-20261110`、084e343d）も
`roundtrip.json` の run_history の末尾とレコードに追記しているため、マージ時にはそこで衝突が見込まれる。
後からマージする側で `rescore_accepted_sources.py --run` を再実行すること。
