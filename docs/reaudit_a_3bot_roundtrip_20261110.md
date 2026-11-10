# 3bot 再監査（分類 a）: リバース済み 13 形の文脈付き独立ブラインド往復（2026-11-10 JST / Asia/Tokyo）

## 対象と方法（#179 方式）

main `2e5312adc25c445685994aa03211804bd1d7ef4a` でリバース（英語のまま）になっている 13 形を、#179 と同じ「3 文脈 × 公式 3 テンプレート = 各形 9 文」で測り直した。

- 公式テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.` を、文脈文（採用英語の位置を `{s}`）ごとにそのまま適用。`?` を含む文脈は `…didn't you?.` / `…? today.` のような不自然な文になるが、テンプレート規則から外さずそのまま使った（norm-nfc-v1 は句読点を落とすので採点には影響しない）。
- 文脈文は 3bot 再監査の `proposed_contexts`（作業側が自作したもの。コーパス由来ではない）。#179 にならい先頭を小文字化（`{s}` / `I` 始まりは除く）。
- **判定は 1 文 = 1 回の独立呼び出し（計 117 回）**。各呼び出しには `scripts/roundtrip.py` の公式 PROMPT と変換文 1 文だけを渡した（リポジトリ・英語ソース・他の文は見せない）。#179 は 36 文を 1 回で判定しており文どうしの相互推測ができたが、今回はそれができない。
- 回答は ID なしで判定完了順に返ってきたので、**内容照合で文に割り当てた**（各回答と各文の英語ソース文・変換文のトークン列類似度、ハンガリアン法の全単射）。テンプレート標識（素 / Maybe…today / She…）と文脈の英語が文ごとに一意なので、形ごとの集計は割り当ての揺れに影響されない（形内で回答を入れ替えても exact 数は同じことを確認）。回答そのものは無修正。
  - 生の回答: `roundtrip_judge/reaudit_a_3bot_raw_answers.txt`（117 行、判定完了順）
  - 割り当て後: `reaudit_a_3bot_blind.json`（`{変換文: 回答}` の平坦な dict、`roundtrip_replay.py reaudit_a_3bot` で再生）、`reaudit_a_3bot_sources.json` の `request_id`
- 採点は `roundtrip.run()`（`accepted_sources` = その entry の公式英語ソース、any-official-source-v1）。seeds [1,2,3] は決定的 replay なので 1 文 1 回答を 3 seed で使い回す（各形 27 targets）。ゲートは exact（norm-nfc-v1）、ge100m（fr/pt/es/zh）は ≥ 0.6、min_trials 9、rate 0 は不可。
- meaning（参考、ゲートに使わない）は**独立判定ではない**: 文と期待英語を作った作業 bot 自身が判定した（別の判定呼び出しはしていない）。規則は「行為者・動詞の意味・テンプレート語（Maybe / today）が変われば different、間接話法への言い換えは same」。
- 再現: `uv run python scripts/reaudit_a_3bot_roundtrip.py --check`（`roundtrip.json` のコピーに対して run() を回し、結果を `reaudit_a_3bot_results.json` と比較）。

## 結果

| 形 | exact | meaning（参考） | 判定 | 本 PR での扱い |
|---|---|---|---|---|
| fr vis | 8/9 | 9/9 | pass | `ROUNDTRIP_REVERSED` から外す |
| fr vins | 7/9 | 9/9 | pass | 同上 |
| fr sus | 6/9 | 6/9 | pass | 同上 |
| fr voulus | 9/9 | 9/9 | pass | 同上 |
| fr prends | 6/9 | 6/9 | pass | 同上 |
| fr avais su | 9/9 | 9/9 | pass | 同上 |
| fr ira | 9/9 | 9/9 | pass | 同上（数一致追従 `this ira` も採用に戻る） |
| fr arrivé | 6/9 | 9/9 | pass | es_fr_tense `arrive-past-1s` を entries に戻す |
| pt virá | 9/9 | 9/9 | pass | `ROUNDTRIP_REVERSED` から外す |
| pt essayé（データ上 pt） | 6/9 | 7/9 | pass | es_fr_tense `try-past-1s` を **lang fr に直して** entries に戻す |
| pt farei | 4/9 | 8/9 | fail | リバース維持（examples_not_registered のまま） |
| es pensamos | 9/9 | 9/9 | pass | **報告のみ**。データは触らない（下記） |
| zh 几点 | 4/9 | 9/9 | fail | リバース維持（examples_not_registered のまま） |

6/9（0.667）で境界通過したのは sus / prends / arrivé / essayé。

### 不一致の中身

- vis: `Maybe you saw the accident yourself today, didn't you?`（today の位置）
- vins: `Why did you come alone…`（素・She の 2 文。公式ソースは不自然な `Why you came alone…`）
- sus: `you suspected`（3 文。sus = knew）
- prends: `You always say I take too long…`（3 文、主語が I に）
- arrivé: `after arriving home late`（3 文、意味は同じ）
- essayé: `I tried … salty today.`（Maybe 落ち）、`yesterday she tried`、`She told me not to blame her, she tried…`
- farei: `I'll do them`（目的語 them）×2、`she would do it herself` / `she would do them`（間接話法）、`… tonight.`（today 落ち）
- 几点: `Can you check what time it is?`（間接疑問の語順、3 文）、`She told me, "Excuse me, …"`、`She asked me what time it is now.`。文脈 c2（can you check {s}）は公式ソース `what time is it` が間接疑問の中で不自然になる設計上の問題もある。

### 回答の割り当てで判断が要ったもの（テンプレート標識が崩れた回答）

| 文 | 回答 | 割り当ての根拠 |
|---|---|---|
| s092 `Maybe essayé the soup myself … today.` | `I tried the soup myself and it was too salty today.` | today 付きの soup 文はこれだけ（Maybe 落ち） |
| s022 `Maybe the report is not finished, but farei tonight today.` | `Maybe the report is not finished, but I will do it tonight.` | Maybe 付きの report 文はこれだけ（today 落ち） |
| s044 `Maybe vis the accident yourself, didn't you? today.` | `Maybe you saw the accident yourself today, didn't you?` | today の位置だけ移動 |
| s102 `Maybe can you check 几点? …` | `Maybe you can check what time it is? …` | Maybe 付き |
| s016 / s061 | `She told me, "…"`（直接話法） | She 付きの同文脈はこれだけ |
| s073 / s093 / s028 / s008 | 間接話法・人称転換（she would / she tried） | 同上 |
| s103 / s117 | `She asked me …` | 同上 |

## データの変更

- `scripts/tense_matrix.py` `ROUNDTRIP_REVERSED` から 8 行削除: fr vis / vins / sus / voulus / prends / avais su / ira、pt virá。tense_matrix bank は +9 entry（基底 8 + `this will go → this ira`）、削除 0。
- `es_fr_tense.json`: `arrive-past-1s`（arrivé, fr）と `try-past-1s`（essayé, **lang fr**）を元の位置に戻した。essayé の metrics は元の tentei 行のまま（essayé は `I tried` と同じ 7 バイトで、o200k トークンだけ縮む）。
- `roundtrip.json` は書いていない（2bot 側の担当）。このため戻した形の gate-visible な record は素の 0/9（never、fr essayé は record なし）のままで、`mapping_graph --check` では fr never 8 / untested 1、pt never 1 と表示され、`docs/roundtrip-impact.md` でもゲート時は次点へ移る扱いになる。文脈 cohort は `reaudit_a_3bot_results.json` にあり、テストはこのファイルを根拠に該当形だけを例外扱いしている。
- es pensamos は es が `ROUNDTRIP_REVERSED_DROP_CANDIDATE_LANGS` で、`we thought` が `ROUNDTRIP_REVERSED_SOURCES` にも入っているため、`ROUNDTRIP_REVERSED` だけ外しても bank は変わらない。2bot の過剰リバース検証と合わせて判断するので本 PR では触らない。
- pt virá と #178: #178（未マージ）は `this virá` を基底リバースに合わせて除外する。virá が通過したので、本 PR が先に入ると #178 の除外は発火せず `this virá`（9/9）は採用のまま整合する。どちらが先に入っても生成物（tense_matrix.json など）は再生成が必要。

## トークン・バイト（戻した 11 対応、o200k_base は文中扱いの先頭スペース付き）

| EN → 変換 | o200k tokens | UTF-8 bytes |
|---|---|---|
| you saw → vis | 2 → 1 | 7 → 3 |
| you came → vins | 2 → 1 | 8 → 4 |
| you knew → sus | 2 → 1 | 8 → 3 |
| you wanted → voulus | 2 → 2 | 10 → 6 |
| you take → prends | 2 → 1 | 8 → 6 |
| you had known → avais su | 3 → 2 | 13 → 8 |
| it will go → ira | 3 → 1 | 10 → 3 |
| this will go → this ira | 3 → 2 | 12 → 8 |
| I arrived → arrivé | 2 → 1 | 9 → 7 |
| it will come → virá | 3 → 2 | 12 → 5 |
| I tried → essayé | 2 → 1 | 7 → 7 |
| 合計 | 26 → 15 | 104 → 60 |

AI 可読性: 上の exact / meaning が今回の測定値（文脈付き・1 文 1 呼び出し）。素の形（文脈なし）の 0/9 は roundtrip.json に残っている。
