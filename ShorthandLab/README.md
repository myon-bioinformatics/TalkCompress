# ShorthandLab（C）

**層3 — 人間同士のギリギリ。** スラング・略語・絵文字・「以降こう書く」規約。

## できること

- EN 略語 + JA 略語 + 絵文字マップ（最長一致）
- `hereafter X=Y` / `∴ X=Y` / `以降 X=Y` をセッション規約として取り込み
- 任意で `--state` JSON に規約を永続化
- `compress` / `expand` 双方向

```bash
uv run python ShorthandLab/shorthand_lab.py compress --text 'as soon as possible'
uv run python ShorthandLab/shorthand_lab.py compress --state /tmp/sh.json --text $'hereafter pull request=PR\nopen a pull request'
```
