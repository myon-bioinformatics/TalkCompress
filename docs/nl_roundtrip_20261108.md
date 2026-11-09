# オランダ語（nl）採用形の往復確認（2026-11-08 JST）

## 対象と結果

main `84e5dca0028d90db73254af33ac2d9d3ce545790` の採用 winner を確認。
nl は lt100m、閾値 0.9、min_trials 9。未検証だった採用6形はすべて通過した。

| fixture / id | 元の英語 | 採用形 | AI が復元した英語 | 復元 / 完了 |
|---|---|---|---|---|
| es_fr_tense / think-pres-1s | I think | denk | I think | 9/9 |
| es_fr_tense / take-pres-1s | I take | neem | I take | 9/9 |
| zh_de_phrases / staubsauger | vacuum cleaner | stofzuiger | vacuum cleaner | 9/9 |
| zh_de_phrases / wasmachine | washing machine | wasmachine | washing machine | 9/9 |
| zh_de_phrases / suchmaschine | search engine | zoekmachine | search engine | 9/9 |
| zh_de_phrases / zwembad | swimming pool | zwembad | swimming pool | 9/9 |

外した採用形はない。そのため examples_not_registered の追記やバンクの変更も不要。
既存の通過8形 gaan, kom, komen, que wil, weten, which wil, who wil, zien はそのまま残した。
vond / dacht / nam / zei などの既存の失敗記録は変更せず、証拠として維持した。

## 方法・限界

既存 nl_blind と PR #161 の la_blind と同じく、変換後18文に対する AI の復元回答を
roundtrip_judge/nl_blind.json に記録し、既存 roundtrip_replay.py nl を
scripts/roundtrip.py の run() で実行した。新しい外部 LLM API は使っていない。
今回の採点回答は、リポジトリ・元英語・担当指示の英語注釈にアクセスしない独立した判定エージェントが
変換後の文だけを見て復元し、親エージェントから受領したもの。既知の元英語から回答を作っていない。

先行した非独立の暫定 cohort は削除せず judge_provenance で採用根拠にできないことを明記した。
独立判定後に同じスクリプトで新しい cohort を追加し、現在の判定は latest_cohort の9/9だけに基づく。
累積 trials=18 は暫定9件と独立判定の replay 9件の履歴であり、18件の独立評価を意味しない。
今回の回答は先行暫定回答と結果的に一致したが、検証根拠は独立判定の方である。

3テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.` と seeds [1, 2, 3]。
各形9件、計54件を run() が数えた。件数の手編集はしていない。
replay は決定的で全 seed に同じ回答を返すため、54件の独立した AI 推論ではない。
ここでの厳密一致は既存 norm-nfc-v1（NFC、大小文字・句読点・空白の正規化後の一致）であり、
生文字列のバイト一致ではない。候補を変えたり、採点方式を変えたりしていない。

CLI の --lang nl だけでは tense_matrix.build() の8形しか対象にならないため、
今回の6形は es_fr_tense.json と zh_de_phrases.json の entry.to から選択して
同じ run(data, cmd, only_lang="nl", entries=entries) に渡した。
run_history と各形の cohort に実行設定・対象・結果が記録される。

## AI 可読性（必須）

今回の18変換文は上表の英語に戻せた（6形とも9/9）。少なくともこの3テンプレートでは
AI が変換後を読んで元の英語に復元できる証拠になった。
ただし独立した意味理解・自然な文章・自由文の可読性評価は **未測定**。
名詞を動詞用テンプレートに入れた文には不自然なものがあり、一般的な可読性を保証しない。

## Issue #29 の required と現在の winner のずれ

Issue #29 は nl 過去形を英語現在完了へ採用した65セル・47形、未実施・report-only と記載している。
しかし現在の tense_matrix.json の nl winner は8セルすべて pres（現在形）で、perf は0セル。
roundtrip.required も []。Issue に列挙された47形は、現在の nl winner 14形のいずれでもない。
今回は現在の採用 winner の不足6形だけを補完したので、Issue の47形を新規採用したり
再検証済みだと扱ったりしていない。nl の tense_matrix ゲートは既に有効であり、
Issue の report-only / 記録0件という説明も現在とは一致しない。Issue 本文は変更していない。

## 範囲

#157（改名）・#161（ラテン語）のブランチは変更していない。共有する roundtrip.json は
マージ時に nl の追加 cohort を保持して競合解消する必要がある。C 層 in favor of→pro は対象外。
バンクの採用結果は変化しないため tense_matrix.json / 生成スクリプトの変更は不要。

## テスト

`uv run pytest`: **5901 passed, 5 skipped, 1 xfailed**（独立判定 cohort 追加後の最終再実行）。
`uv run python scripts/tense_matrix.py --check` と `git diff --check` も成功。
