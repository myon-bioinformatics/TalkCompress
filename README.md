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
- 数字は `0-9`、必要なら `0-F`（16進）。数学記法も可
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

共通入口は `ConvoZip`。各層の詳細はサブディレクトリの README を参照。

```bash
uv sync
uv run python ConvoZip/convo_zip.py --layer 3 --text "as soon as possible"
uv run python ConvoZip/convo_zip.py --layer A --key 'shared' --text "hello bots"
uv run python ConvoZip/convo_zip.py --layer E --stats --text "私は ready and waiting"
uv run pytest -q
```

## ライセンス

MIT
