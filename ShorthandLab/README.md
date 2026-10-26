# ShorthandLab（C）

**層3 — 人間同士のギリギリ。** スラング・略語・絵文字・「以降こう書く」規約。

## できること

- EN 略語 + JA 略語 + 絵文字マップ（最長一致）。チャット / MCP 向けを拡充
- `hereafter X=Y` / `∴ X=Y` / `以降 X=Y` をセッション規約として取り込み（パイプラインでも有効）
- `--lexicon PATH` で追加語彙 JSON（`{long: short}` または `{"map": {...}}`）をマージ
- 任意で `--state` JSON に規約を永続化
- `compress` / `expand` 双方向

```bash
uv run python ShorthandLab/shorthand_lab.py compress --text 'as soon as possible'
uv run python ShorthandLab/shorthand_lab.py compress --lexicon extra.json --text 'special phrase here'
uv run python ShorthandLab/shorthand_lab.py compress --state /tmp/sh.json --text $'hereafter pull request=PR\nopen a pull request'
```

## Domain packs

Built-in packs under `packs/` (`dev`, `mcp`). `--pack NAME` (repeatable) merges into the session map.

