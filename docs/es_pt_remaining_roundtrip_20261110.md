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

## 結果（4形すべて 0/9・リバース）

| 形 | 判定の復元（3テンプレート） | 一致 | 判定 |
|---|---|---|---|
| tomaré | I will take it. / Maybe I will take it today. / She told me that I will take it. | 0/9 | never → リバース |
| acharei | I will find it. / Maybe I will find it today. / She told me that I will find it. | 0/9 | never → リバース |
| logo | Soon. / Maybe later today. / She told me that soon. | 0/9 | never → リバース |
| por isso | That's why. / Maybe that's why today. / She told me that that's why. | 0/9 | never → リバース |

tomaré / acharei は意味は合っているが、判定が目的語 `it` を補ったため norm-nfc-v1 の厳密一致にならない。
logo は「すぐに」、por isso は「だから」と読まれ、公式ソース（as a result / for this reason）と一致しない。
回答は書き換えていない。

## リバース

4形とも手書き bank の形なので `tense_matrix.py` の `ROUNDTRIP_REVERSED` は変更していない（差分0行）。
#171 の pt リバースと同じく、entry 全体を `examples_not_registered` に `roundtrip_reversed: true` と
`why_dropped`（実際の復元を含む）付きで移した。`_existing_sources()` が reversed 行の `from` を予約するので、
tense_matrix がこの英語ソースを埋めることはなく、`tense_matrix.py --check` は up to date のまま（生成 bank 差分なし）。

- `I will take` / `I am going to take` / `I will find` / `I am going to find` は英語のまま。次点（pt tomarei など）は昇格させない。
- `as a result` / `for this reason` は英語のまま。el `άρα` は昇格させない（候補から外れたため `calibrate_estimate.py --write` で o200k_calib.json の `άρα` 1語が抜けた）。

`ROUNDTRIP_ENFORCED_LANGS` は `{nl}` のまま。他言語の winner・記録は変更していない。

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

## AI 可読性（必須）

12文中 **0/12** 文が公式受理英語と norm 一致（試行換算 **0/36**）。
意味の取り違えは logo / por isso で、tomaré / acharei は目的語 `it` の補完による不一致。
この3テンプレート以外の自由文での可読性は **未測定**。

## 範囲

Issue #29、C 層 in favor of→pro、他言語の勝者データ・記録は変更していない。
