# MorphoZip（E）

**層4 — 文内多言語・文法最小。** 予測候補が少ない短い形を優先。一意読み（rank-1・長い形）と語源寄せもここで扱う。

## 方針（言語非依存の最短形）

**ソース言語を問わず、意味が通る最短の表層へ畳む**（記号 OK）。英語専用・日本語専用の特例を増やさない。比較の `≧` `≦` `≒` `=` はその一例であり、代名詞・前置・接続なども同じ原則（U/he/无/前/bc/∴ …）。

### 具体


- 一人称 → `I`（私は/僕は/俺は…を潰す）
- **代名詞 case-split 在庫（5-bit 設計）**（下記）
- 閉じた品詞在庫（冠詞・接続詞・副詞・助動詞・前置 pack1/prep2・助詞・比較）→ 下記。接続 → `&` `/` `bc` `∴`；前置1 → `w/` `4` `←` `@`；前置2 → `de` `无` `内` `前` `後`；助詞 → `∅` `→` `∈` `〜`；比較 → `≧` `≦`。極性 `!`/`¬` は在庫幅とは別の **1bit フラグ**
- whatever 系 → `∀` / `∀loc` / `∀who` … / hereafter → `∴→`
- 助数詞: JA 既存は維持。EN 数量句も実験的に短くする（`3 animals` → `3匹`, `2 people` → `2人` など）。桁化済みの数字が前提（スペル数字→桁は C）
- 冠詞: 引用なしの `the`/`a`/`an` は落とす。`"the"` / `'the'` は内側の語だけ残す（引用符は外す）。`--keep-articles` で無効化
- 数字は既定で `0-9`。`--hex-nums` で小文字16進（`255` → `0xff`）。`--hex-bare` で `0x` なし（`0-F` スタイル）
- 中国語偏重なし。`--stats` で文字密度


## 代名詞（case-split 在庫）

**軸:** 人称 × **格（主格 / 所有格 / 目的格）** + **独立所有格** mine/ours/yours/theirs（コア）。I–my–me–mine、U–your–you–yours、he–his–him、she–her–hers、it–its–it、they–their–them–theirs、y'all–y'all's。格を畳まない。

**中性 it:** 事物・オブジェクトを含む（**物スロットは作らない**）。**指示代名詞（deixis）** this/that/these/those・これ/それ/あれ・ça/eso 等は **別軸** — it に畳まない（登録時は独立 family）。

在庫幅（設計/レポート）: `bits_per_pronoun = ceil(log2(N))`；コア N=26 → **5 bits/出現**。表層書き換えは **utf8+token 優先**（在庫ビットは二次）。

**コア例:** nom `I`/`U`/`he`/`she`/`it`/`we`/`they`/`y'all`；poss `my`/`your`/`his`/`her`/`its`/`our`/`their`/`y'all's`；obj `me`/`you`/`him`/`her`/`it`/`us`/`them`/`y'all`。

**入力別名（格を保つ）:** 彼女/她/ella/elle→she；彼/他/él/il→he；君→U（主格）；私は→I / 私を→me / 私の→my。目的格 you は sentinel 保護で再食わない。

**開いた she:** she→he に畳まない。y'all = EN コンパクト 2pl（they と別表層）。

ヘルパー: `canonicalize_pronoun` / `pronoun_inventory_bits` / `pronoun_bit_cost` / `utf8_bits`。`--stats` の density に `pronoun_bits_*`。

## 指示代名詞（deixis 在庫）

人称・中性 it とは **別の閉じた在庫**。コア: `ça`（近称単）/ `eso`（遠称単）/ `these` / `those` / `あれ`（JA 遠方）。N=5 → 3bit（設計/レポート）。表層は token→utf8 最安（FR/ES 短形が勝つときそれを採用）。


## 閉じた品詞在庫（ビット主・トークン従）

代名詞と同じ式: **`bits = ceil(log2(N))`**／出現。コアは可能な限り **N≤4 → 2bit**。トークン見積は参考のみ（B）。

汎用 API: `closed_inventory_bits(name)` / `canonicalize_closed` / `closed_bit_cost` / `list_closed_inventories`。各品詞に `*_inventory_bits` / `*_bit_cost` エイリアスあり。`density()` の `closed` に集約。

| 品詞 | コア在庫 | N | bits | 主な写像 | 例 |
| --- | --- | --- | --- | --- | --- |
| 代名詞 pronoun | I/my/me/mine … U/your/you/yours … he/his/him … she/her/hers … it/its … they/their/them/theirs + y'all | 26 | **5** | **格軸**+独立所有格；表層 utf8+token 優先；she 開放；**neuter=it（事物）**；君/彼/彼女=入力別名；bits 設計/レポート | `you…`→`U…`；`mine is yours` 維持；`彼女を`→`her` |
| 指示代名詞 deixis | ça / eso / these / those / あれ | 5 | **3** | **人称・it と別在庫**；this/これ/这→ça；that/それ/那→eso（関係詞 that は除外）；token→utf8 cheapest | `this book`→`ça book`；`それは本`→`eso本`；`I think that…` は that 維持 |
| 冠詞 article | ∅ | 1 | **0** | the/a/an → 削除（引用は保持） | `the cat` → `cat` |
| 接続詞 conjunction | & / bc / ∴ | 4 | 2 | and→& or→/ **because→bc** therefore→∴（cuz は否定せず、数学記号系を優先；点々表記の余地） | `… because …` → `… bc …` |
| 副詞 adverb | tho / ~ / ˅ / esp. | 4 | 2 | however→tho approx→~ very→˅ esp.→esp.；拡張 □=always / oft=often；**never→¬ not→!**（極性は助動詞と共有・在庫外1bit）。∀ は whatever 用 | `however very` → `tho ˅`；`always never` → `□ ¬` |
| 助動詞 auxiliary | can / will / must / may | 4 | 2 | could→can would→will should→must might→may；**I'll は C**；否定 `can't/won't/shouldn't/mustn't/may not`→`!can/!will/!must/!may`；`don't/not`→`!`；肯定は素の can/will/must/may。**極性 `!` = 在庫幅とは別1bit** | `I could` → `I can`；`I won't` → `I !will` |
| 前置詞 preposition | w/ / 4 / ← / @ | 4 | 2 | with→w/ for→4 **from→←** at→@；`fr` は別名のみ（colloquial **for real** 揺らぎ）。ML: con/avec/mit・para/pour/für・desde/depuis/aus・bei。**under/above は C** | `for lunch from home at noon` → `4 lunch ← home @ noon` |
| 前置詞2 prep2 | de / 无 / 内 / 前 / 後 | 5 | **3** | of→de；without→**无**（`w/o`/`sin`/`sans`/`ohne` 別名）；within→内（dentro/innerhalb）；before→前（antes/avant/vor）；after→後（después/après/nach）。pack1 分離で 2bit 維持。C 前後/内外は触らない | `of … without … before …` → `de … 无 … 前 …` |
| 助詞 particle | ∅ / → / ∈ / 〜 | 4 | 2 | は/が/を/ねよさ→∅；に/へ→→；で→∈；まで→〜。拡張 も→+ と→& **から→←**。**と=& はトークン観点 OK**；から=← は前置 from と共有（`fr` 別名のみ） | `学校に行く` → `学校→行く`；`東京から` → `東京←` |
| 比較 compare | ≧ / ≦ | 2 | **1** | **言語非依存**: JA/ZH 以上/以下；EN more than/at least/…；ES más de/al menos/…；FR plus/moins de；DE mehr/weniger als → 同じ ≧/≦。≒/=（approx-equal/equal）。単独 under/below/above は C | `18歳以上` / `más de 3` → `≧` |
| 極性 polarity | ! / ¬ | — | **1**/標 | 在庫幅ではないフラグ。助動詞否定・副詞 not/never で共有。肯定 = マーカー無し | `!can` は aux 2bit + 極性1bit |

> **for→4 の注意**: `4` は数字 four と表現の揺らぎが出うる。ビット在庫（2bit）とは別評価。目的の for 相当は EN `for` に加え ES/FR/DE `para`/`pour`/`für`、JA `ために`/`為に`、ZH `为了`→`4`（裸の `为`/`por` は曖昧のため見送り）。`ために` は助詞 `に→→` より先に適用。

> **from→← / fr の注意**: canonical 短形は **`←`**（`→`＝に/へ と対；LTR 1 字）。`fr` は別名として残すが、colloquial EN **for real** との揺らぎがあるため **出力は ← を優先**（`fr` への自動短縮はしない）。

**拡張:** conjunction +∵/+（N=6→3bit）；adverb +also/□/oft；preposition +to（N=5→3bit）；pronoun +mine/theirs/ours/yours（N 微増・仍≈5bit）；particle +/&/←（N=7→3bit）。prep2 はコアで N=5→3bit（pack 分離で pack1 は 2bit 維持）。

**C との境界:** moreover/furthermore/nevertheless・under/above/below・**I'll 族（`family=abbrev` 縮約）**・チャット頭字語・e.g./etc.・**information→ℹ️（`family=emoji`）**・開いた数学記号（`family=symbol` ≠∞±…）・台帳の前後/内外ペアは C。短形は数学/記号優先（両方効くとき絵文字より記号）。 C 台帳 lex の `metrics.bit` は本モジュールの `utf8_bits` /（在庫適用時）`closed_inventory_bits` を参照する（所有は E のまま）。E の bare 前/後（EN before/after）と 以上/以下→≧/≦、助詞コアは別。`in`/`on` は曖昧のため自動書き換え見送り。

**because / cuz:** `because→bc` 採用。`cuz` は可能性として否定しないが、数学記号寄りの `bc` / `∴` 系を優先。将来点々付き表記が載る余地あり（bc のまま）。

**助動詞・副詞 × not（検証パス実装）:** 否定 `can't/won't/shouldn't/mustn't/may not/don't`→`!…` / `!`；肯定は素の can/will/must/may。副詞 `not→!` `never→¬`。極性は `polarity_bit_cost`（1bit/マーカー）。時制の深い畳み込みは未着手。I'll は C 所有のまま。

## その他の Morpho 書換

- **tho**: 口語 EN の `though` クリップ（外国語ではない）。対照の `however`→`though`→`tho`（一般規則2段）。譲歩/程度の `however hard…` は残す。
- **whichever**→`∀opt`（`∀which` はレガシー展開のみ；`which` 残留なし）。
- **EN 3sg**: `he/she`（およびレガシー 彼/她）の直後で `-s` を原型へ（`he chooses`→`he choose`）。`U` は 3sg なし。

## 語彙ポリシー（揺らぎ削減）

`shared/lex_policy.py` を利用（**E 既定**）:

1. **一意読み（長い形）** — find out → `ascertain`（UNIQUE_COMPACT の `ascrt` は付けない）
2. **語源寄せ** — communication→`comm`、configuration→`cfg`、document→`doc` 等（**information→ℹ️ は C `family=emoji`**）

**FILLER 除去・UNIQUE_COMPACT（ascrt）・`I'll`・スペル数字→桁・合意台帳 lex（下/凹凸）は C（ShorthandEdge）の担当。** E 単体ではフィラーを残し、`I will` のまま、スペル数字も残し、under もそのまま。`--strip` / `--aggressive-fillers` / `--spelled-nums` でオプトイン可。パイプライン `C,E` なら C が先にフィラー・I'll・桁化・台帳 lex を行う。

```bash
uv run python MorphoZip/morpho_zip.py --text '私は will find out the information about three animals'
# → um なし想定なら: I will ascertain information about three animals（冠詞落ち・一人称→I。ℹ️/I'll/桁化は C）
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
