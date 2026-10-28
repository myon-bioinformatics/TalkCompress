# TODO

- **D (DensityZip):** 決定名（2026-10-27）。旧仮名 DispatchHub から改称。横断オーケストレーション + density 指標ファサード（Hub は使わない）。合意台帳は C / ShorthandEdge が所有。Zipilogue (A) / MorphoZip (E) と名前を混同しない。

- **D pytest ≈ 0:** DensityZip 専用スイートは持たない。層単体は `tests/test_*.py`（A–E）、またぎは `tests/integration/`（結合・総合）。同一ケースの二重断言は層単体 1 箇所＋integration に揃える。`DensityZip/tests/` は README のみ。

- **B live MT:** `--translate-engine=deep` needs `uv sync --group translate` (`deep-translator`). `argos` is documented but not in the default lock (heavy packs).

- **A Zipilogue 実験方針（2026-10-27）:** 軽量ローカルモデル（**llama.cpp または同等の軽量 GGUF** スタック；同クラス。既定では重いフル精度サーバは使わない）で継続会話を回し、間隔をおいてエージェントが独自の共有表現・スラング（RuleBook 成長）を発明するかを観察する。二者だけの脆い構成より、**複数エージェントを並列のグループ**として回す方を優先。実装（ランナー等）は未着手・方針メモのみ。


- [ ] E 前置詞 for→`4`: 数字 four との揺らぎを在庫ビットとは別に評価。`for` へ戻すか検討（現状 `4`）。

- [x] E 助動詞・副詞 × **not / 肯定**: 否定 `!can/!will/!must/!may`・`don't/not→!`・`never→¬`；肯定は素形；極性1bit（`polarity_bit_cost`）。時制の深い畳み込みは残 TODO。I'll は C。
- [x] E 助詞 particle: コア ∅|→|∈|〜（2bit）。拡張 +|&|←（から=from スロット；fr は別名・for-real 揺らぎ）。と=& OK。
- [x] E from canonical: `←`（`fr` 別名のみ）。ML prep/pronoun エイリアス（ES/FR/DE、bits+tokenize 同スロット）。
- [ ] E 助動詞・時制: 過去/完了と極性の深い相互作用は未着手。
- [x] B 短時制 densifier 拡張（going-to ガード + live Romance/pt/el 候補 + FINAL_TENSE_LANGS）。 古典ラテン活用は見送り；存続ラテン略語は C。複合フレーズバンク成長は別スライス可。
- [x] B sibling pt/el/living-la（`pt_el_latin_phrases.json` + `pt_el_latin_tense.json`）: ZH/DE・ES/FR を書き換えず cheapest に加算。国限定略語/意味落ちは examples_not_registered。
- [ ] E because 表記: `bc` 採用（cuz 否定せず）。点々／数学記号寄りの型が後から載る可能性。
- [ ] E prep2: of→de / without→无 / within→内 / before→前 / after→後。pack1 と分離（3bit）。C 前後・内外ペアと役割分担を観察。
- [x] C 台帳 dual metrics: lex に token（B estimate_tokens）+ bit（E utf8_bits / inventory）を必須記録。候補絞り用。
- [x] B 最終トークン削減（`B-final-token`=`B-final-zh-de`）: phrase candidate bank（複合形・ZH densifier・EN acronym を cheapest）/ ES/FR 短時制 + zh|de 文 minify。`--final-token`/`--final-zh-de` / `--auto` 末尾；fixtures `zh_de_phrases.json` + `es_fr_tense.json`。監査汎用化: however→tho 譲歩ゲート、fui 曖昧さ、死んだ je vais 削除、family=spatial。
- [x] C 台帳: **ビット変化ゼロ**（utf8/primary bit delta=0）の lex を削除。token のみ改善は残さない（私たち→we 等の縮む行は維持）。
- [x] C 台帳: 100件予算で見送った brb/AFAIK/whereas 等を、ゼロビット剪定後に追加（utf8 縮む分のみ・≤100）。
