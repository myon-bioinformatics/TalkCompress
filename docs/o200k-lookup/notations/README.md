# o200k 実測ルックアップ（顔文字・古記法）

o200k 実測の参照用です。近似参照で、人間が通読する想定ではありません。
`estimate_tokens` と `o200k_calib.json` はこの追加では変更していません。

これは取得できた公開ソースのスナップショットです。顔文字や独自符号は増やせるため、閉じた有限集合ではありません。Unicode 絵文字・特殊文字の表（`docs/o200k-lookup/` 直下）とは別ファイルです。

- 計測: tiktoken 0.14.0 / `o200k_base`、estimate は main `84e5dca`（TesseraTalk はその HEAD と差分なし）
- 大きい表は `.jsonl.gz` のまま置いてあります。展開例: `gzip -dc FILE.jsonl.gz`
- AI 可読性: 未測定。意味保持・復元成功も未測定です。
- Blissymbolics は公式 ID と英語 gloss の文字列を測ったもので、図形そのものの理解を測ったものではありません。

## 収録

| ファイル | 件数 | 内容 |
|---|---:|---|
| `kaomoji-ja-o200k.jsonl` | 37,515 | 日本の顔文字。許諾のある公開一覧から |
| `emoticons-ascii-o200k.jsonl` | 485 | 西洋・キリル圏の単行顔文字（Wikipedia / Wiktionary、CC BY-SA 4.0） |
| `kaomoji-i18n-o200k.jsonl` | 530 | 多言語のテキスト顔（bare 487 + 先頭空白 43） |
| `legacy-notations-o200k.jsonl` | 10,832 | 携帯絵文字・Wingdings / Webdings・shortcode・CLDR 注釈など |
| `self-kaomoji-notations-o200k.jsonl.gz` | 64,564 | CLDR 注釈名・gemoji shortcode・携帯 PUA・HTML 実体・X-SAMPA / IPA など。2bot / 3bot の主表は上書きせず、そこに無い分を追加 |
| `self-extra-notations-o200k.jsonl.gz` | 21,681 | MdC、Blissymbolics、楔形文字 ATF、点字、短い TeX / ABC 例 |

合計 135,607 行（重複排除前）。出典の原本・ライセンス本文は `self-notations-sources/` と `self-extra-sources/` にあります。

## 許諾

リポジトリ全体の MIT だけでは足りません。収録ごとに MIT、CC BY 4.0、CC BY-SA、LGPL-2.1-or-later などが付いています。再配布時は各ソースの条件と帰属表示を残してください。

- 日本顔文字: kaomojikan / kaomojiya-collection / netromdk など（MIT）、Wikipedia（CC BY-SA 4.0）
- 西洋顔文字: Wikipedia / Wiktionary（CC BY-SA 4.0）
- 多言語顔文字: wooorm/emoticon（MIT、全文を `kaomoji-i18n-emoticon-MIT-LICENSE.txt` に同梱）、Wikipedia / Wiktionary（CC BY-SA 4.0）
- 古記法: Unicode EmojiSources / CLDR（Unicode License）、github/gemoji と iamcal/emoji-data（MIT）、dingbat-to-unicode（BSD-2-Clause）。Microsoft フォント本体は含みません
- 追加記法: JSesh `signs_description.xml`（CC BY 4.0、フォントなし）、BCI Authorized Vocabulary 2026（CC BY 4.0、BCI 帰属必須）、ORACC 文書例（CC BY-SA 3.0）、liblouis（LGPL-2.1-or-later）、abcjs（MIT）、KaTeX（MIT）

フォント図形や曲データ、許諾が確認できなかった一覧は入れていません。

## 展開

```bash
gzip -dc docs/o200k-lookup/notations/self-kaomoji-notations-o200k.jsonl.gz > /tmp/self-kaomoji-notations-o200k.jsonl
gzip -dc docs/o200k-lookup/notations/self-extra-notations-o200k.jsonl.gz > /tmp/self-extra-notations-o200k.jsonl
```
