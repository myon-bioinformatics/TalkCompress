# TesseraTalk（B）

**層2 — 機械 + 高度な人間。** 文ごとに言語が切り替わるモザイク。LTR + 。！？ を当面の前提。

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

```bash
uv run python TesseraTalk/tessera_talk.py tag --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --text 'Hello. World. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --no-rle --text 'Hello. World.'
uv run python TesseraTalk/tessera_talk.py expand --text 'en:Hello.|World.|ja:こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --stats --text 'Hello. こんにちは。'
```
