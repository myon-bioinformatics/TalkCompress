# ドイツ語（de）採用形の独立ブラインド往復確認（2026-11-09 JST / Asia/Tokyo）

## 対象

origin/main `cdb895387170d42990ebf93573a307959b92c148`（#152 / #167 マージ後）の de 採用 winner を公式データから数え直した。

| 出典 | エントリ | ユニーク形 |
|---|---:|---:|
| tense_matrix.json | 120 | 68 |
| zh_de_phrases.json | 17 | 17 |
| es_fr_tense.json | 1（fand、tense_matrix と共有） | 0 追加 |
| **合計** | **138** | **85** |

開始時点で `de:*` の往復記録は 0 件。ヒントの 85 形 / 138 エントリと一致。

de は `ge100m_langs` に含まれるため閾値は restore rate ≥ 0.6。
min_trials 9、seeds [1, 2, 3]、テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`。
trials > 0 で rate 0（status `never`）は全言語共通で不可。採点は既存 `norm()`（norm-nfc-v1）。

## 結果（85形中 32形通過・53形リバース）

### 維持（32形、各 9/9）

- tense_matrix（18形）: kam, sah, dachtest, denkt, nehmen, finden, wollen, denken, sagen, kamen, sahen, nahmen, fanden, wollten, sagten, dachten, who denkt, which denkt
- zh_de_phrases（14形）: Bahnhof, Datenschutz, Handy, Ampel, Stau, Lenkrad, Mikrowelle, Klimawandel, Haustür, Kraftwerk, Kernenergie, Geburtsurkunde, Telefonnummer, Erderwärmung

### リバース（53形、すべて 0/9 = never）

#### tense_matrix（50形）→ `ROUNDTRIP_REVERSED`

ドイツ語単純過去が英語の現在完了ソースに紐づいている共有面、および `que` 関係詞面が主因。

- 完了ソースに対する単純過去復元: nahm, fand, dachte, kamst, tatest, nahmst, taten, this kam, this sah, this nahm, this fand, this dachte, these kamen, these sahen, these nahmen, these fanden, these dachten, those kamen, those sahen, those nahmen, those fanden, those dachten, who kam, who sah, who nahm, who fand, who dachte, who kamen, who fanden, which kam, which sah, which nahm, which fand, which dachte, which kamen, which sahen, which nahmen, which fanden, which dachten, que kam, que sah, que nahm, que fand, que dachte, que kamen, que sahen, que nahmen, que fanden, que dachten
- que 関係詞（判定は That …）: que denkt, que kam, que sah, que nahm, que fand, que dachte, que kamen, que sahen, que nahmen, que fanden, que dachten
`scripts/tense_matrix.py` に個別の `ROUNDTRIP_REVERSED` を追加して再生成。nl/homograph ゲート後に prefer_on_tie 勝者がリバース対象ならセルを空にして英語のまま（次点昇格なし）。負け候補としてだけ含まれる場合は当該形のみ落とし、他言語の origin/main 勝者は維持。`ROUNDTRIP_ENFORCED_LANGS` は `{nl}` のまま広げていない。

#### zh_de_phrases（3形）→ `examples_not_registered`

- Tankstelle（filling station → 判定 Gas station）
- Parkplatz（parking place → 判定 Parking lot）
- wenn（if and when → 判定 If）

zh エントリ 62 件は無変更。

#### es_fr_tense（1形 fand）→ `examples_not_registered`

共有面 `fand` は tense_matrix 側の first entry（I have found）で 0/9。es_fr の `I found` → fand も同じ面のため除外。他候補（encontré / achei / vond）は昇格させていない（英語のまま）。

失敗53形の記録は `roundtrip.json` に証拠として残した。

## 方法・provenance

変換後255文（85形×3テンプレート）を、変換文だけを見て復元し `roundtrip_judge/de_blind.json` に記録した。
既存 `scripts/roundtrip_replay.py de` を `scripts/roundtrip.py` の `run(data, cmd, only_lang="de", entries=...)` に渡し、first-entry-per-form（tense_matrix → zh_de_phrases → es_fr_tense の順）で採点した。件数は run() が数え、手編集していない。
各 cohort に `judge_provenance` を付けた。

**開示（#169 同種）**: 判定者は Grok Bot（本任務と同じアシスタント）であり、TalkCompress 作業もしているため完全なブラインド評価ではない。回答は変換文からの通常英語復元であり、登録ソースへの一致を狙って書き換えていない。

**replay の注意**: replay は決定的で、全 seed に同じ回答を返す。各形9件は3件の独立回答の再利用であり、seed ごとの独立した AI 推論ではない。

**共有面**: 同一変換文を生む複数エントリ（例: kam の past/perf × he/she/it）は形単位で、bank 順の最初のエントリだけを run() に渡した（#168 と同じ）。

## AI 可読性（必須）

独立判定は255文すべてに復元を返した。norm 後に公式の期待英語（first entry）と一致したのは 96/255 文
（形単位で 32形が 3/3、53形が 0/3）。この3テンプレート以外の自由文での可読性は **未測定**。
公式往復（norm-nfc-v1）そのものが本タスクの可読性証拠であり、上記レートを可読性指標とする。

## 範囲

既存 `required` は [] のまま、往復ゲートの強制は有効化していない。Issue #29 本文、C 層 in favor of→pro、
他言語の勝者、#153 #154 #157 #161–#170 のブランチは変更していない。
共有の `roundtrip.json` / `tense_matrix.*` / `zh_de_phrases.json` / `es_fr_tense.json` は他言語 PR（とくに #169）と競合しうる。

## テスト

`uv run pytest` の結果は PR 本文に記載。`uv run python scripts/tense_matrix.py --check` と `git diff --check` も実施。
