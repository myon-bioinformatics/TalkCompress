# ShorthandEdge（C）

語源: *shorthand*（速記・略語）+ *edge*（人間側の縁・境界）。層3の「人間ギリギリ」のエッジ。

**層3 — 人間同士のギリギリ。** スラング・略語・絵文字・「以降こう書く」規約。加えて **FILLER 除去**・**UNIQUE_COMPACT**（ascertain→`ascrt`）・**同一言語の省略**（`I will`→`I'll`）・**スペル数字→桁**（`three`→`3`）・**合意台帳 lex**（under→`下`、凹凸 など）を担当。

## 合意台帳（ledger）

lex の **`breakdown`（内訳）**: 品詞が付けば POS（`pronoun` / `deixis` / …）、否则 `collocation` / `熟語` / `slang` / `acronym` / `token圧縮` 等の平たいタグ1つ（列を増やし過ぎない）。

ソース・オブ・トゥルースは [`ledger/conventions.json`](ledger/conventions.json)。読込は `shared/ledger.py`。C が compress 時に適用（`--no-ledger` でオフ）。information→ℹ️ も C `family=emoji`。

| kind | 役割 |
| --- | --- |
| `lex` | 置換（`from`→`to`）。`apply_layer=C`。**`metrics.token` + `metrics.bit` 必須**（B `estimate_tokens` / E `utf8_bits` or inventory） |
| `policy` | 方針メモ（EN+ZH+JA は開始セット；天井ではない）。`metrics` 省略可 |

登録時はトークン観点とビット観点の両方を台帳に入れる。両方足すと短形候補が絞れる。C が B/E ヘルパーを呼ぶ（所有は移さない）。

```bash
uv run python -m shared.ledger --validate-metrics
uv run python -m shared.ledger --backfill-metrics   # lex に dual metrics を再計算して書く
```

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
- 合意台帳 lex: `under`/`below`→`下`、家具 `table`→`机`（同等に `桌`/`桌子` や mesa/Tisch/tavolo/tafel/τραπέζι 可・SQL/tech は残す）、`デコボコ`/`bumpy`→`凹凸` など
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


## Abbrev family（C 一層）

略・縮約・頭字語は **C の `family=abbrev`** にまとめる（E は I'll 族を確立しない）。

| abbrev_kind | 例 | 書換 |
| --- | --- | --- |
| `contraction` | `c-ill` I will→I'll、`c-dont` do not→don't | `apply_en_contractions`（台帳は登録のみ / `ledger_apply=false`） |
| `acronym` | `c-asap` / `c-brb` / `c-tldr` … | 台帳 lex + packs |
| `latin` | `conj-for-example`→e.g.、`conj-etc`、`conj-vs`、`conj-that-is`→i.e. | 台帳 lex |

`EN_CONTRACTION_SPEC`（`shared/lex_policy.py`）が縮約の単一ソース。台帳へは:

```bash
uv run python -m shared.ledger --sync-contractions
```

極性メモ: C が `do not`→`don't` / `cannot`→`can't` したあと、E は `don't`→`!` / `can't`→`!can` に畳み得る（パイプライン `C,E`）。




## Ever family（C・5W1H 譲歩）

`no matter how/what/…` や `regardless of how/…` など **複数語の譲歩句**を `-ever` に畳む（`family=ever`）。

| wh | 例 from | to |
| --- | --- | --- |
| how | no matter how / regardless of how | however |
| what | no matter what | whatever |
| which | no matter which | whichever |
| where | no matter where | wherever |
| when | no matter when | whenever |
| who | no matter who | whoever |

- **however ゲート**: 逆接の however（しかし）は対象外。台帳の multiword `from[]` だけ置換。`ambiguity_sensitive`（衝突 / `--prefer-precision` で原文維持）。
- **whyever** は不自然なので見送り。
- ML cognate（`egal wie` / `no importa cómo` / `n'importe comment` 等）は `select_cheapest_form` が `-ever` を選び utf8 も縮むときだけ `from` 別名。
- dual metrics 必須；utf8 必須縮小。`c-asap`（ASAP）は `尽快` より短いので C では ASAP 優先のまま。

## Emoji family（C 一層）

語→絵文字の短縮は **C の `family=emoji`**（`family=abbrev` の隣）。台帳は **適用する**（`ledger_apply=true`）。

**多言語 pivot ルール（policy-emoji-pivot）:** ML 別名 → **pivot**（既定 EN；EN が不自然なら JA）→ 絵文字。emoji id ごとに pivot を1つ。台帳行の `pivot` / `pivot_lang` を見れば判断できる。適用は二段（alias→pivot、pivot→emoji）。

**短形優先（policy-short-form-priority）:** (1) 意味がはっきり載るなら **数学/記号優先**（≧≦、←→、∴∵、&、✓、★、≠、∞ 等の E/C 在庫）。(2) 噛み合わないときだけ絵文字。両方効くなら既存記号を選び絵文字ピアを増やさない（check→✓ not ✅；star→★ not ⭐；cross→✕ not ❌）。

**言語横断 cheapest（policy-cross-lang-cheapest）:** 意味が通る候補から B `estimate_tokens` → E `utf8_bits` が最も楽な表層を選ぶ（`shared.ledger.select_cheapest_form`）。登録時 dual metrics；utf8 不変は落とす。

**`family=symbol`:** E 閉じた品詞以外の開いた数学記号（≠ ∞ ± % ° ⇒ ⇔ ∝ √ × ÷）。絵文字より記号が載るならこちら。E の ~/≒/= /≧/≦/∴/bc/∀ は増やさない。

| 例 | pivot | 短形 | 備考 |
| --- | --- | --- | --- |
| ファイア / Feuer / fire / on fire | fire (en) | 🔥 | sample=ファイア（utf8 縮）。ML→fire→🔥 |
| heart / ハート / Herz | heart (en) | ♡ | ❤️ は utf8 増のため不採用 |
| thumbs up / いいね | thumbs up (en) | 👍 | |
| check / チェック | check (en) | ✓ | 記号優先（✅ と同義） |
| cross / ばつ | cross mark (en) | ✕ | 記号優先（❌ と同義；× は乗算曖昧） |
| star / スター | star (en) | ★ | 記号優先（⭐ より ★） |
| warning / 警告 | warning (en) | ⚠ | |
| hundred / 百点 | hundred (en) | 💯 | |
| information / インフォメーション 等 | information (en) | ℹ️ | 旧 ETYMON から移管；FYI 句は DEFAULT_MAP が先 |
| not equal / infinity / … | — | ≠ ∞ ± … | `family=symbol`（E 未所有） |

`EMOJI_SPEC`（`shared/lex_policy.py`）が単一ソース。utf8 が縮まない bare idea/eyes/… は DEFAULT_MAP の runtime extras のみ。**information→ℹ️ も C**（E etymon から移管）。

```bash
uv run python -m shared.ledger --sync-emoji
uv run python -m shared.ledger --sync-symbol
uv run python -m shared.ledger --apply 'ハートとファイア'
```

## Domain packs

Built-in packs under `packs/` (`dev`, `mcp`). `--pack NAME` (repeatable) merges into the session map.

## Round-4

台帳に左右・前後・内外・大小・接続詞英語短形・家具 table→机/桌ほか多言語の机相当（SQL スキップ）・曖昧さゲート。`packs/chat.json`。


## Ambiguity gate / furniture table

Owned entirely by C (`shared/ledger.py` + `ledger/conventions.json`).

| Rule | Behavior |
| --- | --- |
| Furniture `table`/`tables` | → canonical **机** (allowed: 机 / 桌 / 桌子 / mesa / Tisch / tavolo / tafel / τραπέζι). Not 机-only dogma — short desk equivalents across JA/ZH and Romance/Germanic/Greek. |
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
