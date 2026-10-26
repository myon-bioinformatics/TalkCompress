# TesseraTalk（B）

**層2 — 機械 + 高度な人間。** 文ごとに言語が切り替わるモザイク。LTR + 。！？ を当面の前提。

## できること

- 文分割（`.!?。？！…`）
- Unicode スクリプト + 軽い語彙キューによるヒューリスティック LID（ラウンドロビンではない）
- `compress` → `en:…|ja:…` モザイク / `expand` → 平文 / `tag` → `[lang] …`

```bash
uv run python TesseraTalk/tessera_talk.py tag --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py expand --text 'en:Hello.|ja:こんにちは。'
```
