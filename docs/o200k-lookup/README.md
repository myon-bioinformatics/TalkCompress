# o200k 実測ルックアップ（絵文字・特殊文字）

o200k 実測の参照用です。近似参照で、人間が通読する想定ではありません。表を足しただけで `☺` や `!👍` の経路差は直りません（estimate_tokens と `o200k_calib.json` はこの追加では変更していません）。

- 計測: tiktoken 0.14.0 / `o200k_base`、estimate は main `84e5dca`
- key（`s`）は正確な入力文字列。NFC/NFD・FE0E/FE0F・ZWJ・肌色・tag は統合していません。
- `emoji.jsonl`: Unicode emoji-test.txt 18.0（2026-04-30）全 5244 シーケンス（fully/minimally/unqualified/component）
- `specials.jsonl`: 絵文字以外の記号・制御・結合・全角・数学英数字・VS・Tag など 15098 件。3bot 測定 14374 件（単独 12087 + 結合列 2287）が主データ、別測定のみの 724 件を追加。不一致時は `alt`（今回 0 件）
- `cheap-symbols.jsonl`: 4bot 実測 40442 件（o200k 13491 / cl100k 9797 / p50k 8577 / r50k 8577）。1 token・英語 gloss より安い・o200k が cl100k より安い、のいずれかを満たす列。emoji-test 17.0 基準。pieces/hex は省略（`ids` から復元可）。意味保持は未検証
- `tokenizer-notes-4bot.md`: その結論（埋め込み生データは除去）。要点: BMP=1token や「見た目 1 文字=安い」は不成立。o200k の fully-qualified 1 token は 23 件、ZWJ を含む valid UTF-8 token は 4 encoding とも 0、複数 CP で 1 token は o200k の ❤️ のみ、地域旗 3 件（🏴󠁧󠁢󠁥󠁮󠁧󠁿 等）は o200k が cl100k より高い
- `probe-5bot.json`: pretoken 分類つきのサンプル測定、`design-5bot.md`: 設計メモ

各ファイルの 1 行目は `_meta`（出典・バージョン・キー説明）。以降 1 行 1 件、`o`=o200k、`e`=estimate、`d`=e-o、`b`=UTF-8 バイト数。

AI 可読性: 未測定
