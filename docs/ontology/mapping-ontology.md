# 対応表オントロジーとナレッジグラフ試作（読み取り専用）

TesseraTalk の対応表（英語 → 短い他言語形）について、**概念と関係の意味（オントロジー）** を定め、
いまのデータからその意味に沿って **具体的な知識をつないだグラフ（ナレッジグラフ）** を組み立てる。

- 実装: `scripts/mapping_graph.py`（標準ライブラリのみ。tiktoken も tense_matrix の import も不要）
- テスト: `tests/test_mapping_graph.py`
- **これはモデルと読み取り専用ツールであり、移行ではない。** 採用・リバース・往復ゲートの挙動は一切変えない。
  既存の設定（`ROUNDTRIP_*`）と生成物（`tense_matrix.json` / `tense_matrix_report.json` / `roundtrip.json`）を
  読むだけで、どのファイルにも書き込まない。

## 1. クラス（概念）

| クラス | 日本語 | 安定 ID | 主な属性 |
|---|---|---|---|
| `Language` | 言語 | `lang:<code>` | `ge100m`、`roundtrip_enforced`、`reversal_strategy` |
| `EnglishSource` | 元の英語 | `en:<小文字・空白正規化した英語>` | `text` |
| `Form` | 形（言語つき表記） | `form:<lang>:<form>` | `status`（下記） |
| `Adoption` | 採用形（ある英語に対して採用された形） | `adopt:<lang>:<form>:<英語>` | `bank`、`entry_id`、`meaning`、`en_kept` |
| `Candidate` | 候補 | `cand:<lang>:<form>:<英語>` | `origin`（バンク#id / report）、`not_registered`、`gated` |
| `RoundtripRecord` | 往復記録 | `rt:<lang>:<form>:<run_id>`（v4 以前は `:legacy`） | `evaluator`、`measured_at_main`、`timestamp`、`completed`、`restored`、`latest` |
| `ReversalDecision` | 外した理由 | `rev:<lang>:<form>` / `revsrc:<英語>` | `strategy`、`setting` |
| `ParityFollow` | 数一致追従 | `parity:<subject>:<tense>:<verb>` | `follower_form`、`base_form`、`base_reversed` |

ID の考え方:

- **形の同一性は「言語＋表記」**。`form:pt:foi` と `form:es:fui` は別物、`form:el:tomaré` と `form:es:tomaré` も別物。
  これは `roundtrip.json` のキー `lang:form` と同じ粒度で、往復記録がそのまま形に結びつく。
- **採用は「言語＋表記＋元の英語」**。同じ `foi` でも `he went` と `she went` は別の採用（同じ形を共有）。
  ciao の再混入のような事故は「どの英語に対して、どの言語の形として」入ったかで識別できる。
- 英語は小文字化・空白正規化だけ行う（縮約形の展開はしない。`from` の 2 番目以降は `alsoReplaces`）。

### Status（形の状態）

| 値 | 意味 | 由来 |
|---|---|---|
| `pass` | 最新コホートが閾値以上（ge100m 0.6 / lt100m 0.9） | `roundtrip.status()` |
| `fail` | 試行は足りているが閾値未満 | `roundtrip.status()` |
| `never` | 復元率 0 | `roundtrip.status()` |
| `unverified` | 記録はあるが試行不足・不完全なコホート | `roundtrip.status()` |
| `untested` | **記録そのものが無い**（未測定） | グラフ側で付与 |
| `not_applicable` | 英語のまま（`lang: en`）など往復の対象外 | グラフ側で付与 |

**「記録が無い」は「失敗」ではない。** `untested` は通過でも失敗でもない第三の状態として持ち、
`never` / `fail` と混ぜて数えない。判定は `scripts/roundtrip.py` の `status()` をそのまま使い、
グラフ側で閾値を再実装しない。

## 2. 関係（向きを固定）

主語 → 述語 → 目的語。向きは常に「具体的なもの → 参照先」。

| 主語 | 述語 | 目的語 | 意味 |
|---|---|---|---|
| Form | `inLanguage` | Language | この形はこの言語の形 |
| Adoption | `usesForm` | Form | この採用はこの形を使う |
| Adoption | `replaces` | EnglishSource | この採用はこの英語（`from[0]`）を置き換える |
| Adoption | `alsoReplaces` | EnglishSource | `from` の別表記 |
| Candidate | `proposesForm` | Form | この候補はこの形 |
| Candidate | `forSource` | EnglishSource | この候補はこの英語に対するもの |
| Candidate | `rejectedBy` | ReversalDecision | この候補は往復失敗で外された |
| RoundtripRecord | `verifies` | Form | この往復記録はこの形を検証した |
| ReversalDecision | `reverses` | Form | この判断はこの形を外した |
| ReversalDecision | `basedOn` | RoundtripRecord | 外した根拠の往復記録 |
| ReversalDecision | `keepsEnglish` | EnglishSource | この英語は次点に昇格させず英語のまま |
| ParityFollow | `follower` | EnglishSource | 追従する側のセル（this / these / those） |
| ParityFollow | `followsVerbOf` | Form | 追従元（数の一致する代名詞の勝者動詞） |
| ParityFollow | `derivesForm` | Form | 追従の結果採用された形（採用時のみ） |

## 3. いまの散らばった設定との対応

| 現在の設定 / データ | オントロジー上の表現 |
|---|---|
| `ROUNDTRIP_REVERSED`（言語横断の和集合 `(lang, form)`） | `ReversalDecision rev:<lang>:<form>`（`setting=ROUNDTRIP_REVERSED`）`reverses` Form。`strategy` は言語の外し方で決まる |
| `ROUNDTRIP_REVERSED_SOURCES` | `ReversalDecision revsrc:<英語>`（`strategy=source_keeps_english`）`keepsEnglish` EnglishSource |
| `ROUNDTRIP_REVERSED_ANY_CANDIDATE_LANGS = {it}` | Language の `reversal_strategy = any_candidate_empties_cell`（候補に出ただけでセルを空にする, #168） |
| `ROUNDTRIP_REVERSED_DROP_CANDIDATE_LANGS = {es}` | `reversal_strategy = drop_candidate_before_ranking`（順位付け前に候補だけ落とす, #172） |
| de の tie-winner 設定 `ROUNDTRIP_REVERSED_TIE_WINNER_LANGS = {de}`（#174、このベースには未導入） | `reversal_strategy = tie_winner_empties_else_drop`（英語に勝つ反転勝者ならセルを空に、そうでなければ反転候補だけ落とす）。定数があれば自動で読む |
| それ以外（pt・fr など） | `reversal_strategy = adopted_winner_only`（採用勝者のみ外す, #171 / #173） |
| `examples_not_registered[].roundtrip_reversed` | `ReversalDecision`（`strategy=fixture_not_registered`）＋ `Candidate.rejectedBy` |
| `roundtrip.json` の `records[*].cohorts` | コホートごとに 1 つの `RoundtripRecord`。`latest=True` が判定対象（v4 会計） |
| `roundtrip.json` の `run_history[*].judge_provenance` | `evaluator`（例 `independent_blind_judge`、無ければ `cmd:<command_sha256 先頭12桁>`）と `measured_at_main`（`origin_main_sha`） |
| `ROUNDTRIP_ENFORCED_LANGS = {nl}` | Language の `roundtrip_enforced=True`。nl の `roundtrip_gated` 候補は `Candidate(gated=True)` |
| `required: []` | 変更なし（グラフは強制しない） |
| `tense_matrix_report.json` の `parity_verb` | `ParityFollow`（`followsVerbOf` で追従元の Form へ） |

設定の **意味** は 1 つ（「この形をこの英語に使わない」）で、違いは **適用の仕方（strategy）** だけ、という整理になる。
今日 #173 に一本化した際に継ぎ合わせが難所だったのは、この strategy が言語ごとの別定数として書かれていたため。

## 4. 推論の 3 種類を分ける

| 種類 | TalkCompress での例 | 実行方法 | グラフでの扱い |
|---|---|---|---|
| グラフ探索 | 数一致追従（`this` は 3sg 代名詞の勝者動詞を主語付きで再利用）、ある英語の全言語候補 | 辺をたどるだけ | `--parity-reversed`、`--source` |
| 論理推論 | 「Form が reverses されている ⇒ その Form を usesForm する Adoption は残ってはいけない」 | 定義から機械的に導く | `--check` の `reversed_still_adopted` |
| LLM による判断 | 往復で AI が英語に戻せたか（AI 可読性） | 独立ブラインド判定・`--run --cmd` | `RoundtripRecord` として **事実の記録** だけ持つ。グラフが推測で埋めることはしない |

追従は機械的に導けるが、**追従先の形が AI に読めるかは往復で確かめるまで事実ではない**。
例: `this virá` は数一致追従で採用されているが、追従元 `virá` は pt で reversed（#171）。
グラフはこれを「追従元が外された追従」として列挙するだけで、外すかどうかの判断はしない（挙動を変えない）。

依存と因果も同じで、「追従元が失敗した ⇒ 追従先も読めない」とは断定しない。調査対象を絞るのに使う。

## 5. 時点と根拠

`RoundtripRecord` には `evaluator`・`measured_at_main`・`timestamp` を持たせる設計にしたが、
現在のデータで埋まるのは次のとおり（`--check` が数える）:

- `measured_at_main`: `judge_provenance.origin_main_sha` を持つ pt の run だけ。他は未記録。
- `timestamp`: どの run にも無い（全件未記録）。
- `evaluator`: v4 コホートはコマンド digest か judge 種別、legacy（nl）は不明。

測定後に形が変わったか（測った main と今の main の差）を機械的に検出するには、今後の往復 run で
`origin_main_sha` と時刻を記録するのが前提になる（本 PR ではデータを変えない）。

## 6. ツール

```
uv run python scripts/mapping_graph.py --check                  # 言語別 status 件数・整合性
uv run python scripts/mapping_graph.py --untested --lang de     # 記録の無い採用形
uv run python scripts/mapping_graph.py --source "I will take"   # 一つの英語に対する全言語の採用・候補と status
uv run python scripts/mapping_graph.py --parity-reversed        # 追従元が reversed の数一致追従
uv run python scripts/mapping_graph.py --collisions             # 同じ形の他言語・他の意味
uv run python scripts/mapping_graph.py --node form:pt:foi       # 1 ノードと辺
```

`--collisions` の分類:

- `cross_language`: 同じ表記が複数言語の採用形として登録されている（「既に他言語・他の意味で登録された形は採らない」規則の監査）。
- `lang_label_mismatch`: 採用行の `lang` と、同じ行の候補リストで同じ表記に付いた言語が食い違う。
- `multi_meaning`: 同じ `lang:form` が別の動詞（意味）にも採用されている。
- `tense_merge`: 同じ動詞の別時制に同じ形（例: 過去形を現在完了にも使う）。情報のみ。

`--check` が非 0 で終わるのは、グラフ自体が矛盾する場合（同じ ID が別クラス、行き先の無い辺）だけ。
未測定や衝突は報告するが失敗にはしない。

## 7. このベース（#173, `fix/fr-roundtrip-20261109`）での実行結果

採用形（`lang:form` の一意数、英語据え置き行を除く）の status:

| lang | pass | fail | never | unverified | untested | not_applicable |
|---|---|---|---|---|---|---|
| cs | 0 | 0 | 0 | 0 | 8 | 0 |
| de | 0 | 0 | 0 | 0 | 85 | 0 |
| el | 0 | 0 | 0 | 0 | 4 | 0 |
| en | 0 | 0 | 0 | 0 | 0 | 4 |
| es | 100 | 0 | 0 | 0 | 0 | 0 |
| fr | 93 | 0 | 0 | 0 | 0 | 0 |
| it | 28 | 0 | 0 | 0 | 0 | 0 |
| la | 0 | 0 | 0 | 0 | 9 | 0 |
| nl | 8 | 0 | 0 | 0 | 6 | 0 |
| pl | 0 | 0 | 0 | 0 | 2 | 0 |
| pt | 210 | 0 | 0 | 0 | 0 | 0 |
| zh | 37 | 0 | 0 | 0 | 0 | 0 |

- reversed なのに採用に残っている形: 0 件。
- 追従元が reversed の数一致追従: 22 件（うち採用のまま 1 件: `this virá`）。
- `lang_label_mismatch`: 3 件（`es_fr_tense` の `take-fut-1s` / `take-fut-goingto-1s` は `tomaré` が `lang: el`、
  `leave-fut-goingto-1s` は `vou sair` が `lang: es`）。データは直していない（別 PR で判断）。
- de（#174）、nl 6 形（#163）、cs/pl（#165）、el（#164）、la（#161）はこのベースでは未測定として出る。
  #161/#164 の `logo`・`por isso`・`acharei`（pt）、`tomaré`（es）は、このベースでは **採用形ではなく候補** として
  存在し、いずれも `untested`。
