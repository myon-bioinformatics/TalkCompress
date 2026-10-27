# MorphoZip（E）

**層4 — 文内多言語・文法最小。** 予測候補が少ない短い形を優先。一意読み（rank-1・長い形）と語源寄せもここで扱う。

## 方針（言語非依存の最短形）

**ソース言語を問わず、意味が通る最短の表層へ畳む**（記号 OK）。英語専用・日本語専用の特例を増やさない。比較の `≧` `≦` `≒` `=` はその一例であり、代名詞・前置・接続なども同じ原則（君/彼/无/前/bc/∴ …）。

### 具体


- 一人称 → `I`（私は/僕は/俺は…を潰す）
- **代名詞 2-bit 在庫**（下記）
- 閉じた品詞在庫（冠詞・接続詞・副詞・助動詞・前置 pack1/prep2・助詞・比較）→ 下記。接続 → `&` `/` `bc` `∴`；前置1 → `w/` `4` `←` `@`；前置2 → `de` `无` `内` `前` `後`；助詞 → `∅` `→` `∈` `〜`；比較 → `≧` `≦`。極性 `!`/`¬` は在庫幅とは別の **1bit フラグ**
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
| 代名詞 pronoun | I / 君 / 彼 / they | 4 | 2 | they\|them\|y'all 同一；她→彼表層；ES/FR/DE 主語（yo/je/ich, tú/tu/du, él/il/ella/elle, ellos/ils…）同スロット | `yo … ella` → `I … 她` |
| 冠詞 article | ∅ | 1 | **0** | the/a/an → 削除（引用は保持） | `the cat` → `cat` |
| 接続詞 conjunction | & / bc / ∴ | 4 | 2 | and→& or→/ **because→bc** therefore→∴（cuz は否定せず、数学記号系を優先；点々表記の余地） | `… because …` → `… bc …` |
| 副詞 adverb | tho / ~ / ˅ / esp. | 4 | 2 | however→tho approx→~ very→˅ esp.→esp.；拡張 □=always / oft=often；**never→¬ not→!**（極性は助動詞と共有・在庫外1bit）。∀ は whatever 用 | `however very` → `tho ˅`；`always never` → `□ ¬` |
| 助動詞 auxiliary | can / will / must / may | 4 | 2 | could→can would→will should→must might→may；**I'll は C**；否定 `can't/won't/shouldn't/mustn't/may not`→`!can/!will/!must/!may`；`don't/not`→`!`；肯定は素の can/will/must/may。**極性 `!` = 在庫幅とは別1bit** | `I could` → `I can`；`I won't` → `I !will` |
| 前置詞 preposition | w/ / 4 / ← / @ | 4 | 2 | with→w/ for→4 **from→←** at→@；`fr` は別名のみ（colloquial **for real** 揺らぎ）。ML: con/avec/mit・para/pour/für・desde/depuis/aus・bei。**under/above は C** | `for lunch from home at noon` → `4 lunch ← home @ noon` |
| 前置詞2 prep2 | de / 无 / 内 / 前 / 後 | 5 | **3** | of→de；without→**无**（`w/o`/`sin`/`sans`/`ohne` 別名）；within→内（dentro/innerhalb）；before→前（antes/avant/vor）；after→後（después/après/nach）。pack1 分離で 2bit 維持。C 前後/内外は触らない | `of … without … before …` → `de … 无 … 前 …` |
| 助詞 particle | ∅ / → / ∈ / 〜 | 4 | 2 | は/が/を/ねよさ→∅；に/へ→→；で→∈；まで→〜。拡張 も→+ と→& **から→←**。**と=& はトークン観点 OK**；から=← は前置 from と共有（`fr` 別名のみ） | `学校に行く` → `学校→行く`；`東京から` → `東京←` |
| 比較 compare | ≧ / ≦ | 2 | **1** | **言語非依存**: JA/ZH 以上/以下；EN more than/at least/…；ES más de/al menos/…；FR plus/moins de；DE mehr/weniger als → 同じ ≧/≦。≒/=（approx-equal/equal）。単独 under/below/above は C | `18歳以上` / `más de 3` → `≧` |
| 極性 polarity | ! / ¬ | — | **1**/標 | 在庫幅ではないフラグ。助動詞否定・副詞 not/never で共有。肯定 = マーカー無し | `!can` は aux 2bit + 極性1bit |

> **for→4 の注意**: `4` は数字 four と表現の揺らぎが出うる。ビット在庫（2bit）とは別評価とし、最終的に `for`（原形）などに戻る可能性あり（未変更・TODO）。

> **from→← / fr の注意**: canonical 短形は **`←`**（`→`＝に/へ と対；LTR 1 字）。`fr` は別名として残すが、colloquial EN **for real** との揺らぎがあるため **出力は ← を優先**（`fr` への自動短縮はしない）。

**拡張:** conjunction +∵/+（N=6→3bit）；adverb +also/□/oft；preposition +to（N=5→3bit）；pronoun +it（N=5→3bit）；particle +/&/←（N=7→3bit）。prep2 はコアで N=5→3bit（pack 分離で pack1 は 2bit 維持）。

**C との境界:** moreover/furthermore/nevertheless・under/above/below・**I'll 族（`family=abbrev` 縮約）**・チャット頭字語・e.g./etc.・台帳の前後/内外ペアは C。 C 台帳 lex の `metrics.bit` は本モジュールの `utf8_bits` /（在庫適用時）`closed_inventory_bits` を参照する（所有は E のまま）。E の bare 前/後（EN before/after）と 以上/以下→≧/≦、助詞コアは別。`in`/`on` は曖昧のため自動書き換え見送り。

**because / cuz:** `because→bc` 採用。`cuz` は可能性として否定しないが、数学記号寄りの `bc` / `∴` 系を優先。将来点々付き表記が載る余地あり（bc のまま）。

**助動詞・副詞 × not（検証パス実装）:** 否定 `can't/won't/shouldn't/mustn't/may not/don't`→`!…` / `!`；肯定は素の can/will/must/may。副詞 `not→!` `never→¬`。極性は `polarity_bit_cost`（1bit/マーカー）。時制の深い畳み込みは未着手。I'll は C 所有のまま。

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
