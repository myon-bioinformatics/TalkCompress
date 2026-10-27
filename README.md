# TalkCompress

会話の圧縮・省略化を目的とした実験リポジトリです。生成AIのコンテキスト節約や、MCP / チャット応答の短縮といった「減らす」工夫を、**読める相手のグラデーション**として拡張します。

Python 中心。stdlib 専用かどうかは未決定（厳しい制約は課しません）。単一ファイル寄りのモジュールから始めます。

## 圧縮の4層

| 層 | 読める相手 | ねらい |
| --- | --- | --- |
| 1 | 機械同士 | 共有ルール台帳でスラング的に短縮（鍵付き封筒は任意）。人間非可読でよい |
| 2 | 機械 + 高度な人間 | 文単位で言語が切り替わる多言語（LTR優先） |
| 3 | 人間同士のギリギリ | スラング・略語・絵文字・「以降こう書く」型の規約 |
| 4 | 文内多言語・文法最小 | 1語/1字の高密度、接続詞的つなぎ、予測候補が少ない表現 |

層4の方針メモ:

- 中国語偏重は避ける。最短・予測負担が軽い表現を優先
- 日本語の短い表現や助数詞（匹・個など）は有用なら採用
- whatever / hereafter 系の「ほぼ1語」化も積極採用
- 性別名詞の重い体系は避け、中性寄りでコストを下げる
- 数字は `0-9`、必要なら `0-F`（16進、`--hex-nums`）。数学記法も可
- 層3（C）が FILLER 除去・UNIQUE_COMPACT・I'll・スペル数字・合意台帳 lex。層4（E）は一意読み（長い形）・語源寄せ（ℹ️）・文法最小（`shared/lex_policy.py`）。D は **DensityZip**（横断オーケストレーション + density 指標ファサード）。 A Zipilogue / D DensityZip / E MorphoZip は別物（単独「Zip」は使わない）。F は当面なし

## サブプロジェクト（A–E）

| ID | 名前 | 主な担当 |
| --- | --- | --- |
| A | [Zipilogue](Zipilogue/) | 層1 — 共有ルール台帳＋任意の鍵付き封筒 |
| B | [TesseraTalk](TesseraTalk/) | 層2 — 文単位モザイク + 翻訳トークン最短（Romance/Germanic/Greek + JA/ZH） |
| C | [ShorthandEdge](ShorthandEdge/) | 層3 — スラング・略語・絵文字・規約・FILLER・UNIQUE_COMPACT・I'll・スペル数字・**合意台帳** |
| D | [DensityZip](DensityZip/) | 横断 — 入出力・層切替・共通CLI + **density** 指標ファサード（台帳は持たない; Zipilogue/MorphoZip とは別） |
| E | [MorphoZip](MorphoZip/) | 層4 — 文内多言語・文法最小・ℹ️・冠詞・助数詞（フィラー除去は既定オフ） |

## 開発・CI

- Python は `uv` 管理（`uv.lock` をコミット）。`uv sync` のあと `uv run pytest`。
- CI は Aoi 寄り: `setup-uv`、pytest の JUnit を `build/test-results/`、親リポの reusable junit-identity。
- A–E の親は本リポ。真親 myon-bioinformatics への child 登録はしない。[docs/subprojects.md](docs/subprojects.md)

## 使い方

共通入口は `DensityZip`（`uv run python DensityZip/density_zip.py ...`）。 Zip 系は **Zipilogue (A)** / **DensityZip (D)** / **MorphoZip (E)** をフルネームで区別。 各層の詳細はサブディレクトリの README を参照。サンプルは [examples/](examples/)。

```bash
uv sync
uv run python DensityZip/density_zip.py --layer 3 --text "as soon as possible"
uv run python DensityZip/density_zip.py --layer A --key 'shared' --text "hello bots"
# A 共有ルール台帳（鍵なしでも可。頻出フレーズが r1… に育つ）
uv run python Zipilogue/zipilogue.py rule-sim --state /tmp/book.json --threshold 3 --text $'ready and waiting\nready and waiting\nready and waiting\nready and waiting'
uv run python DensityZip/density_zip.py --layer A --rule-state /tmp/book.json --text "ready and waiting"
uv run python DensityZip/density_zip.py --layer E --stats --text "私は ready and waiting"

# パイプライン（層を順に適用）
uv run python DensityZip/density_zip.py --pipeline C,E --text "um thank you for your information"

# 予算: 既定 C,E を繰り返し、len<=N か縮小停止まで。最短結果を返す
uv run python DensityZip/density_zip.py --budget 40 --stats --text "um thank you for your information please"

# ヒューリスティック自動選択（B/C/E。鍵付きで --auto-machine なら末尾に A）
uv run python DensityZip/density_zip.py --auto --text "Hello. こんにちは。Thanks for your information."

# 役割別層（JSONL）。identity/skip は無変更。マルチ段は user=C+E
uv run python DensityZip/density_zip.py --jsonl --role-layers 'user=C,assistant=E,system=identity' \
  --file examples/sample_chat.jsonl

# 変換トレース（stderr JSON）
uv run python DensityZip/density_zip.py --pipeline C,E --trace --text "um thank you"

# 層の密度比較（JSON Lines）
uv run python DensityZip/density_zip.py --compare --text "I have 3 animals and 2 people"

# ファイル入出力 / Zipilogue AAD・環境変数鍵
uv run python DensityZip/density_zip.py --layer C --file in.txt --out out.txt
TALKCOMPRESS_ZIP_KEY=secret uv run python DensityZip/density_zip.py --layer A --aad chat --file plain.txt --out env.txt

# 語彙ポリシー上書き（プロセス内） / MorphoZip 16進・expand
uv run python DensityZip/density_zip.py --layer E --lex-policy policy.json --text "..."
uv run python MorphoZip/morpho_zip.py --mode expand --text "3匹"
uv run python MorphoZip/morpho_zip.py --hex-nums --text "retry 255 times"

# ShorthandEdge 語彙エクスポート / hereafter 提案
uv run python ShorthandEdge/shorthand_edge.py compress --text "..." --export-lexicon out.json
uv run python ShorthandEdge/shorthand_edge.py suggest --text "continuous integration ... continuous integration"

# TesseraTalk 段落保持 / Zipilogue 複数フレーム
uv run python TesseraTalk/tessera_talk.py compress --preserve-newlines --text $'Hello.\n\nこんにちは。'
uv run python Zipilogue/zipilogue.py encode --key k --frames --text $'line1\nline2'

uv run pytest -q
```

### `--auto` の目安

| 入力の傾向 | 選ばれやすい層 |
| --- | --- |
| ASCII スラング・略語寄り | `C` → 必要なら `E` |
| 複数スクリプト / 多文の混在 | `B` → 必要なら `E` |
| 短い / CJK 密度高め | `E` |
| `--auto-machine` + 鍵あり | 末尾に `A`（暗号化は明示時のみ） |


### Round-3 追加

```bash
# スライディング窓（JSONL）: 圧縮後に末尾 N 件。--keep-system で system は落とさない
# --window と --budget 併用時: 先に行ごと圧縮 → window → さらに古い行から budget まで削除
uv run python DensityZip/density_zip.py --pipeline C,E --jsonl --window 3 --keep-system \
  --file examples/window_chat.jsonl

# 名前付きプロファイル（CLI が上書き）。profiles/mcp-short.json など
uv run python DensityZip/density_zip.py --profile mcp-short --text "um thank you for your information"
uv run python DensityZip/density_zip.py --profile chat-mosaic --text "Hello. こんにちは。"

# 品質ゲート（既定は非厳格）。shrink 不足で終了コード 1。--allow-weak で警告のみ
uv run python DensityZip/density_zip.py --layer C --min-ratio 0.5 --text "xyzzy" || true

# ドメインパック / 保護スパン（[[keep:...]] はラッパ除去・中身そのまま）
uv run python DensityZip/density_zip.py --layer C --pack mcp --pack dev --text "model context protocol"
uv run python DensityZip/density_zip.py --layer E --text '[[keep:thank you for your information]] please'

# Zipilogue 鍵指紋（鍵自体は出さない） / encode dry-run
uv run python DensityZip/density_zip.py --fingerprint-key --key 'shared'
uv run python Zipilogue/zipilogue.py fingerprint --key 'shared'
uv run python Zipilogue/zipilogue.py encode --key k --dry-run --stats --text hello

# 語彙ポリシー差分
uv run python shared/lex_policy.py --diff other_policy.json
```

### Round-4 追加

```bash
# A: RuleBook の export / import / threshold / 複数ピア交渉マージ
uv run python Zipilogue/zipilogue.py rule-export --state book.json --export /tmp/rules.json
uv run python Zipilogue/zipilogue.py rule-import --state book.json --import /tmp/peer.json
uv run python Zipilogue/zipilogue.py rule-threshold --state book.json --threshold 2
uv run python Zipilogue/zipilogue.py rule-negotiate --state book.json --import /tmp/p1.json --peer /tmp/p2.json

# B: 翻訳トークン最短をハブ経由（D は配線のみ）
uv run python DensityZip/density_zip.py --layer B --translate-min --text "Good morning. See you later."

# C: 台帳（左右・前後・接続詞英語短形）/ chat パック
uv run python ShorthandEdge/shorthand_edge.py compress --text "check left and right" --pack chat

# E: 助数詞（台・棟・杯…）・e.g./i.e.・スマート引用符の冠詞保持
uv run python MorphoZip/morpho_zip.py --text "I have 3 cars for example"
```

### Zipilogue RuleBook（A）

送受信が同じ JSON 台帳をロードし、宣言（`rule: long => short`）や反復観察で短いトークンを育てます。暗号封筒は `--key` があるときだけ巻きます。詳細は [Zipilogue/README.md](Zipilogue/README.md)。

```bash
uv run python Zipilogue/zipilogue.py rule-declare --state book.json --long 'status update complete' --short r1
uv run python Zipilogue/zipilogue.py rule-observe --state book.json --text 'status update complete please'
uv run python Zipilogue/zipilogue.py rule-encode --state book.json --text 'status update complete'
```

## ライセンス

MIT
