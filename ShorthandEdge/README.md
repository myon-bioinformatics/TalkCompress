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
- 合意台帳 lex: `under`/`below`→`下`、家具 `table`→`机`（同等に `桌`/`桌子` 可・SQL/tech は残す）、`デコボコ`/`bumpy`→`凹凸` など
- 曖昧さゲート: `moreover`→`also` 等は衝突時または `--prefer-precision` で原文維持（C 所有）
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

## Round-4

台帳に左右・前後・内外・大小・接続詞英語短形・家具 table→机/桌（SQL スキップ）・曖昧さゲート。`packs/chat.json`。


## Ambiguity gate / furniture table

Owned entirely by C (`shared/ledger.py` + `ledger/conventions.json`).

| Rule | Behavior |
| --- | --- |
| Furniture `table`/`tables` | → canonical **机** (allowed targets: 机 / 桌 / 桌子). Not 机-only dogma — pick a short EN+ZH+JA furniture lexeme. |
| SQL/tech context | Keep English `table` when cues like `SQL`, `SELECT`, `CREATE TABLE`, `JOIN`, `schema`, `db`, `database` appear. |
| `ambiguity_sensitive` conj | e.g. moreover→also, therefore→so, nevertheless→but. Clear additive context still shortens. |
| Collision | If the short form already appears in the text, keep the longer original. |
| `--prefer-precision` | Skip all ambiguity-sensitive shortenings. |

```bash
uv run python -m shared.ledger --apply 'put it on the table'
# → put it on 机
uv run python -m shared.ledger --apply 'CREATE TABLE users'
# → CREATE TABLE users
uv run python -m shared.ledger --apply 'moreover we also need time'
# → moreover we also need time  (collision)
uv run python -m shared.ledger --prefer-precision --apply 'moreover we continue'
# → moreover we continue
```
