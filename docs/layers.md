# 層とサブプロジェクトの対応

詳細はルート README と [subprojects.md](subprojects.md) を参照。

| 層 | サブプロジェクト |
| --- | --- |
| 1 機械同士 | Zipilogue (A) |
| 2 文単位多言語 | TesseraTalk (B) — LID/RLE モザイク + **翻訳トークン最短**（並列多言語→短さ＋揺らぎ。Romance/Germanic/Greek + JA/ZH・自然短形。C 台帳は使わない）+ **最終トークン削減**（複合形/ZH densifier・ES/FR 短時制・zh\|de 文 minify） |
| 3 人間ギリギリ | ShorthandEdge (C) |
| 4 文内・文法最小 | MorphoZip (E) |
| 横断 + density | DensityZip (D) |

### Zip 名の区別

単独の「Zip」は使わない。常にフルネーム:

| ID | フルネーム | 役割 |
| --- | --- | --- |
| A | **Zipilogue** | 層1 — 共有ルール / 任意封筒（density ではない） |
| D | **DensityZip** | 横断 — density 指標ファサード + 層オーケストレーション |
| E | **MorphoZip** | 層4 — 形態・閉じた品詞在庫ビット・文法最小 |

**E 原則（言語非依存の最短形）:** ソース言語を問わず意味が通る最短表層へ畳む（記号 OK）。比較 ≧≦≒= はその一例であり、特定言語（ES/DE/FR）だけの特例ではない。代名詞・前置・接続なども同原則。

JUnit は CI で `build/test-results/pytest-<ver>.xml` に置き、artifact 名は `junit-py*` です（Aoi / ascii_artist と同系）。

語彙ヘルパーは `shared/lex_policy.py`。合意済み規約の台帳は **C** の `ShorthandEdge/ledger/conventions.json`（読込は `shared/ledger.py`）。担当は:

- **B**: LID/RLE モザイク。文ごとに翻訳候補（fixtures）でトークンが減るなら採用。EN+ZH+JA は開始セットであり天井ではない（Romance es/fr/pt/it、Germanic de/nl/en、Greek el、ja/zh がスコープ）。自然短形 OK。ライブ MT（`--translate-engine=deep|argos`）は対象言語へ並列翻訳し、短さ＋揺らぎで選ぶ。C 合意台帳パッチは適用しない。**`estimate_tokens` / translate-min の本体**。**最終トークン削減**（`final_token_pass` / 別名 `final_zh_de_token_pass`；`--final-token` / `--final-zh-de`；D では `B-final-token`=`B-final-zh-de`）: A–E の後に cheapest-token 候補を適用 — **複合形**（名詞+名詞・形容詞+名詞など、トークンが減るとき自由に採用；複合名詞はラベルであり名詞限定ポリシーではない；DE/nl 複合1語化を含む）、**ZH densifier**、**短時制活用**（live Romance es/fr/pt + nl/el；go/come/do/be/have/must/want/see/take/think/try/find/…；`es_fr_tense.json`；progressive *going は `to` 後続で抑制＝going-to ガード；古典ラテン活用は見送り）、フレーズ候補に JA densifier（`なる早` 等）も載せ得る（`FINAL_PHRASE_LANGS`=zh|de|en|ja|nl）；ASAP 等 EN 頭字語が cheapest で勝つ。phrase bank は token+utf8_bits 両縮小の候補を優先。文単位 minify は `zh|de` に制限。EN 複数パラフレーズは `select_cheapest`（token→utf8）で先に1つに絞り、横断言語より EN-first。時制の EN 縮約（I'll 等）は C 側。トークン+utf8 両方縮小を優先；token-only 勝ちは辞書的に明確な形のみ
- **C**: FILLER 除去・UNIQUE_COMPACT（短縮クリップ）・同一言語の省略（`I'll` など）・スペル数字→桁・**合意台帳 lex**（under/below→下、家具 `table`→机/桌 ほか多言語の机相当、デコボコ→凹凸 など）。ベース語彙は EN+ZH+JA 寄りだが他言語 cognate も可。接続詞短縮は **曖昧さゲート**（`also` 衝突時や `--prefer-precision` で原文維持）。**登録台帳の lex はトークン観点（B `estimate_tokens`）とビット観点（E `utf8_bits` / 適用時は `closed_inventory_bits`）の両方を `metrics` に必須記録。**内訳 `breakdown`** はフラット短形1文字列 — 品詞なら 代/示/助/前/…、否则 連/熟/俗/頭/略/↓T 等（長いENタグは共有短形へ；深い列は作らない）** — 両方揃って初めて候補絞りに使える（policy は省略可）。 **`family=abbrev` は C 一層**: 縮約（`c-ill` / `I will`→`I'll` は `apply_en_contractions`・台帳は `ledger_apply=false` の登録）、チャット頭字語（`c-asap`…）、ラテン短形（`e.g.`/`etc.`/`vs`/`i.e.`）。極性は C の `don't`/`can't` のあと E が `!` / `!can` に畳み得る（`C,E`）。 **`family=emoji` も C 一層**: 語→絵文字（ファイア→🔥、heart/ハート→♡ など `EMOJI_SPEC`；`ledger_apply=true`；dual metrics・utf8 縮必須）。**多言語経路は ML 別名→pivot（既定 EN；JA 可）→絵文字**（台帳に `pivot`/`pivot_lang`；二段適用）。**短形優先**: 意味がはっきり載るなら **数学/記号優先**（≧≦←→∴∵& ✓★≠∞ 等）、否則絵文字 — 両方効くなら既存記号を選び絵文字ピアを増やさない（check→✓ not ✅）。**言語横断 cheapest**: 意味が通る候補から token（B）→utf8 bit（E）が最も楽な表層を選ぶ（`select_cheapest_form` / `policy-cross-lang-cheapest`）。`family=symbol` は E 閉じた品詞以外の開いた数学記号（≠∞±…）。**`family=spatial`**: 空間・サイズ対（↑↓ / under→下 / 左右 / 凹凸 等）。**`family=ever`**: 5W1H 譲歩 multiword→`-ever`（no matter how→however / what→whatever / which→whichever / where→wherever / when→whenever / who→whoever；however は逆接「しかし」ゲートで複数語の譲歩句のみ；whyever 見送り；cognate は cheapest+utf8 縮のときだけ）。E 閉じた品詞在庫の写像も **登録記録**として同台帳に `apply_layer=E` + `inventory` + dual metrics で載せる（書換エンジン所有は E のまま；C の `apply_ledger_lex` は C 行のみ）
- **E**: UNIQUE_READINGS（長い形）・ETYMON_ALIGN（comm/cfg/doc 等；information→ℹ️ は C emoji）・助数詞・**閉じた品詞在庫（ビット主）**: 代名詞 case-split+独立所有格 I/my/me/mine…U/your/you/yours…he/his/him…she/her/hers…it/its（neuter=事物）…they/their/them/theirs+y'all（N=26→5bit；表層 utf8+token 優先；she 開放；君/彼/彼女=入力別名；在庫ビット設計/レポート二次）／**指示代名詞 deixis** ça|eso|these|those|あれ（N=5→3bit；this/これ→ça・それ→eso；≠ it；関係詞 that 除外）／冠詞 ∅（the/a/an 落とし・0bit）／接続 &|/|bc|∴（2bit；because→bc；cuz は数学記号系優先で見送り可；moreover 等は C）／副詞 tho|~|˅|esp.（2bit；拡張 □/oft；not→! never→¬）／助動詞 can|will|must|may（2bit；I'll は C；否定 !can/!will/!must/!may・don't→!；肯定は素形）／極性 !|¬（在庫外 **1bit/マーカー**；助動詞・副詞共有）／前置 pack1 w/|4|←|@（2bit；from/から→←・fr は別名のみ for-real 揺らぎ；ML con/avec/mit 等；under/above は C；in/on 見送り；for→4 揺らぎ別評価）／前置 pack2 de|无|内|前|後（N=5→3bit；of→de without→无(w/o別名) within→内 before→前 after→後）／助詞 ∅|→|∈|〜（2bit；はがをねよさ→∅；にへ→→；で→∈；まで→〜；拡張 も→+ と→& から→←；と=& OK）／比較 ≧|≦（1bit；**言語非依存** — JA/ZH/EN/ES/FR/DE 等を同じ記号へ；≒/=；単独 under/below は C）。API: `closed_inventory_bits` / `closed_bit_cost` および各 `*_bit_cost`；`density().closed`。フィラー/compact/`I'll`/スペル数字/台帳 lex は既定オフ
- **D DensityZip**: 層横断オーケストレーション（pipeline / auto / budget / window / profile / quality / compare）+ **density 指標ファサード**（token 寄りは budget / compare / B `estimate_tokens` の表出、bit 寄りは E `density()` / `closed_bit_cost`（代名詞含む）の集約）。`C,E` パイプラインなら C が先にフィラー・I'll・スペル数字・台帳 lex を処理し、E が冠詞・助数詞・残 ETYMON を適用する（ℹ️ は C）。`--auto` / `--final-token`（=`--final-zh-de`）既定で末尾に `B-final-token`（=`B-final-zh-de`；B 最終トークン削減；`--no-final-token` でオフ）。台帳は持たない

**テスト分担:** D 専用 pytest は実質ゼロ。層単体 → `tests/test_*.py`；層またぎ（pipeline C→E・compare・budget/window/profile 等）→ `tests/integration/`（結合・総合）。`DensityZip/tests/` にテストモジュールは置かない。同一ケースの二重断言は避け、層単体は 1 箇所・またぎは integration に寄せる。

A の RuleBook（`Zipilogue/rulebook.py`）は機械同士で育つスラング台帳で、C の静的合意台帳とは別物。

**A Zipilogue 実験方針（2026-10-27）:** **llama.cpp または同等の軽量 GGUF** スタック（同クラス；既定では重いフル精度サーバは使わない）で継続会話を回し、間隔観察で共有スラング（RuleBook）が育つかを見る。二者固定より**複数エージェント並列グループ**を優先。ランナー実装は未着手（方針のみ）。

F は当面なし。
