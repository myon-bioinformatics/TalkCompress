# イタリア語（it）採用形の独立ブラインド往復確認（2026-11-08 JST）

## 対象

main `84e5dca0028d90db73254af33ac2d9d3ce545790` の it 採用 winner を公式データから数え直した。
`tense_matrix.build()` の it 40エントリ・30形と、`pt_el_latin_phrases.json` の `ciao`（see you soon）1形で、
計 **41エントリ・31ユニーク形**。開始時点で `it:*` の往復記録は0件だった。

it は `ge100m_langs` に含まれるため閾値は restore rate ≥ 0.6（lt100m の 0.9 ではない）。
min_trials 9、seeds [1, 2, 3]、テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`。
trials > 0 で rate 0（status `never`）は全言語共通で不可。採点は既存 `norm()`（norm-nfc-v1）。

## 結果（31形中 28形通過・3形リバース）

| 形 | 出典 | 復元 / 完了 | 判定 |
|---|---|---|---|
| avrò dato, sto dando, starò pensando, starò dando | tense_matrix | 各 9/9 | pass |
| trovi, dici, sai, vorrai | tense_matrix | 各 9/9 | pass |
| dai（you give） | tense_matrix | 6/9（0.667） | pass（`Dai.` → `Come on.` の3件が不一致） |
| stavi facendo, stavi pensando, stavi dando | tense_matrix | 各 9/9 | pass |
| starai facendo, starai pensando, starai dando | tense_matrix | 各 9/9 | pass |
| sa, dà, avrà dato, sta pensando, sta dando（he/she/it 共有） | tense_matrix | 各 9/9 | pass（下記ルール） |
| vorremo, avremo dato, stavamo dando | tense_matrix | 各 9/9 | pass |
| this avrà dato, who sa, who dà, which sa, which dà | tense_matrix | 各 9/9 | pass |
| **que sa**（que knows） | tense_matrix | **0/9** | never → リバース（判定は `That knows`） |
| **que dà**（que gives） | tense_matrix | **0/9** | never → リバース（判定は `That gives`） |
| **ciao**（see you soon） | pt_el_latin_phrases | **0/9** | never → リバース（判定は `Hello`） |

## リバース

- `que sa` / `que dà`: 生成 JSON は手編集せず、`scripts/tense_matrix.py` に個別の
  `ROUNDTRIP_REVERSED = {("it","que sa"), ("it","que dà")}` を追加して再生成した。
  言語単位の強制（`ROUNDTRIP_ENFORCED_LANGS`）ではなく、it の他の形は report-only のまま。
  リバース対象を候補に含むセル（mx-know-pres-rel-que-sg / mx-give-pres-rel-que-sg）は候補を空にして英語のまま残し
  （`cell["roundtrip_reversed"]` に記録）、次点の他言語候補（es que sabe / de que gibt）は昇格させない。
  これにより es / de を含む他言語の winner は origin/main と同一のまま。新しい候補は追加していない。
- `ciao`: #164（ギリシャ語 πάλι）と同じく `pt_el_latin_phrases.json` の entries から外し、
  `examples_not_registered` に理由付きで移した。他候補（pt até / el γεια）は昇格させていない（英語 see you soon のまま）。
- 失敗3形の記録は `roundtrip.json` に証拠として残した。

## 方法・provenance

変換後93文（31形×3テンプレート）を、リポジトリ・元英語・担当指示の注釈にアクセスしない
独立判定エージェントが変換文だけを見て復元し、親エージェント経由で受領した。回答は無修正で
`roundtrip_judge/it_blind.json`（変換文→復元文）に記録し、既存 `scripts/roundtrip_replay.py it` を
`scripts/roundtrip.py` の `run(data, cmd, only_lang="it", entries=...)` に渡して採点した。件数は run() が数え、手編集していない。
各 cohort に `judge_provenance`（kind: independent_blind_judge）を付けた。

**replay の注意**: replay は決定的で、全 seed に同じ回答を返す。各形9件（3テンプレート×3 seed）は
3件の独立回答の再利用であり、seed ごとの独立した AI 推論ではない。

**ciao**: CLI の `--lang it` は `tense_matrix.build()` しか列挙しないため、#163 の nl 追加形と同様に
`pt_el_latin_phrases.json` の entry を `entries=` で明示的に渡した。

**he/she/it 共有形のルール**: `sa` / `dà` / `avrà dato` / `sta pensando` / `sta dando` は he/she/it の3エントリが
同じ変換文を生む。記録キーは `lang:form` 単位で、検証単位は形。判定は `he` を選んだ。
同一変換文に対し、その文の公式な受理元英語（he/she/it のいずれか）に一致すれば一致とするルールを採用し、
実装としては各形の bank 順で最初のエントリ（he）1件の対象を run() に渡した（回答は書き換えていない）。
参考: エントリごとに厳密に数えると各形 9/27（she/it は同一文なので原理的に区別不能）。

## AI 可読性（必須）

独立判定は93文すべてに復元を返した。norm 後に公式の期待英語と一致したのは 81/93 文
（形単位で 27形が3/3、dai が2/3、que sa・que dà・ciao が0/3）。共有形は he を受理元として数えた。
この3テンプレート以外の自由文での可読性は **未測定**。

## 範囲

既存 `required` は [] のまま、往復ゲートの強制は有効化していない。Issue #29 本文、C 層 in favor of→pro、
他言語の勝者データ・記録、#153 #154 #157 #161–#165 のブランチは変更していない。
共有の `roundtrip.json` は他言語 PR と競合しうるので、マージ時は it の cohort を保持して解消すること。

## テスト

`uv run pytest`: **5903 passed, 5 skipped, 1 xfailed**（新規 `tests/test_it_roundtrip_gate.py` 6件を含む）。
`uv run python scripts/tense_matrix.py --check` と `git diff --check` も成功。セル削減に合わせ `scripts/tokenizer_compat.py --compat` で docs/tokenizer_compat.{json,md} を再生成（2セル減のみ）。
