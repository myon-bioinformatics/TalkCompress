# TalkCompress 絵文字・特殊文字 lookup 設計メモ

## 対象と結論

- 対象: public・非 archived の `myon-bioinformatics/TalkCompress`、main。
- 分析 HEAD: **`84e5dca0028d90db73254af33ac2d9d3ce545790`**。取得後 `git ls-remote origin refs/heads/main` と一致を確認。
- 作業日: 2026-11-07 JST。box の `/workspace/tc-emoji-5bot` のみで分析。禁止された既存 checkout、ユーザー PC は不使用。
- 実装、コミット、push、PR、外部投稿はなし。参照一覧のアップロードもこの担当では行っていない。
- **最もマージしやすい形: 参照用の詳細 JSON と、既存 `o200k_calib.json` の圧縮数値表を分離する。runtime は現行 `emoji_costs.ranges` / `vs16` を維持し、本当に必要になった列だけ任意の `sequences: {文字列: 整数cost}` として追加する。文字クラスを cost の代用にしない。**
- 今回の調査だけを取り込むなら docs/fixtures の参照一覧追加のみ。推定器変更は別の明示的な変更として評価する。表を足しただけで `☺` の既存結果が直るわけではない。
- **AI可読性: 未測定。** runtime 性能差、全 Unicode 絵文字網羅率、変換後の意味保存も未測定。

## 計測条件・再現資料

`estimate_tokens` と実 tokenizer を同じ入力で独立実行した。入力を tokenizer に渡す前に正規化・空白追加はしていない。先頭空白版は別カラム。

- Python 3.14.8 / Unicode database 16.0.0 / tiktoken 0.14.0 / `o200k_base`。
- スクリプト: `/workspace/tc-emoji-share/lookup-probe-5bot.py`
- 生結果: `/workspace/tc-emoji-share/lookup-probe-5bot.json`。`samples` と `adjacency_samples` に入力、分類、実測値を記録。単字表走査は集計と先頭の不一致例を記録しており、全不一致行の保存ではない。
- 再現: `uv run --no-project --with tiktoken==0.14.0 python /workspace/tc-emoji-share/lookup-probe-5bot.py`。追加の隣接測定結果は JSON の `adjacency_samples` に保存済み（この再実行はその追加カラムを再生成しない）。
- 回帰確認: `uv run --no-project --with pytest --with tiktoken==0.14.0 pytest -q -p no:cacheprovider tests/test_estimate_vs16.py tests/test_estimate_rare_chars.py tests/test_estimate_invisible_controls.py tests/test_estimate_unicode_boundaries.py tests/test_estimate_jamo_ivs.py tests/test_estimate_nfd.py tests/test_estimate_nfd_hangul.py tests/test_estimate_vi.py tests/test_estimate_unicode_ranges.py`
- 上記は **253 passed in 0.65s**。全テストではない。出力された agreement 集計は別の固定サンプルの既存 report-only 出力であり、本調査の網羅率ではない。
- 計測後の `git diff --exit-code` と `git status --short` は変更なし。

## 現行の分類器とコスト

中心は `TesseraTalk/tessera_talk.py` の `_PRETOKEN` (L510–554)、`estimate_tokens` (L835–975)。同名の別実装は検索で見つからない。`shared/ledger.py` はこの関数を参照する。

処理単位は **正規表現で分けた run と、その中のコードポイント／限定的な部分文字列**。grapheme cluster や見た目の一文字ではない。最初に NFC 化 (L868)、最後に `_nfd_extra` (L981–1002) で元の Latin 結合文字列・Hangul jamo の一部差分を加える。NFD 入力を単に NFC と同一費用にする仕様ではない。

以下は pretoken のクラス。`_wclass()` の `a/s/v/x/g/o` は**別階層の語フォールバック分類**なので混同しない。

| pretoken | 判定・範囲（コードに記載） | token 推定 |
|---|---|---|
| `i` | U+0900–097F、0980–0DFF、0E80–0FFF、1000–109F、1780–17FF の run。母音記号・virama も同じ run | `max(1, ceil(len(run) / _brahmic_rate(run[0])))`。先頭文字の固定ブロック別 rate |
| `c` | Thai U+0E00–0E7F | `_thai_cost`: 表の最長語から greedy、未一致はコードポイントごとに 1。直前空白は専用表がなければ追加 1 |
| `x` | 上記等を除いた `[^\W\d_]` の文字 run と Hebrew の指定 marks | `_script_factor_cost` があればそれ。なければ Hebrew/Arabic 指定 marks で分割し各片 `ceil(len/4)`、各 mark +1 |
| `o` | Cyrillic U+0400–04FF、Arabic U+0600–06FF、Greek U+0370–03FF / 1F00–1FFF | 語表・長さ表・script factor。Arabic marks は分割して片の語費用 + mark 数 |
| `w` | ASCII/Latin U+00C0–024F / 1E00–1EFF と U+0300–036F 結合文字、指定英語縮約 | `_word_cost` の大文字例外、一般例外、縮約、英単語表、長さ・接尾辞表、fallback の順。Vietnamese は空白と文全体判定あり |
| `d` | `\d{1,3}` | 1/run。ASCII 数字限定ではない |
| `k` | U+3400–9FFF / F900–FAFF / 3040–30FF / AC00–D7AF | CJK/kana/Hangul 多文字表の greedy 4/3/2、それ以外 1/字。先頭または直前空白の専用処理あり |
| `j` | Hangul jamo U+1100–11FF / A960–A97F / D7B0–D7FF、IVS U+E0100–E01EF | UTF-8 byte 数。NFC で合成される Hangul は末尾の補正も参照 |
| `b` | U+20000–323AF、F0000–10FFFF | UTF-8 byte 数 |
| `u` | 全角数字・英字 FF10–19 / FF21–3A / FF41–5A、FF61–9F、1D400–1D7FF | `_range_cost` の測定済み単字表。未登録は UTF-8 byte 数 |
| `t` | Ethiopic 1200–139F / 2D80–2DDF / AB00–AB2F | U+1380 未満は 2/字、それ以外 3/字、直前空白 +1 |
| `e` | 下記の emoji run 正規表現 | `_emoji_cost`: 表の 2 コードポイント key を優先し、残り単字。未知は UTF-8 byte 数 |
| `n` | NEL、NBSP、Ogham、line/paragraph separator、narrow NBSP、medium math space | `_COSTLY_WS_COST` の数値を加算 |
| `p` | `[^\w\s]` の連続。ただし keycap tail は止める | 通常 run 基本 1 + U+00A0 以上で `symbol_vocab` にない文字ごと +1。C0/DEL は各1、C1は各2の別式 (L967–970) |

これらの class そのものに UTF-8 **byte score** はない。上記の byte fallback は「byte 数を token 推定に使う」という意味。元入力の byte 数は `len(text.encode('utf-8'))` と独立。`shared/ledger.py` L372–389 / `shared/lex_policy.py` L763–774 は token → bit/UTF-8 → length → order の選択方針を持つので、同 token の表現を見た目の字数だけで評価してはならない。

### `i` の rate と語クラス

`_BRAHMIC_RATES` / `_brahmic_rate` (L66–87): Gurmukhi 1.75、Gujarati 2.5、Oriya 1.0、Telugu/Kannada 2.5、Sinhala 1.75、Lao 0.5、Tibetan 0.75、Myanmar 1.75、Khmer 1.5。それ以外の `i` は既定 3。docstring の Myanmar 一律 `ceil(2*len/3)` より**実コードの rate 表が優先**される。

`_wclass` (L642–654) は Greek=`g`、その他指定文字=`o`、Latin Extended Additional=`v`、Extended-A/B=`s`、ASCII=`a`、その他アクセント=`x`。`_fallback_cost` (L657–680) は `class+len` の表、Greek の近似、Latin Extended の加算など。Vietnamese は `_VI_SYLLABLE`、`_VI_RARE`、`vi_space_vocab` による専用費用があり、今回これを emoji 表へ統合する理由はない。

### Unicode category と tokenizer

`unicodedata.category()` で「絵文字」「結合文字」を包括判定してはいない。NFC と固定範囲、Python `re` の `\w/\d/\s`、文字列の `isascii` 等で決まる。このため category `So` でも `p` にも `e` にもなり得る。`\w/\d/\s` の詳細は Python Unicode 定義にも依存する。

runtime は stdlib-only の近似器。tiktoken は校正・検証時だけ。`scripts/calibrate_estimate.py` は `o200k_base` を使い、互換性比較の `scripts/tokenizer_compat.py` は `o200k_base` と `cl100k_base` 等を別途扱う。`estimate_tokens` が backend を切り替える設計ではない。

## 既存の機械可読表

- `TesseraTalk/fixtures/o200k_calib.json` を `_load_calib` (L683–713) が lazy-load。生成元は `scripts/calibrate_estimate.py --write`。ファイルの notes は手編集禁止を明記する。
- `emoji_costs`: `ranges: [[start整数, costの数字列], ...]` と `vs16: 文字列`。今回展開結果は単字 **5597**、2文字 key **2**、合計 **5599**。対象範囲には emoji でない数学記号等も含まれるので「5597 emoji」と呼ばない。
- 範囲: U+2190–2BFF、U+200D、U+FE0F、U+1F000–1FAFF、U+E0020–E007F と、© ® ‼ ⁉ ™ ℹ 〰 〽 ㊗ ㊙。generator は孤立コードポイントの o200k cost を測り `min(cost, 9)` で 1 桁にする (L149–165)。
- `_unpack_emoji` (L734–744) は各単字を `str -> int` に展開。現在の `vs16` は **`❤` のみ**で `❤️: 1` を作る。さらに `FE0F+20E3: 1`、裸の `20E3: 1` を追加。2文字 key は `❤️` と keycap tail。
- `symbol_vocab` → `cal['sym']`: **128** 文字。`scripts/calibrate_estimate.py` の `symbol_vocab` (L80–93) は **先頭空白を付けて単一 token になる**非 ASCII・非英数字・非空白を採取。孤立単字の表とは測定文脈が異なる。
- `_FULLWIDTH_COSTS` / `_HALFWIDTH_COSTS` / `_MATH_ALNUM_COSTS` (L573–612): それぞれ **94 / 63 / 1024** 桁の単字費用表。全角記号も表自体は持つが、`u` 分岐は全角英数字等のみなので表にある全字が必ずこの経路を通るわけではない。
- `_COSTLY_WS_COST` (L819–830): NEL=2、NBSP=1、Ogham=3、line separator=1、paragraph separator=2、narrow NBSP=1、medium math space=2。
- その他 `en_costs`、`exceptions`、`exceptions_cased`、`contractions`、`len_table`、`suffixes`、`suffix_floor`、`cjk_vocab`、`cjk_space_vocab`、`thai_vocab`、`thai_space_vocab`、`vi_space_vocab`。語表と絵文字単字表は別責務。

## 列・結合の扱い

- **VS16**: text-default 対象記号 + FE0F を `e` へ入れる。`❤️` は2字 key で1、`☺️` は単字 `☺=1` + `FE0F=1` で2。孤立 FE0F は `p` になり2。
- **VS15**: FE0E は `e` の範囲にない。`☺︎` 全体は `p`、`👍︎` は `e` + `p`。表示指定を消してよいという規則ではない。
- **ZWJ**: U+200D が `e` を成立させる。家族等を単一 grapheme として数えず、各部品の費用を加算。Sinhala 内の単独 ZWJ、および Lao/Khmer 内 ZWSP だけは `_same_block_fragments` による限定的な割引がある (L880–887)。emoji 内 ZWJ は割り引かない。
- **肌色**: U+1F3FB–1F3FF は U+1F000–1FAFF の一部として単字表から加算。独立した Fitzpatrick 判定はない。
- **国旗**: regional indicator は同じ補助平面範囲の `e`。2字ペアを国コードとして検証・一体化しない。片側だけでも費用が付く。
- **keycap**: 先頭数字は `d`、`#/*` は `p`、FE0F?+20E3 は `e`。現行表を full `1️⃣` key に変えるだけでは到達せず、逆に既存尾部を足すと二重計上になり得る。
- **tag sequence**: E0020–E007F は emoji run 内なら単字表を加算。旗+タグ列は実測一致例あり。しかし tag のみでは ZWJ/補助平面 emoji の anchor を満たさず `p` へ落ちる。
- **結合文字**: Latin 0300–036F は `w` に入り NFC 後の残存 marks を加算。stacked marks は追加加算。Hebrew/Arabic は `_SCRIPT_MARKS_RE` で分割。Indic は符号を含む run の長さ近似。Unicode 全域の mark を一律処理する仕組みはない。
- **IVS / Hangul**: E0100–E01EF は `j` で4 byte相当/字。Hangul syllable は `k`、分解 jamo は NFC と `_nfd_extra` の補正対象。emoji tag E0020–E007F と IVS を同じ範囲扱いにしない。
- **CJK/Thai/Vietnamese**: 既存の語 greedy / 空白条件 / NFD 補正を維持。表を grapheme 一律費用にするとこれらの区切りや既存選択順位を変えてしまう。

## 代表入力の今回実測

`E` は main の推定、`T` は生入力の o200k 実測。`sp E/T` は先頭に ASCII 空白を1個付加した別入力。分類は NFC 後、byte数は元入力。表の範囲は代表例であり全絵文字一覧ではない。

| 入力（不可視文字は escape） | pretoken | E | T | sp E/T | UTF-8 bytes |
|---|---|---:|---:|---|---:|
| `!?+$` | `p` | 1 | 2 | 1/3 | 4 |
| `___` | `一致なし` | 0 | 1 | 0/1 | 3 |
| `☺` | `p` | 2 | 1 | 2/2 | 3 |
| `\u263a\ufe0f` | `e` | 2 | 2 | 2/3 | 6 |
| `\u263a\ufe0e` | `p` | 3 | 2 | 3/3 | 6 |
| `☹` | `p` | 2 | 2 | 2/2 | 3 |
| `\u2639\ufe0f` | `e` | 3 | 3 | 3/3 | 6 |
| `❤` | `p` | 1 | 1 | 1/1 | 3 |
| `\u2764\ufe0f` | `e` | 1 | 1 | 1/1 | 6 |
| `→` | `p` | 1 | 1 | 1/1 | 3 |
| `→→` | `p` | 1 | 2 | 1/2 | 6 |
| `☺☺` | `p` | 3 | 2 | 3/3 | 6 |
| `©` | `p` | 1 | 1 | 1/1 | 2 |
| `\xa9\ufe0f` | `e` | 2 | 2 | 2/2 | 5 |
| `™` | `p` | 1 | 1 | 1/1 | 3 |
| `\u2122\ufe0f` | `e` | 2 | 2 | 2/2 | 6 |
| `∴` | `p` | 2 | 2 | 2/2 | 3 |
| `✅` | `p` | 1 | 1 | 1/1 | 3 |
| `\u2600\ufe0f` | `e` | 3 | 3 | 3/3 | 6 |
| `\ufe0e` | `p` | 2 | 1 | 2/2 | 3 |
| `\ufe0f` | `p` | 2 | 1 | 2/2 | 3 |
| `\u200d` | `e` | 1 | 1 | 1/1 | 3 |
| `\u200c` | `p` | 1 | 1 | 1/1 | 3 |
| `e\u0301` | `w` | 2 | 2 | 2/2 | 3 |
| `x\u0301` | `w` | 2 | 2 | 2/2 | 3 |
| `x́̂` | `w` | 5 | 3 | 5/3 | 5 |
| `\u0301` | `p` | 2 | 1 | 2/2 | 2 |
| `👍` | `e` | 1 | 1 | 1/1 | 4 |
| `👍🏽` | `e` | 3 | 3 | 3/3 | 8 |
| `🏽` | `e` | 2 | 2 | 2/3 | 4 |
| `👨‍👩‍👧‍👦` | `e` | 11 | 11 | 11/11 | 25 |
| `👩🏽‍💻` | `e` | 7 | 7 | 7/7 | 15 |
| `🧑🏽‍💻` | `e` | 8 | 8 | 8/8 | 15 |
| `❤️‍🔥` | `e` | 3 | 3 | 3/3 | 13 |
| `🏳️‍🌈` | `e` | 6 | 6 | 6/7 | 14 |
| `🇯🇵` | `e` | 4 | 4 | 4/4 | 8 |
| `🇺🇸` | `e` | 4 | 4 | 4/4 | 8 |
| `🇯` | `e` | 2 | 2 | 2/2 | 4 |
| `1️⃣` | `d+e` | 2 | 2 | 2/3 | 7 |
| `1⃣` | `d+e` | 2 | 2 | 2/3 | 4 |
| `#️⃣` | `p+e` | 2 | 2 | 2/2 | 7 |
| `*️⃣` | `p+e` | 2 | 2 | 2/2 | 7 |
| `12️⃣` | `d+e` | 2 | 2 | 2/3 | 8 |
| `🏴 + tag(gbeng) + CANCEL TAG` | `e` | 26 | 26 | 26/27 | 28 |
| `\U000e0067` | `p` | 2 | 4 | 2/5 | 4 |
| `葛󠄀城` | `k+j+k` | 7 | 6 | 7/7 | 10 |
| `한국어` | `k` | 2 | 2 | 2/2 | 9 |
| `한국어` | `k` | 24 | 24 | 24/25 | 24 |
| `ภาษาไทย` | `c` | 2 | 2 | 2/2 | 21 |
| `Tiếng Việt` | `w+w` | 3 | 3 | 3/3 | 14 |
| `Tiếng Việt` | `w+w` | 9 | 8 | 9/8 | 18 |
| `שלום` | `x` | 1 | 1 | 1/1 | 8 |
| `مَرْحَبًا` | `o` | 9 | 6 | 9/6 | 18 |
| `क़` | `i` | 1 | 2 | 1/2 | 6 |
| `क्ष` | `i` | 1 | 1 | 1/1 | 9 |
| `ක‍ක` | `i+e+i` | 2 | 3 | 2/3 | 9 |
| `☻` | `p` | 2 | 2 | 2/2 | 3 |
| `☃` | `p` | 2 | 2 | 2/2 | 3 |
| `✈` | `p` | 2 | 2 | 2/2 | 3 |
| `⚠` | `p` | 2 | 2 | 2/2 | 3 |
| `⬆` | `p` | 2 | 2 | 2/3 | 3 |
| `♻` | `p` | 2 | 2 | 2/2 | 3 |
| `✔` | `p` | 1 | 1 | 1/1 | 3 |
| `✖` | `p` | 2 | 2 | 2/2 | 3 |
| `🔟` | `e` | 2 | 2 | 2/2 | 4 |
| `🫩` | `e` | 3 | 3 | 3/3 | 4 |


## 確認できたギャップ・注意点

### ☺ の 2 vs 1 は再現。VS16 不足ではなく経路差

`estimate_tokens("☺")=2` / `o200k("☺")=1` / `_emoji_cost("☺", cal['emoji'])=1`。単字表には既に正しい費用がある。だが孤立 `☺` は `p`、`symbol_vocab` にはなく基本1+追加1になる。先頭空白を付けた実入力 `" ☺"` は o200k=2 なので、現状はその文脈では合う。

`tests/test_estimate_vs16.py` L35–38 はこの2を**意図的に固定**し、単字表を記号全般へ適用した過去の一致率低下をコメントしている。その過去割合は今回再測定していないので採否根拠として再利用せず、変更するなら固定コーパスで再評価する。`☺️` は推定2/実測2なので、`☺` と同一 key に正規化してはならない。

### 表の欠落と「表に到達しない」を分ける

既存 emoji 展開表の全単字 **5597** を孤立入力で走査したところ、推定と o200k の不一致は **1566**、その経路は `p=1458`、`x=108`。これは**既存表範囲の測定**であり、Unicode emoji に限定した不一致率ではない。

例: `∀`、`∆`、`∞` は推定2/実測1、`⍀` は2/3。`e` 対象の広い範囲には数学記号や文字も含まれ、`x` が `e` より後でも `e` の anchor を満たさない文字は `x` へ行く。新しいデータを大量に足してもこの経路差は解消しない。

### 文脈・隣接依存

- `→→`: `p` 全体で推定1/実測2。記号 run を単字和に変えると既存意味（費用モデル）が変わる。
- `!👍`: `p` が全体を消費し推定1/実測2。一方 `👍!` は `e+p` で2/2。`©👍` も1/2。**emoji 表の拡充だけでは直らない tokenizer 境界問題**。
- `☺👍`: `e` が広い prefix を含み全体を取るため2/2。孤立 `☺` と分岐が異なる。
- `ok ☺️`: 推定3/実測4、`🏳️‍🌈` は裸6/6だが先頭空白版6/7。孤立表から空白文脈の token 数は決められない。
- `☺︎`: 3/2、孤立 FE0F: 2/1、孤立 FE0E: 2/1、`👍︎`: 3/2。VS15 の専用計測・経路はない。
- 孤立 tag U+E0067: 2/4。旗についた tag(gbeng) 列: 26/26。
- `x́̂`: 5/3。`Tiếng Việt`: 9/8。NFC/NFD と marks の費用は近似であり、見た目の一文字化では解決しない。
- `葛`+IVS+`城`: 7/6。`क़`: 1/2。Arabic `مَرْحَبًا`: 9/6。隣接 script の近似も残っているが emoji 表改修とは分離すべき。
- `_` / `___` は `_PRETOKEN` のどの枝にも入らず推定0、o200k=1。ASCII 特殊文字にも未捕捉がある。emoji 探索に混ぜて全 classifier を置換しない。

## 推奨 lookup の形

### 参照用（アップロードする全一覧）

詳細な根拠は runtime の圧縮表へ埋め込まず、UTF-8 JSON の `meta` と `rows`（大きければ JSONL + metadata JSON）として保存する。入力文字列を一次 key にし、コードポイント列を監査用にも保存。同一文字列でも `context` が異なれば別記録とする。NFC/NFD、FE0E/FE0F、ZWJ、肌色、tag は**削除・統合しない**。

```json
{
  "meta": {
    "head": "84e5dca0028d90db73254af33ac2d9d3ce545790",
    "encoding": "o200k_base",
    "tiktoken": "0.14.0",
    "ai_readability": "未測定"
  },
  "rows": [
    {"text": "☺", "codepoints": ["U+263A"], "context": "bare",
     "estimate": 2, "measured_tokens": 1, "utf8_bytes": 3,
     "pretokens": [["p", "☺"]]},
    {"text": " ☺", "codepoints": ["U+0020", "U+263A"], "context": "leading-space",
     "estimate": 2, "measured_tokens": 2, "utf8_bytes": 4,
     "pretokens": [["p", "☺"]]}
  ]
}
```

必要な属性: 測定日時(JST)、出典 Unicode release/URL とデータファイル hash、tool version、元入力、正規化後入力、context/実際の全文、pretoken span/クラス、推定値、実測値、byte数、gap、測定不能理由。未実施の metric は `null` と理由 `未測定` にする。RGI列/非RGI列の区別と実際の対応範囲も記載する。クラス文字は説明用であり token cost の代用品にしない。

### runtime（既存 JSON の局所拡張）

`o200k_calib.json` の既存 `emoji_costs` をそのまま使う。必要な場合だけ任意の `sequences` を追加。key は **正確なコードポイント列を含む Python/JSON 文字列**、value は **非負ではなく正の整数 token cost**。class や byte 数や説明はここに入れない（byte 数は入力から算出できる）。既存の単字表は範囲圧縮、列だけ sparse dict。将来9を超える費用の列も dict の整数なら桁制限がない。

以下は形の例。`👩🏽‍💻: 7` は今回測定済みだが、現行和と同値なので**今追加する必要はない**。

```json
{
  "ranges": [[128077, "1"]],
  "vs16": "❤",
  "sequences": {"👩🏽‍💻": 7}
}
```

これは全既存表を置換する JSON ではなく shape の抜粋。生成元 `scripts/calibrate_estimate.py` を更新してから再生成する。巨大な全文再校正による無関係な差分は避ける。

`_unpack_emoji` の既存展開末尾に、入力検査後の sparse override を追加する程度で済む。

```python
# _unpack_emoji: existing ranges / vs16 / keycap entries are kept.
out.update(d.get("sequences", {}))
```

現在 `_emoji_cost` は **2字しか検索しない**ので、長い key を入れる場合は最長長さを loader で求め、各位置で最長一致→単字→UTF-8 byte fallback にする。既存 Thai の `th_max` 方式 (L707–709、761–788) に寄せられる。新規依存や正規表現の巨大 alternation は不要。最長一致は近似の決定規則であり BPE の完全再現を保証しない。

重要な制約:

1. `_PRETOKEN` が返した **`e` run 内だけ**を消費する。列の cost を使ったらその列全体を一度だけ進め、VS16/ZWJ/肌色の個別費用を再加算しない。
2. FE0F を global に zero-cost にしない。`❤️=1` でも `☺️=2`。FE0E を FE0F の別名にしない。
3. keycap は既存 tail key を維持。full `1️⃣` を runtime key にするなら `d/p` と `e` をまたぐ再設計が必要で、今回の最小変更には入れない。
4. `p` に孤立 `☺` の費用を反映したければ**別設計**。例えば run 全体の完全一致に限る専用 `symbol_run_costs` と先頭空白条件の別表なら影響範囲を明示できるが、それでも測定済み文脈だけの近似。`cal['emoji']` の存在を理由に `p` 全域を単字和にしない。
5. 入力は estimate 内で NFC 化される。新しい runtime key は NFC 不変の列に限定・検証し、raw NFD の測定記録とは分ける。正規化で同 key になる別費用行は拒否し、`_nfd_extra` を迂回しない。
6. 参照一覧にある全ての Unicode 列を runtime に自動採用しない。既存 `e` に到達しない列はデータだけでは反映されない。未知/unassigned の broad-range 文字と RGI emoji も分ける。
7. `sequences` の key 空文字・空白・非文字列、value の bool/非整数/0以下、既存 key の矛盾を generator/テストで検査。JSON の重複 key は通常 load で消えるため、生成前に一意性を検査する。

## 他の形を採らない理由

| 案 | 問題 |
|---|---|
| `codepoint -> i/c/x/o` だけ | run 分岐と語表は単字属性で決まらず、列と文脈費用も表せない。emoji はそもそも主に `e/p` |
| codepoint -> cost だけで全記号を置換 | 既存表で既に到達問題あり。VS16 ペア、keycap tail、句読点 run、先頭空白の費用を失う |
| 全 grapheme -> 1 | BPE token は見た目と一致しない。家族11、旗4など測定に反する |
| NFC で参照 key を統合 | raw NFD の実測差を消す。FE0F 等の削除は表示意味も変え得る |
| Python 巨大 dict の直書き | runtime 本体の差分と校正データの差分が混在。既存 JSON lazy-load を再利用できない |
| import 時に別 JSON を全件ロード | 既存 lazy-load と二重管理。文脈付き参照一覧を runtime に不要に持ち込む |
| 文字の frozen set のみ | `symbol_vocab` のような二値特性には向くが可変数値や複合列費用を表せない |
| runtime に tiktoken / grapheme 依存追加 | stdlib-only の既存契約と異なる。測定専用依存としては既に使える |
| 全 Unicode emoji 列を regex に展開 | 重複/境界の管理と差分が大きい。未知文字 fallback も別途必要 |

## 後続マージ案

1. **参照一覧を先に**: 他担当の網羅データを上の詳細形式に統合。meta に版/測定条件/網羅範囲を必須化。今回の既存表走査を「全絵文字検証」と呼ばない。AI可読性は未測定のまま。
2. **必要なら runtime を局所拡張**: `emoji_costs.sequences` → `_unpack_emoji` → 最長一致 `_emoji_cost`。列の差が測定で見つからなければ追加しない。既存単字/VS16/keycap を動かさない段階は既存推定結果完全一致を確認できる。
3. **境界変更は別に評価**: `☺` の `p` 経路、VS15、孤立 tags、`!👍`、underscore はデータ追加と分離。`p` の変更を含めれば「意味変更なし」とは言わず、採用表現の順位変動も計測する。
4. テストは `test_estimate_vs16.py`、`test_estimate_rare_chars.py`、`test_estimate_invisible_controls.py`、`test_estimate_unicode_boundaries.py` を維持。`☺` の2を変える場合だけ、その意図・空白文脈を明記して期待値変更。`test_estimate_jamo_ivs.py`、`test_estimate_nfd*.py`、`test_estimate_unicode_ranges.py`、`test_estimate_vi.py` も回帰対象。
5. 新規列には表loaderの後方互換・未知fallback・最長重複prefix・tail二重計上防止・bare/space/語中/句読点前後を固定テスト化。肌色、RI単独/ペア、VS15/VS16、孤立/連結tag、keycap tail のすべてを含める。
6. ミュータントは「最長一致を単字和へ」「列消費後にも部品加算」「VS16一律無料」「ZWJ無料」「keycap tail二重加算」「`p` に全表を適用」「全NFDをNFCと同一費用」を落とすテストを用意。今回この変更のミュータント試験は未実施。
7. `uv run pytest` と、固定コーパスで before/after の tokens・UTF-8 bytes・候補順位/勝者変化・実行時間を測る。今回その変更後比較、速度差、AI可読性は **未測定**。

## 引用先

全コード参照は上記 HEAD のもの。GitHub URL の `blob/84e5dca0028d90db73254af33ac2d9d3ce545790/` 以下で固定可能。

- `TesseraTalk/tessera_talk.py`: 分類、校正表展開、費用、NFD補正。
- `TesseraTalk/fixtures/o200k_calib.json`: 現行費用表。
- `scripts/calibrate_estimate.py`: 先頭空白 symbol 表と孤立 emoji 単字表の異なる生成条件。
- `scripts/gen_unicode_range_costs.py`: 全角・半角・数学文字単字費用生成。
- `tests/test_estimate_vs16.py`: 孤立 `☺=2` を意図的に維持する回帰。
- `tests/test_estimate_rare_chars.py` / `test_estimate_invisible_controls.py`: emoji列、keycap、tag fallback、script control の回帰。
- `TesseraTalk/README.md` L52–65: 近似器であること、過去の著者報告と独立検証の区別。

**AI可読性: 未測定。**
