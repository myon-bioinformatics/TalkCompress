# スペイン語（es）採用形の独立ブラインド往復確認（2026-11-09 JST / Asia/Tokyo）

## 対象

main `cdb895387170d42990ebf93573a307959b92c148` の es 採用 winner を公式データから数え直した。
`tense_matrix.build()` の es **128エントリ** と、`es_fr_tense.json` の es **40エントリ**（うち surface 重複 2形 `fui` / `dije`）で、
計 **168エントリ・129ユニーク形**。開始時点で `es:*` の往復記録は0件、`required` に es は無し。

es は `ge100m_langs` に含まれるため閾値は restore rate ≥ 0.6（lt100m の 0.9 ではない）。
min_trials 9、seeds [1, 2, 3]、テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`。
trials > 0 で rate 0（status `never`）は全言語共通で不可。採点は既存 `norm()`（norm-nfc-v1）。

## 結果（129形中 105形通過・24形リバース）

通過105形はすべて 9/9（rate 1.0）。閾値ぎりぎり（例: it `dai` 6/9）の形は無し。

### リバース（24形・いずれも 0/9 never）

**tense_matrix（21形 / 26エントリ）** — `scripts/tense_matrix.py` の `ROUNDTRIP_REVERSED` + `ROUNDTRIP_REVERSED_SOURCES` で再生成し、対象セルは英語のまま残した（次点言語は昇格させない）。

| 形 | 主なソース | 判定の復元例 |
|---|---|---|
| viste / dijiste | you have seen / said | you saw / you said |
| hizo / dijo（he/she/it 共有） | he has done / said | he did / he said |
| pensamos（past+perf 共有） | we thought / have thought | we think |
| this/these/those + hizo/dijo/dijeron | demonstrative perfect | this/these/those did/said |
| who/which + hizo/dijo/dijeron | relative perfect | who/which did/said |
| que va / ve / toma / hizo / dijo / dan / dijeron | que … | that …（公式ソースは que …） |

**es_fr_tense（3形）** — 短形を `examples_not_registered` に理由付きで移し、entries 側は英語同一性（`to` = `from[0]`）に替えて既存ソースを維持（tense_matrix が埋めないようにする）。他言語候補は昇格させていない。

| 形 | ソース | 判定の復元例 |
|---|---|---|
| vamos | we will go | we go |
| fue | she went（from に he went も含む） | he went |
| pude | I could | I was able to |

失敗24形の記録は `roundtrip.json` に証拠として残した。

## リバース後のバンク

- tense_matrix es: 128 → **102** エントリ（21ユニーク形 / 26エントリ減）
- es_fr_tense es: 40エントリのまま（短形3を英語同一性に置換 + `examples_not_registered` に短形を記録）
- 採用ユニーク形: **108**（短形100 + 英語同一性8。後者は従来の `I will want` 等5形に今回3形を加えたもの）
- winner-check vs origin/main: **es はリバース形のみ減・新規採用なし。他言語（cs/de/fr/it/nl/pl/pt）は entry id・形とも完全一致。**

## 方法・provenance

変換後387文（129形×3テンプレート）を、リポジトリ・元英語・担当指示の注釈にアクセスしない
独立判定エージェントが変換文だけを見て復元し、親エージェント経由で受領した。回答は無修正で
`roundtrip_judge/es_blind.json`（変換文→復元文）に記録し、既存 `scripts/roundtrip_replay.py es` を
`scripts/roundtrip.py` の `run(data, cmd, only_lang="es", entries=...)` に渡して採点した。件数は run() が数え、手編集していない。
各 cohort に `judge_provenance`（kind: independent_blind_judge）を付けた。

**replay の注意**: replay は決定的で、全 seed に同じ回答を返す。各形9件（3テンプレート×3 seed）は
3件の独立回答の再利用であり、seed ごとの独立した AI 推論ではない。

**es_fr_tense 追加形**: CLI の `--lang es` は `tense_matrix.build()` しか列挙しないため、#163 の nl 追加形・#168 の ciao と同様に
`es_fr_tense.json` の entry を `entries=` で明示的に渡した。

**共有 surface のルール**: `va` / `hizo` / `fui` 等、複数エントリが同じ変換文を生む形は記録キー `lang:form` 単位で検証する。
判定復元が、その変換文の公式受理元英語（`from` / he/she/it / past↔perfect の別エントリ）のいずれかと
norm 一致すれば一致とする。実装は、全テンプレートで判定と一致する最初のエントリを代表として `run()` に渡した
（回答は書き換えていない。エントリごとに厳密に数えると共有形は過少計上になる）。

**ROUNDTRIP_REVERSED のセル空化**: #168 と同様、リバース形を候補に含むセルで「origin/main 上その英語ソースの勝者がリバース対象」なら候補を空にして英語のまま残す。
bare 形（hizo 等）が他言語セルの非勝者候補にだけ載っている場合は、その候補だけ落として他言語 winner は維持する
（空セル化しすぎると de/fr/pt が変わるため。`ROUNDTRIP_REVERSED_SOURCES` で対象ソースを固定）。

言語単位の強制（`ROUNDTRIP_ENFORCED_LANGS`）には es を加えていない（引き続き `{nl}` のみ）。

## AI 可読性（必須）

独立判定は387文すべてに復元を返した。norm-nfc-v1 後に公式の期待英語（キーの `expected_norm` / 受理元のいずれか）と一致したのは **315/387** 文。
共有形は上記 any-accepted-source ルールで数えた。この3テンプレート以外の自由文での可読性は **未測定**。

## 範囲

既存 `required` は [] のまま、往復ゲートの強制は有効化していない。Issue #29 本文、C 層 in favor of→pro、
他言語の勝者データ・記録、#153 #154 #157 #161–#170 のブランチは変更していない。
共有の `roundtrip.json` / `tense_matrix.*` / `es_fr_tense.json` は他言語 PR と競合しうるので、マージ時は es の cohort とリバースを保持して解消すること。

## テスト

`uv run pytest` と `uv run python scripts/tense_matrix.py --check`、`git diff --check` を実施（結果は PR 本文に記載）。
セル削減に合わせ `scripts/tokenizer_compat.py --compat` で docs/tokenizer_compat.{json,md} を再生成。
