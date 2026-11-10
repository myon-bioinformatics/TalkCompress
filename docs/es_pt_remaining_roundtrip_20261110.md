# es / pt 未往復の採用4形の独立ブラインド往復確認（2026-11-10 JST / Asia/Tokyo）

## 対象

main `2e5312adc25c445685994aa03211804bd1d7ef4a` で採用中なのに往復記録が無かった4形。
#161（la ergo / ideo のリバース）と #164（el πάρω / βρω のリバース）で次点が繰り上がったが、
es（#172）・pt（#171）のブラインド判定より後だったため未測定だった。

| 記録キー | bank / entry | 受理する公式英語（any-official-source-v1） |
|---|---|---|
| es:tomaré | es_fr_tense `take-fut-1s` / `take-fut-goingto-1s` | I will take / I'll take / I am going to take / I'm going to take |
| pt:acharei | es_fr_tense `find-fut-1s` / `find-fut-goingto-1s` | I will find / I am going to find / I'm going to find |
| pt:logo | pt_el_latin_phrases `as-a-result-la-pt-el` | as a result |
| pt:por isso | pt_el_latin_phrases `for-this-reason-la-pt` | for this reason |

測定前のソースは `roundtrip_judge/remaining_20261110_sources.json` に凍結した。
es / pt は `ge100m_langs` なので閾値は restore rate ≥ 0.6。trials > 0 で rate 0（never）は全言語で不可。
min_trials 9、seeds [1, 2, 3]、テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`、norm-nfc-v1。

## 結果（2形採用維持・2形リバース）

| 形 | 素の形 exact | 文脈付き exact | 文脈付き meaning（参考） | 最終 |
|---|---|---|---|---|
| es tomaré | 0/9 | **9/9** | 9/9 | **採用維持**（リバース取り消し） |
| pt acharei | 0/9 | **9/9** | 9/9 | **採用維持**（リバース取り消し） |
| pt logo | 0/9 | 0/9 | 9/9 | リバース（英語のまま） |
| pt por isso | 0/9 | 0/9 | 9/9 | リバース（英語のまま） |

ゲートは exact（norm-nfc-v1、ge100m ≥ 0.6、trials>0 で rate 0 は不可）のまま。meaning はゲートに使わない参考値。

### 素の形（`{s}.` ほか公式3テンプレート）

| 形 | 判定の復元 | exact |
|---|---|---|
| tomaré | I will take it. / Maybe I will take it today. / She told me that I will take it. | 0/9 |
| acharei | I will find it. / Maybe I will find it today. / She told me that I will find it. | 0/9 |
| logo | Soon. / Maybe later today. / She told me that soon. | 0/9 |
| por isso | That's why. / Maybe that's why today. / She told me that that's why. | 0/9 |

tomaré / acharei の不一致は目的語 `it` の補完だけだったので、目的語を与えた文脈で測り直した。

### 文脈付き（3文脈 × 公式3テンプレート = 各形9文）

採用英語が自然な読みになる文脈を作り（例 `I will take the bus.` → `Tomaré the bus.`）、公式3テンプレートで包んだ。
依頼文に採用英語そのもの（take / find / as a result / this reason）は一切出していない。

| 形 | 文脈（採用英語の位置を {s} で表記） | 判定の復元例 | exact |
|---|---|---|---|
| tomaré | {s} the bus / {s} the blue one / {s} your advice | I will take the bus. | 9/9 |
| acharei | {s} the key / {s} a better job / {s} your phone | I will find the key. | 9/9 |
| logo | the bus broke down and {s} we were late ほか2文 | The bus broke down, so we were late. | 0/9 |
| por isso | the shop is closed and {s} we are going home ほか2文 | The shop is closed, so we are going home. | 0/9 |

logo / por isso は意味は合っている（meaning 9/9）が、判定は `so` で言い換え、公式ソース（as a result / for this reason）と exact 一致しない。

### 記録の仕方

- **素の形の cohort**（4形とも 0/9）は全形の `records` に残した（履歴は保持）。
- **文脈 cohort が通過した形**（tomaré / acharei）は、同じ `records[lang:form]` に gate-visible な cohort として追記した。
  最新 cohort が通過なので `status()` は pass。テンプレートは各形の文脈テンプレート9本（`config.templates`）、受理英語は文脈中の採用英語だけ。
  seeds [1, 2, 3] の replay なので各形 27 targets（9文 × 3 seed の再利用）、27/27。
- **文脈 cohort が不通過の形**（logo / por isso）は、`run()` を scratch コピーに対して実行し、その cohort を
  `context_studies.remaining_20261110` に `gate_visible: false` で保存した。`records` の最新は素の形 0/9 のままなので、`status()` は never でリバースと一致する。
- 各文脈 cohort に `meaning_match_ref`（変換文ごとの same / different）を付けた。ゲートには使わない。
- すべて `scripts/remaining_roundtrip_20261110.py --run-context` が `run()` で数えた。手編集していない。

## 採用維持とリバース

- tomaré / acharei: `es_fr_tense.json` の take-fut-1s / take-fut-goingto-1s / find-fut-1s / find-fut-goingto-1s を main と同一に戻した（リバース取り消し）。
- logo / por isso: #171 の pt リバースと同じく、`pt_el_latin_phrases.json` の entry 全体を `examples_not_registered` に
  `roundtrip_reversed: true` と `why_dropped` 付きで移した。`as a result` / `for this reason` は英語のまま。el `άρα` は昇格させない
  （候補から外れたため `calibrate_estimate.py --write` で o200k_calib.json の `άρα` 1語が抜けた）。
- 4形とも手書き bank の形なので `tense_matrix.py` は差分0行。`tense_matrix.py --check` は up to date。
- `ROUNDTRIP_ENFORCED_LANGS` は `{nl}` のまま。他言語の winner・記録は変更していない。

## 方法・provenance

判定は作業担当の assistant ではなく、文脈を持たない独立した強いモデルのエージェント（#172 と同水準）が行った。
1回の呼び出しで `scripts/roundtrip.py` の公式 `PROMPT` と変換文12文だけを受け取り、リポジトリ・元英語・注釈には触れていない。
番号付きの返答は無修正で保存（SHA256 `1c6c4c121d20e9fc3873de6a2785ebbbcde86bb231ab250aad63ad306f77fca3`）し、
`N. ` の番号だけを変換文に対応付けて `roundtrip_judge/remaining_20261110_blind.json` に記録した。
`scripts/remaining_roundtrip_20261110.py --run` が `scripts/roundtrip_replay.py remaining_20261110` を
`run(entries=..., accepted_sources=...)` で再生した。件数は run() が数え、手編集していない。

**replay の注意**: replay は決定的で、全 seed に同じ回答を返す。各形9件は3件の回答の再利用であり、
seed ごとの独立推論ではない。

**先行判定（採点対象外）**: 先にローカルの Qwen2.5-7B-Instruct（Q4_K_M、temperature 0、1文1呼び出し）でも判定したが、
myon の依頼で上記の判定に置き換えた。roundtrip.json には記録していない。参考までに当時の復元は
tomaré「I will take.」ほか 3/9、acharei 0/9（After that. 等）、logo 0/9（Look at the logo. 等）、
por isso 6/9（Therefore. / Maybe for this reason today. / She told me that for this reason.）だった。

**文脈付きの判定**: 別の、文脈を持たない独立した強いモデルのエージェントが、1回の呼び出しで公式 `PROMPT` と
番号付き・シャッフル済み（`random.Random(20261110)`）の変換文36文だけを受け取って復元した
（依頼 SHA256 `cabb6f38…d54c`、返答 SHA256 `cdd34ac2…599a`、無修正）。番号を変換文に対応付けて
`roundtrip_judge/remaining_20261110_ctx_blind.json` に記録し、文脈設計（答え）は `remaining_20261110_ctx_sources.json` に凍結した（判定には見せていない）。
meaning は、さらに別の文脈なしエージェントが A（期待英語）/ B（判定の復元）の36組だけを見て same / different を答えたもの
（組 SHA256 `0ef30a89…`、回答 SHA256 `e3f3c035…`、`remaining_20261110_ctx_meaning.json`）。

**開示**: 文脈は私たち（PR 作成側）が設計した。36文を1回で判定したので、判定は文どうしを見比べて推測できる
（同じ形が9回出る）。replay は決定的で、各文の1回答を3 seed で再利用している。

## AI 可読性（必須）

- 素の形: 12文中 **0/12** 文が exact 一致（試行換算 0/36）。
- 文脈付き: 36文中 **18/36** 文が exact 一致（tomaré 9/9、acharei 9/9、logo 0/9、por isso 0/9）。meaning（参考）は **36/36**。
- この2種類のテンプレート以外の自由文での可読性は **未測定**。

## 範囲

Issue #29、C 層 in favor of→pro、他言語の勝者データ・記録は変更していない。
