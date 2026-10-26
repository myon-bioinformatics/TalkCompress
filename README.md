# TalkCompress

会話の圧縮・省略化を目的とした実験リポジトリです。生成AIのコンテキスト節約や、MCP / チャット応答の短縮といった「減らす」工夫を、**読める相手のグラデーション**として拡張します。

Python 中心。stdlib 専用かどうかは未決定（厳しい制約は課しません）。単一ファイル寄りのモジュールから始めます。

## 圧縮の4層

| 層 | 読める相手 | ねらい |
| --- | --- | --- |
| 1 | 機械同士 | 共有鍵前提の強い符号化。人間非可読でよい |
| 2 | 機械 + 高度な人間 | 文単位で言語が切り替わる多言語（LTR優先） |
| 3 | 人間同士のギリギリ | スラング・略語・絵文字・「以降こう書く」型の規約 |
| 4 | 文内多言語・文法最小 | 1語/1字の高密度、接続詞的つなぎ、予測候補が少ない表現 |

層4の方針メモ:

- 中国語偏重は避ける。最短・予測負担が軽い表現を優先
- 日本語の短い表現や助数詞（匹・個など）は有用なら採用
- whatever / hereafter 系の「ほぼ1語」化も積極採用
- 性別名詞の重い体系は避け、中性寄りでコストを下げる
- 数字は `0-9`、必要なら `0-F`（16進、`--hex-nums`）。数学記法も可
- 層4は FILLER 除去・一意読み・語源寄せ（`shared/lex_policy.py`）。別サブプロジェクト F は当面なし

## サブプロジェクト（A–E）

| ID | 名前 | 主な担当 |
| --- | --- | --- |
| A | [Zipilogue](Zipilogue/) | 層1 — 機械同士の符号化・鍵付き往復 |
| B | [TesseraTalk](TesseraTalk/) | 層2 — 文単位の言語切替モザイク |
| C | [ShorthandLab](ShorthandLab/) | 層3 — スラング・略語・絵文字・規約辞書 |
| D | [ConvoZip](ConvoZip/) | 横断 — 入出力・層の切替・共通CLIの受け口 |
| E | [MorphoZip](MorphoZip/) | 層4 — 文内多言語・形態素/文法最小の圧縮 |

## 開発・CI

- Python は `uv` 管理（`uv.lock` をコミット）。`uv sync` のあと `uv run pytest`。
- CI は Aoi 寄り: `setup-uv`、pytest の JUnit を `build/test-results/`、親リポの reusable junit-identity。
- A–E の親は本リポ。真親 myon-bioinformatics への child 登録はしない。[docs/subprojects.md](docs/subprojects.md)

## 使い方

共通入口は `ConvoZip`。各層の詳細はサブディレクトリの README を参照。サンプルは [examples/](examples/)。

```bash
uv sync
uv run python ConvoZip/convo_zip.py --layer 3 --text "as soon as possible"
uv run python ConvoZip/convo_zip.py --layer A --key 'shared' --text "hello bots"
uv run python ConvoZip/convo_zip.py --layer E --stats --text "私は ready and waiting"

# パイプライン（層を順に適用）
uv run python ConvoZip/convo_zip.py --pipeline C,E --text "um thank you for your information"

# 予算: 既定 C,E を繰り返し、len<=N か縮小停止まで。最短結果を返す
uv run python ConvoZip/convo_zip.py --budget 40 --stats --text "um thank you for your information please"

# ヒューリスティック自動選択（B/C/E。鍵付きで --auto-machine なら末尾に A）
uv run python ConvoZip/convo_zip.py --auto --text "Hello. こんにちは。Thanks for your information."

# 役割別層（JSONL）。identity/skip は無変更。マルチ段は user=C+E
uv run python ConvoZip/convo_zip.py --jsonl --role-layers 'user=C,assistant=E,system=identity' \
  --file examples/sample_chat.jsonl

# 変換トレース（stderr JSON）
uv run python ConvoZip/convo_zip.py --pipeline C,E --trace --text "um thank you"

# 層の密度比較（JSON Lines）
uv run python ConvoZip/convo_zip.py --compare --text "I have 3 animals and 2 people"

# ファイル入出力 / Zipilogue AAD・環境変数鍵
uv run python ConvoZip/convo_zip.py --layer C --file in.txt --out out.txt
TALKCOMPRESS_ZIP_KEY=secret uv run python ConvoZip/convo_zip.py --layer A --aad chat --file plain.txt --out env.txt

# 語彙ポリシー上書き（プロセス内） / MorphoZip 16進・expand
uv run python ConvoZip/convo_zip.py --layer E --lex-policy policy.json --text "..."
uv run python MorphoZip/morpho_zip.py --mode expand --text "3匹"
uv run python MorphoZip/morpho_zip.py --hex-nums --text "retry 255 times"

# ShorthandLab 語彙エクスポート / hereafter 提案
uv run python ShorthandLab/shorthand_lab.py compress --text "..." --export-lexicon out.json
uv run python ShorthandLab/shorthand_lab.py suggest --text "continuous integration ... continuous integration"

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

## ライセンス

MIT
