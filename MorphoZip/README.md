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

**C との境界:** moreover/furthermore/nevertheless・regarding→re:・as follows→↓・inter alia→i.a.・under/above/below・**I'll 族（`family=abbrev` 縮約）**・チャット頭字語・e.g./etc.・**information→ℹ️（`family=emoji`）**・開いた数学記号（`family=symbol` ≠∞±…）・台帳の前後/内外ペアは C。短形は数学/記号優先（両方効くとき絵文字より記号）。 C 台帳 lex の `metrics.bit` は本モジュールの `utf8_bits` /（在庫適用時）`closed_inventory_bits` を参照する（所有は E のまま）。E の bare 前/後（EN before/after）と 以上/以下→≧/≦、助詞コアは別。`in`/`on` は曖昧のため自動書き換え見送り。

**because / cuz:** `because→bc` 採用。`cuz` は可能性として否定しないが、数学記号寄りの `bc` / `∴` 系を優先。将来点々付き表記が載る余地あり（bc のまま）。

**助動詞・副詞 × not（検証パス実装）:** 否定 `can't/won't/shouldn't/mustn't/may not/don't`→`!…` / `!`；肯定は素の can/will/must/may。副詞 `not→!` `never→¬`。極性は `polarity_bit_cost`（1bit/マーカー）。時制の深い畳み込みは未着手。I'll は C 所有のまま。

## その他の Morpho 書換

- **tho**: 口語 EN の `though` クリップ（外国語ではない）。対照の `however`→`though`→`tho`（一般規則2段）。譲歩/程度の `however hard…` は残す。
- **prep / prep-like adv（有限高頻）**: across→↔ along→沿 among/amid→中 beside→傍 between→間 beyond→≫ against→対 around→○ during→中 except→除 including→含 inside→内 outside→外 through→通 until/till→〜 despite→雖；overhead→頭上 overseas→海外 underground→地下 upstairs/downstairs→上階/下階 indoors/outdoors→屋内/屋外 ahead→→ together→共 meanwhile→∥ nearby→近 等。追加（同一優先）: according to→依 / owing|due to→因 / prior to→前 / subsequent to→後 / in spite of→雖 / in front of→前 / in back of→後 / next to→傍 / close to→近 / far from→遠 / away from→離 / out of→外 / opposite→対側 / into→入 / circa→c. / beneath→下；beforehand→先 / forever→∞ / overnight→泊 / thereafter→後 / everywhere→∀loc / somewhere→某处 / elsewhere→别处 / anew→再。閉じ在庫Nは膨らませず `_SUBS`+台帳。via/per/since/onto/upon/anyway 等は見送り。 **cycle2**: in favor of→pro / on behalf of→代表 / by means of→手段 / in terms of→観点 / in accordance with|pursuant to→準 / as for|as to→re: / up to→≦ / down to→至 / in between→間 / off of→外 / out from→出 / in light|view of→鑑 / in lieu|place of→代 / for the sake of→為 / in case of→場合 / regardless|irrespective of→不問 / aside|apart from|other than→他 / along|together with→共 / as opposed to|rather than→vs / past→過 / round→○ / following→次 / preceding→先 / pending→未決。 **cycle3**: by virtue of→力 / by way of|courtesy of→経 / on account|by reason of→因 / for fear of→恐 / in exchange|return for→⇔ / in regard to→re: / on top of→且 / at the expense of→犠牲 / at the risk of→危 / in the event of→場合 / in the middle|midst of→最中 / on the verge of→瀕 / for lack|want of→欠 / in excess of→超 / in contrast to|with→対比 / as a result|consequence of→∴ / in the course of→過程 / over the course of→通 / in the face of→面前。 **cycle4**: for the purpose of→目的 / for the benefit of→益 / in the interest(s) of→利 / to the detriment of→害 / in support of→援 / in charge of→責 / in control of→制 / in search of→求 / in need of→要 / in hope(s) of→希 / in the wake of→跡 / in the name of→名 / at the hands of→手 / at the mercy of→弄 / ahead|in advance of→先 / in association with→連携 / in comparison with|to→比 / in common with→共通 / subject to→条件 / adjacent to→隣 / in defiance of→反 / by order of→命 / under cover of→覆 / at odds with→対立 / with a view|eye to→狙 / on the basis of→基 / in the presence of→在 / at the price of→代価 / under the auspices of→傘 / in parallel|tandem with→∥。折り込み: by dint|force→力 / brink|point→瀕 / exception|exclusive|save for→除 / inclusive→含 / short|default→欠 / thanks|grounds→因 / cost→犠牲 / process→過程 / as per→準 / conjunction→共 / connection|relative|respect|regards|apropos→re: / vis-à-vis→vs / clear of→離 / free|devoid|absence→无 / outside|inside of→外|内 / unlike→≠。 **cycle5**: in response|reaction|reply to→応 / in answer to→答 / in line|step with→沿 / in agreement|keeping with→合 / depending on|upon→依 / as well as→+ / let alone|much less|not to mention→況 / faced|confronted with|up against→直面 / pertaining|relating to→関 / independent of→独立 / akin|similar|comparable to→≒ / equivalent to→≡ / limited|restricted|confined to→限 / attributable|ascribable to→帰；for the time being|for now→暫 / at once|right|straight away→即 / all of a sudden→突 / from time to time|now and then|by chance→偶 / at last→遂 / at first→初 / in short|brief→略 / in fact→実 / in practice→実際 / in theory→理 / in general→一般 / on purpose|by design→故意 / in vain→徒 / at present|at the moment→今 / ahead of time→早 / under way→進行。折り込み: meantime|interim→∥ / over and above|above and beyond→超 / based on→基 / except|but for→除 / across from→対側 / next door→隣 / conflict|variance→対立 / compliance|conformity→準 / from now on→∴→ / reference|relation→re:。 **cycle6**: contrary|counter to→逆 / proportional to→比例 / in pursuit of→追；after all→結局 / above all→最 / all in all→総 / all the same→猶 / by and large|on the whole→概 / by far→遥 / for sure|certain→確 / in any case|event|at any rate→何れ / in the end→最終 / in the long run→長期 / on the contrary→反対 / on the other hand→他方 / to some|a certain extent→或程 / as usual|always→常 / more or less→殆 / little by little|bit by bit→徐 / step by step→逐 / one by one→逐一 / side by side→並列 / again and again|over and over→繰 / as a result→結果 / in advance→予 / by all means→是非 / in essence→本質 / in detail→詳 / in retrospect|hindsight→回顧 / without fail→必ず。折り込み: with regard|respect to→re: / once again|more→再 / right now→今。 **cycle7**: north|south|east|west of→北|南|東|西 / to the left|right of→左|右 / on the part of→側 / in disregard of→無視 / out of control|date|order→暴走|廃|故障 / under pressure|control→圧|制御 / liable|resistant|sensitive to→負|耐|敏 / inferior|superior|preferable to→劣|優；no longer|any longer→最早 / as yet→未 / on (the) one hand→一方 / in the short run→短期 / to a large extent→大程 / shortly|soon after→直後 / shortly before→直前 / day|year by day|year→日々|年々 / face to face→対面。折り込み: exclusive of→除 / contiguous→隣 / previous→前 / near to→近 / every now and then|so often|now and again→偶 / as a matter of fact→実。 **cycle8**: upstream|downstream of|from→上流|下流 / out of place|reach→不所|届外 / under fire|review→被弾|審査中 / immune|prone to→免疫|傾向 / preparatory|preliminary to→準備 / further to→追伸 / in praise of→賛 / such as→如；for real→真 / in turn|full→順|全 / in succession|back to back→連続 / hand in hand→携 / head to head→直接 / long since→久 / right|just then→其時 / en route→途中 / by no means|in no way→決して / no|without doubt→疑無 / in some way|many ways→或様|多様 / at times|all times|random→時々|常時|乱。折り込み: out of nowhere|the blue→突 / excluding→除。 **cycle9**: abreast of→並 / cognizant|cognisant of→知 / mindful of→念 / fond|proud of→好|誇 / capable|incapable|worthy of→能|不能|値 / typical|indicative|suggestive|characteristic of→典型|示|示唆|特質 / rid|full of→撤|満 / composed|consisting|comprised of→構成 / for the duration of→期間；offshore→沖 / simultaneously|concurrently→同時 / respectively→各 / similarly|likewise→同様 / in particular→特 / so to speak|as it were→言わば / as such→斯 / once and for all→断 / currently|presently→現 / formerly|previously→旧 / alternately|alternatively→交互 / ever since→以来。折り込み: bereft of→欠 / afraid|scared of→恐 / conversely→逆 / thereupon|whereupon→其時。 **cycle10（予定最終）**: weary|ashamed|jealous|envious|empty of→厭|恥|嫉|空 / made of|from→製；ashore|overboard|underwater→岸|船外|水中 / nationwide|worldwide|globally→全国|世界 / clockwise|counterclockwise|anticlockwise→時計|反時計 / inside out|upside down→裏返|逆さ / backwards|backward|sideways→後方|横；en masse→一斉 / all along→当初 / ever|forever after→以後 / for keeps→永久 / off and on|on and off→断続 / through and through→徹底 / more often than not→大抵 / at a glance|at first glance|sight→一見 / at stake→賭 / in earnest|effect→本気|実質 / out of stock→品切。折り込み: vis-a-vis→vs / afterward→後 / as of yet→未 / first and foremost→最 / as a rule|in the main|for the most part→概 / as a whole→総 / in a nutshell→略 / in a row→連続 / at length→遂 / ad infinitum→∞ / considering→鑑。 **cycle11（半角スペース見送り埋め）**: as of→起 / for once→一度 / of late→近頃 / hitherto→従来 / thus far|to date→今迄 / under age|underage→年少 / one-on-one→1:1 / by and by→稍後 / anywhere→∃loc / nowhere→∅loc / anytime→∀時 / somewhat→稍；mutatis mutandis→準変 / ceteris paribus→他同 / sui generis→独自 / pari passu→同率 / ex officio→職権 / prima facie→一応 / ipso facto→当然 / a priori→先験 / de facto→d.f. / in situ→現場 / ad hoc→adhoc。折り込み: for good→∞ / somehow→或様。via/per/onto/upon・per se・hereof/thereby/hereto/herewith・so far は見送り。
- **prep compounds / legal（有限）**: `throughout`→`通`、`toward(s)`→`→`（← と対；助詞に/へ同面）。`hereinafter`→`∴↓` / `hereafter`·`henceforth`→`∴→` / `herein`→`∈` / `thereof`→`∴of` / `therein`→`∈it`（`∈there` は utf8 非勝利）/ `thereto`→`∴to` / `therewith`→`∴w/` / `whereby`→`∴by`。prep2 N は膨らませず `_SUBS`+台帳。`hereof`・`thereby`・`hereto`・`herewith`（there* / ∴ と意味衝突）は見送り。結果接続 hence/thus/accordingly→`∴`。譲歩 notwithstanding→雖（despite / in spite of の終端。in spite of・in lieu of 自体は prep 側）、albeit/although→tho。pursuant to / in accordance with は C `c-pursuant`→per と E `prep-in-accordance-with`→準 を併存（層別）。
- **whichever**→`∀opt`（`∀which` はレガシー展開のみ；`which` 残留なし）。
- **関係代名詞 / relative（関代）**: `which`→`that`（EN内; tok 2→1; `, which` と後置名詞ゲート; 疑問 which? / pied-pipe `in which` は除外）。`whom`→`who`。 Romance/DE 長形（lequel*/welcher*/el|la|los|las que）→`que`。 **bare q は出さない**（queue/question/数学と衝突）。 指示 that→eso・補文 that は既存ゲート維持（`that is`→i.e.；文頭/句読後 that→eso； bare `that`+be の deixis 食いは外し、関係 `N that BE` を保護）。 見送り: whose・lo que・関係 where/donde/où/wo（∀loc 族と衝突）。 台帳 `rel-which` / `rel-whom` / `rel-que`（breakdown=関代）。
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
