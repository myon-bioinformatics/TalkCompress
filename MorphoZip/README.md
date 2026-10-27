# MorphoZip（E）

**層4 — 文内多言語・文法最小。** 予測候補が少ない短い形を優先。一意読み（rank-1・長い形）と語源寄せもここで扱う。

## 方針

- 一人称 → `I`（私は/僕は/俺は…を潰す）
- **代名詞 2-bit 在庫**（下記）
- 閉じた品詞在庫（冠詞・接続詞・副詞・助動詞・前置詞）→ 下記。接続 → `&` `/` `bc` `∴`；前置 → `w/` `4` `fr` `@`；`w/o` は拡張
- whatever 系 → `∀` / `∀loc` / `∀who` … / hereafter → `∴→`
- 助数詞: JA 既存は維持。EN 数量句も実験的に短くする（`3 animals` → `3匹`, `2 people` → `2人` など）。桁化済みの数字が前提（スペル数字→桁は C）
- 冠詞: 引用なしの `the`/`a`/`an` は落とす。`"the"` / `'the'` は内側の語だけ残す（引用符は外す）。`--keep-articles` で無効化
- 数字は既定で `0-9`。`--hex-nums` で小文字16進（`255` → `0xff`）。`--hex-bare` で `0x` なし（`0-F` スタイル）
- 中国語偏重なし。`--stats` で文字密度


## 代名詞（2-bit 在庫）

**指標の整理（代名詞）:** 主 = **ビット**（在庫 `ceil(log2(N))`、コア 2bit でゲート）。副・軽め = **トークン**（例: `y'all` はトークン観点で **1トークン** 扱い）。代名詞の選択をトークン軸で深く吟味・最適化はしない（トークン見積は B TesseraTalk `estimate_tokens` の参考表示のみ）。

主指標は **在庫インデックス幅**（UTF-8 長ではない）:

`bits_per_pronoun = ceil(log2(N))` where `N = len(PRONOUN_CANONICAL)`（出現ごと・表層 UTF 長はコストに入れない）。

**コア（≤2 bit 目標）:** `PRONOUN_CANONICAL = (I, 君, 彼, they)` → **N=4 → 2 bits/出現**。

| スロット | ビット | 表層の自由変異（同じコスト） |
| --- | --- | --- |
| `I` | 2 | I / me / my（JA 私は…→I など） |
| `君` | 2 | 君 / 君の ← you / your / あなた… |
| `彼` | 2 | 彼 / 彼の ← he/him/his；**她 / 她の は表層のみ**（ビットは 彼） |
| `they` | 2 | **they / them / y'all**（および their）— 同一スロット |

2pl 入力（`you all` / `you guys` / 皆さん / 你们…）→ 表層 `y'all`（スロット `they`）。
3pl は `they`/`them` のまま（潰さない）。`he or she` → `彼/她`（they へ畳まない）。

**她について（両方の数字）:**

| 経路 | コスト |
| --- | --- |
| コア在庫（彼女/she → 表層 她、スロット 彼） | **2 bits**/出現 |
| 二次指標 `utf8_bits("她")` | **24 bits**（3 UTF-8 bytes × 8） |
| もし 她を第5コアにすると | N≥5 → 全員 **3 bits**（採用しない） |

**拡張（オプトイン）:** `PRONOUN_EXTENDED = (…, it)` → N=5 → 3 bits。`pronoun_inventory_bits(extended=True)` / `pronoun_bit_cost(..., extended=True)`。`it` は表層として出すが、コア予算ゲートには入れない。

ヘルパー: `canonicalize_pronoun` / `pronoun_inventory_bits` / `pronoun_bit_cost` / `utf8_bits`。`--stats` の density に `pronoun_bits_*` を含む。


## 閉じた品詞在庫（ビット主・トークン従）

代名詞と同じ式: **`bits = ceil(log2(N))`**／出現。コアは可能な限り **N≤4 → 2bit**。トークン見積は参考のみ（B）。

汎用 API: `closed_inventory_bits(name)` / `canonicalize_closed` / `closed_bit_cost` / `list_closed_inventories`。各品詞に `*_inventory_bits` / `*_bit_cost` エイリアスあり。`density()` の `closed` に集約。

| 品詞 | コア在庫 | N | bits | 主な写像 | 例 |
| --- | --- | --- | --- | --- | --- |
| 代名詞 pronoun | I / 君 / 彼 / they | 4 | 2 | they\|them\|y'all 同一；她→彼表層 | `he or she` → `彼/她` |
| 冠詞 article | ∅ | 1 | **0** | the/a/an → 削除（引用は保持） | `the cat` → `cat` |
| 接続詞 conjunction | & / bc / ∴ | 4 | 2 | and→& or→/ because→bc therefore→∴ | `and … because … therefore` → `& … bc … ∴` |
| 副詞 adverb | tho / ~ / ˅ / esp. | 4 | 2 | however→tho approx→~ very→˅ esp.→esp. | `however very` → `tho ˅` |
| 助動詞 auxiliary | can / will / must / may | 4 | 2 | could→can would→will should→must might→may；**I'll は C** | `I could` → `I can` |
| 前置詞 preposition | w/ / 4 / fr / @ | 4 | 2 | with→w/ for→4 from→fr at→@；**under/above は C** | `for lunch from home at noon` → `4 lunch fr home @ noon` |

**拡張:** conjunction +∵/+（N=6→3bit）；adverb +also；preposition +of/to/w/o（N=7→3bit）；pronoun +it（N=5→3bit）。

**C との境界:** moreover/furthermore/nevertheless・under/above/below・I'll は C（台帳／曖昧さゲート／縮約）。E は触らない。`in`/`on` は曖昧のため自動書き換え見送り。

## 語彙ポリシー（揺らぎ削減）

`shared/lex_policy.py` を利用（**E 既定**）:

1. **一意読み（長い形）** — find out → `ascertain`（UNIQUE_COMPACT の `ascrt` は付けない）
2. **語源寄せ** — information/info/情報/información → `ℹ️`（U+2139 U+FE0F）

**FILLER 除去・UNIQUE_COMPACT（ascrt）・`I'll`・スペル数字→桁・合意台帳 lex（下/凹凸）は C（ShorthandEdge）の担当。** E 単体ではフィラーを残し、`I will` のまま、スペル数字も残し、under もそのまま。`--strip` / `--aggressive-fillers` / `--spelled-nums` でオプトイン可。パイプライン `C,E` なら C が先にフィラー・I'll・桁化・台帳 lex を行う。

```bash
uv run python MorphoZip/morpho_zip.py --text '私は will find out the information about three animals'
# → um なし想定なら: I will ascertain ℹ️ about three animals（冠詞落ち・一人称→I・ℹ️。I'll/桁化なし）
uv run python MorphoZip/morpho_zip.py --text 'I see 3 animals and 2 people'
# → I see 3匹 & 2人
uv run python MorphoZip/morpho_zip.py --stats --text 'I am here with you'
uv run python MorphoZip/morpho_zip.py --hex-nums --text 'retry 255 times'
uv run python MorphoZip/morpho_zip.py --strip --text 'um ready'   # オプトイン
uv run python MorphoZip/morpho_zip.py --no-unique --text '...'   # 一意化オフ
```

## Protected spans

`[[keep:...]]` and `` `keep:...` `` wrappers are stripped; inner text is preserved unchanged through compress. `--protect-regex` (repeatable) masks full matches the same way.

## Round-4

助数詞（台・棟・杯・組・社・通・機・階）、e.g./i.e.、スマート引用符の冠詞保持。
