# ShorthandEdge（C）

語源: *shorthand*（速記・略語）+ *edge*（人間側の縁・境界）。層3の「人間ギリギリ」のエッジ。

**層3 — 人間同士のギリギリ。** スラング・略語・絵文字・「以降こう書く」規約。加えて **FILLER 除去**・**UNIQUE_COMPACT**（ascertain→`ascrt`）・**同一言語の省略**（`I will`→`I'll`）・**スペル数字→桁**（`three`→`3`）・**合意台帳 lex**（under→`下`、凹凸 など）を担当。

## 合意台帳（ledger）

ソース・オブ・トゥルースは [`ledger/conventions.json`](ledger/conventions.json)。読込は `shared/ledger.py`。C が compress 時に適用（`--no-ledger` でオフ）。ℹ️ は E の語源パスのまま。

| kind | 役割 |
| --- | --- |
| `lex` | 置換（`from`→`to`）。`apply_layer=C` |
| `policy` | 方針メモ（EN+ZH+JA ベースなど） |

```bash
uv run python -m shared.ledger --list
uv run python -m shared.ledger --apply 'under the table'
uv run python ShorthandEdge/shorthand_edge.py compress --text 'below average and デコボコ'
```

## できること

- EN 略語 + JA 略語 + 絵文字マップ（最長一致）。チャット / MCP 向けを拡充
- フィラー除去（um / えーと / I mean …）— E ではなくここが既定の担当
- UNIQUE_READINGS + UNIQUE_COMPACT（find out → ascertain → `ascrt`）
- 同一言語の短縮: `I will`→`I'll`（`私は will` も先に `I` 化）、`three`→`3` など
- 合意台帳 lex: `under`/`below`→`下`、`デコボコ`/`bumpy`→`凹凸` など
- `hereafter X=Y` / `∴ X=Y` / `以降 X=Y` をセッション規約として取り込み（パイプラインでも有効）
- `--lexicon PATH` で追加語彙 JSON（`{long: short}` または `{"map": {...}}`）をマージ
- 任意で `--state` JSON に規約を永続化
- `compress` / `expand` 双方向

```bash
uv run python ShorthandEdge/shorthand_edge.py compress --text 'as soon as possible'
uv run python ShorthandEdge/shorthand_edge.py compress --text 'um please find out the answer'
# → pls ascrt the answer
uv run python ShorthandEdge/shorthand_edge.py compress --text 'um 私は will find out about three animals'
# → I'll ascrt about 3 animals
uv run python ShorthandEdge/shorthand_edge.py compress --lexicon extra.json --text 'special phrase here'
uv run python ShorthandEdge/shorthand_edge.py compress --state /tmp/sh.json --text $'hereafter pull request=PR\nopen a pull request'
```

## Domain packs

Built-in packs under `packs/` (`dev`, `mcp`). `--pack NAME` (repeatable) merges into the session map.
