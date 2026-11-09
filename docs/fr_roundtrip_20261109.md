# フランス語（fr）採用形の独立ブラインド往復確認（2026-11-09 JST）

## 対象

main `cdb895387170d42990ebf93573a307959b92c148` の fr 採用 winner を公式データから数え直した。
`tense_matrix.build()` の fr 133エントリ・110形（コミット済み `tense_matrix.json` と同一）と、
`es_fr_tense.json` の `lang=fr` 4エントリ（pris / écrirai / vivrai / arrivé）で、
計 **137エントリ・113ユニーク形**（`pris` は両ファイルにある）。開始時点で `fr:*` の往復記録は0件だった。

fr は `ge100m_langs` に含まれるため閾値は restore rate ≥ 0.6。
min_trials 9、seeds [1, 2, 3]、テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`。
trials > 0 で rate 0（status `never`）は全言語共通で不可。採点は既存 `norm()`（norm-nfc-v1）。

## 結果（113形中 96形通過・17形リバース）

通過した96形はすべて 9/9。0/9 以外の途中値はなかった。

| 形 | 出典 | 復元 / 完了 | 判定 |
|---|---|---|---|
| veux, ai voulu, ai eu, ai su, serai allé, serai venu, aurai fait / vu / pris / trouvé / voulu / eu / dit / su | tense_matrix | 各 9/9 | pass |
| venez, pensez, feras, trouverez, penseras, diras, sauras, allas, dîtes | tense_matrix | 各 9/9 | pass |
| dit, fera, prendra, voudra, pensera, dira, saura, sut, sera venu（共有形） | tense_matrix | 各 9/9 | pass（下記ルール） |
| prendrons, penserons, dirons, saurons, sûmes, avons voulu / eu / su, aurons trouvé, avions su | tense_matrix | 各 9/9 | pass |
| voudront, ont voulu, ont eu, auront fait / vu / pris / trouvé / voulu / eu / dit / su / donné, avaient su | tense_matrix | 各 9/9 | pass |
| this ira / fera / prendra / voudra / pensera / dira / saura / sera venu | tense_matrix | 各 9/9 | pass |
| these・those voudront / ont voulu / ont eu / ont su / auront fait / vu / pris / trouvé / voulu / eu / dit / su / donné | tense_matrix | 各 9/9 | pass |
| who dit, which dit, which ont voulu / ont eu / ont su | tense_matrix | 各 9/9 | pass |
| écrirai, vivrai | es_fr_tense | 各 9/9 | pass |
| **prends**（you take） | tense_matrix | **0/9** | never（判定は `I take`） |
| **vins / vis / voulus / sus**（you came / saw / wanted / knew） | tense_matrix | **各 0/9** | never（判定は `I came` / `I saw` / `I wanted` / `I knew`） |
| **pris**（you took。es_fr の I took と共有） | tense_matrix + es_fr_tense | **0/9** | never（判定は `I took`） |
| **avoir voulu / avoir eu / avoir su**（you have wanted / had / known） | tense_matrix | **各 0/9** | never（判定は `To have wanted` などの不定詞） |
| **avais su**（you had known） | tense_matrix | **0/9** | never（判定は `I had known`） |
| **ira**（it will go） | tense_matrix | **0/9** | never（判定は `He will go`） |
| **ont su**（they knew。they have known と共有） | tense_matrix | **0/9** | never（判定は `They have known`） |
| **que dit / que ont voulu / que ont eu / que ont su** | tense_matrix | **各 0/9** | never（判定は `That says` / `That have …`） |
| **arrivé**（I arrived） | es_fr_tense | **0/9** | never（判定は `He arrived`） |

## リバース

- tense_matrix の16形: 生成 JSON は手編集せず、`scripts/tense_matrix.py` に個別の
  `ROUNDTRIP_REVERSED`（fr 16形）を追加して再生成した。言語単位の強制（`ROUNDTRIP_ENFORCED_LANGS`）は
  `{nl}` のまま広げておらず、fr の他の形は report-only のまま。
  順位付け後の勝者がリバース対象のセルは `status=reject`・`cell["roundtrip_reversed"]` を記録して英語のまま残し、
  次点の他言語候補（英語同形を含む）は昇格させない。
- #168 との違い: #168 は「候補にリバース対象を含むセルを空にする」実装だったが、fr ではそのままだと
  vins / vis / voulus / avais su が負け候補として入っている 1s セルの他言語 winner（de kam / de sah / pt quis / pt soubera）まで消える。
  他言語の勝者を書き換えないため、**勝者がリバース対象のときだけ**英語に戻す形にした。
- パリティ連動: 数のパリティ規則（this / these / those は数が一致する代名詞の勝者を主語付きで再利用するか英語）により、
  代名詞側の `ira`（it will go）と `ont su`（they have known）を英語に戻した結果、自身は 9/9 で通過した
  `this ira` / `these ont su` / `those ont su` の3形も英語に戻った（`tests/test_tense_matrix.py` のパリティ検査に従う）。
  往復記録はいずれも pass のまま残している。
- es_fr_tense.json の2形: `take-past-1s`（pris）と `arrive-past-1s`（arrivé）だけを `entries` から
  `examples_not_registered` に理由付きで移した（#164 / #168 の ciao と同じ方式）。es / pt / de / el / nl のエントリは無変更。
  候補の es tomé / llegué、pt cheguei、nl kwam aan、el έφτασα は昇格させていない（英語のまま）。
- `I took` は es_fr から外れるとマトリクスで新規セル扱いになり de `nahm` が採用されるため、
  `ROUNDTRIP_REVERSED_SOURCES = {"i took"}` で英語のまま残した（新しい候補は追加していない）。
- 結果として fr の採用は tense_matrix 113エントリ・91形 + es_fr 2形（écrirai / vivrai）= **93形**。
  他言語の winner は origin/main と同一（変更は fr 20エントリの削除のみ）。
- 失敗17形の記録は `roundtrip.json` に証拠として残した。

## 方法・provenance

変換後339文（113形×3テンプレート）を、リポジトリ・元英語・担当指示の注釈にアクセスしない
独立判定エージェントが変換文だけを見て復元し（3バッチ、親エージェント経由で受領）、回答は無修正で
`roundtrip_judge/fr_blind.json`（変換文→復元文）に記録した。既存 `scripts/roundtrip_replay.py fr` を
`scripts/roundtrip.py` の `run(data, cmd, only_lang="fr", entries=...)` に渡して採点した。1017件すべて完了、
タイムアウト・実行エラー 0。件数は run() が数え、手編集していない。各 cohort に `judge_provenance`
（kind: independent_blind_judge）を付けた。

**replay の注意**: replay は決定的で、全 seed に同じ回答を返す。各形9件（3テンプレート×3 seed）は
3件の独立回答の再利用であり、seed ごとの独立した AI 推論ではない。

**CLI ではなく entries= を使った理由**: `--lang fr` は `tense_matrix.build()` しか列挙しないため
écrirai / vivrai / arrivé が漏れ、また共有形の全エントリを渡してしまう。

**共有形のルール（回答を見る前に固定）**: #168 と同じく、ユニーク形ごとに bank 順
（`tense_matrix.build()` の fr、続いて `es_fr_tense.json` の fr）で最初のエントリ1件の対象を run() に渡した。
同じ変換文を生むエントリ（he/she/it、says/said の `dit`、I/you の `veux`、knew/have known の `ont su`、
tense_matrix / es_fr の `pris`）はこの1件の元英語でのみ採点される。
参考: `pris`（判定 `I took` = es_fr の元英語）と `ont su`（判定 `They have known` = 2番目のエントリ）は
別ソースなら一致していたが、回答を見てから採点元を選ばないため 0/9 のまま扱った。

## AI 可読性（必須）

独立判定は339文すべてに復元を返した（空回答なし）。norm 後に公式の期待英語（各形の最初のエントリ）と一致したのは
**288/339 文**（通過96形が各3/3、リバース17形が各0/3）。同じ変換文の別エントリの英語まで許すと 294/339
（pris・ont su の6文が増えるだけ）。復元文の一致判定のみで、別の可読性ルーブリックによる評価はしていない。
不一致の大半は、主語を落とした2人称形を1人称（`I …`）で、`avoir …` を不定詞で、`que …` を `That …` で読んだもの。
この3テンプレート以外の自由文での可読性は **未測定**。

## 範囲

既存 `required` は [] のまま、往復ゲートの強制は有効化していない（`ROUNDTRIP_ENFORCED_LANGS` は `{nl}`）。
Issue #29 本文、C 層 in favor of→pro、他言語の勝者データ・記録、#153 #154 #157 #161–#170 のブランチは変更していない。
新しい言語候補は追加していない。共有の `roundtrip.json` / `tense_matrix.py` / `tense_matrix.json` / `es_fr_tense.json` は
#168 / #169 など他言語 PR と競合しうるので、マージ時は fr の cohort と `ROUNDTRIP_REVERSED` の両方の項目を保持して解消すること。

## テスト

再生成: `scripts/tense_matrix.py`（tense_matrix.json / docs/tense-matrix.md / docs/tense_matrix_report.json）、
`scripts/tokenizer_compat.py --compat`、`scripts/roundtrip.py --write-doc`（docs/roundtrip-impact.md、report-only）、
`scripts/calibrate_estimate.py --write`（o200k_calib.json から外れた arrivé / έφτασα の2語のみ）。
既存テストのうち、リバースした形を前提にしていた `test_final_zh_de.py`（tranche2 の件数・終端）、
`test_pd20_examples.py`（frank-arrived を keep に）、`test_stative_perfect.py`（you have known/had/wanted は英語）、
`test_you_u.py`（you came → you come）を更新し、`tests/test_fr_roundtrip_gate.py` を追加した。
