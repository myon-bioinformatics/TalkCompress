# TesseraTalk（B）

**層2 — 機械 + 高度な人間。** 文ごとに言語が切り替わるモザイク。LTR + 。！？ を当面の前提。

**重み:** 翻訳によるトークン削減（EN / JA / ZH）。自然に短い形（翻訳由来の略語含む）は許容。C の合意台帳パッチ（under→下 など）は **適用しない**。

## できること

- 文分割（`.!?。？！…`）
- Unicode スクリプト + 軽い語彙キューによるヒューリスティック LID
- `compress` → モザイク / `expand` → 平文 / `tag` → `[lang] …`
- **RLE モザイク（既定オン）**: 連続する同言語では言語タグを省略し継承

  ```
  en:Hello.|World.|ja:こんにちは。
  ```

  `expand` は旧形式 `lang:sent|lang:sent` と RLE の両方を受理。`--no-rle` で常にフルタグ。
- `--stats` で文数・言語ヒストグラム（JSON → stderr）
- **翻訳トークン最短（opt-in）**: `--translate-min` / `translate_min=True`

  文ごとに `fixtures/translations.json` の候補（EN/JA/ZH・自然な短形）を `estimate_tokens` で比較し、**厳密に短いときだけ**採用。ライブ翻訳 API は使わない（pytest 決定的）。C 台帳とは別経路。

```bash
uv run python TesseraTalk/tessera_talk.py tag --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --text 'Hello. World. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --no-rle --text 'Hello. World.'
uv run python TesseraTalk/tessera_talk.py expand --text 'en:Hello.|World.|ja:こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --stats --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --translate-min --text 'Good morning. Please reply as soon as possible.'
```

## prefer-ltr / script_mix

`--prefer-ltr` biases Latin+CJK mixes without kana toward `en` rather than `zh`. `script_mix(text)` returns script counts/ratios; included in `--stats` JSON.

## C との境界

| | B TesseraTalk | C ShorthandEdge |
| --- | --- | --- |
| 短縮の主因 | 文の翻訳でトークンが減るなら採用 | 登録済み略語・合意台帳 lex |
| 略語 | 翻訳結果として自然に出るもの OK | パッチ／台帳で明示登録 |
| under→下 等 | しない（翻訳バンク経由のみ） | 台帳で適用 |

## Round-4

翻訳バンク拡充。`--translate-min` は DispatchHub 経由でも可。
