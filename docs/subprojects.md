# サブプロジェクト（A–E）と git subtree

TalkCompress は A–E（+ 共有推定器 TokenCostHeuristic）の**親**です。将来まとめて切り出すときは Aoi の子リポと同様に `git subtree` で同期する想定です。いまは独立しそうにないので、同一リポ内のディレクトリのまま進めます。

| ID | 表示名（旧名） | ディレクトリ / モジュール | 役割 |
| --- | --- | --- | --- |
| A | **RulePeerCodec**（旧 Zipilogue） | `RulePeerCodec/rule_peer_codec.py` | 1 機械同士: 動的共有ルール（observe / `--peer` / `encode_with_rules`・`decode_with_rules`）+ 任意封筒 |
| B | **SentenceCalibratedMosaic**（旧 TesseraTalk） | `SentenceCalibratedMosaic/sentence_calibrated_mosaic.py` | 2 文単位の言語モザイク + 翻訳候補選択（TranslationSelector は B 内部の関数群で、独立した表示名ではない） |
| — | **TokenCostHeuristic**（新設） | `TokenCostHeuristic/token_cost_heuristic.py` | 共有トークン推定器 `estimate_tokens` と `fixtures/o200k_calib.json`・`fixtures/en_wordlist.txt`。全ユニットはここから import する（旧来の B 本体への逆依存を解消） |
| C | **ShorthandSessionEdge**（旧 ShorthandEdge） | `ShorthandSessionEdge/shorthand_session_edge.py` | 3 人間ギリギリ: 登録済み lex（合意台帳はここ）+ Session |
| D | **DensityFacadeRoute**（旧 DensityZip） | `DensityFacadeRoute/density_facade_route.py` | 入口・配線・会話 I/O + **density** 指標ファサード（圧縮層ではない） |
| E | **MorphoGrammarMinimal**（旧 MorphoZip） | `MorphoGrammarMinimal/morpho_grammar_minimal.py` | 4 文内の閉じた品詞形態論 + 文法最小の書き換え |

### 名前について

各ユニットは 3 語の表示名で呼ぶ。散文で単独の「Zip」は使わない。D の `--layers` は互換のため旧名（`zipilogue` / `tessera` / `tessera_talk` / `shorthand_edge` / `density_zip` / `densityzip` / `morpho_zip`）も入力別名として受け付ける。

RulePeerCodec の封筒は改名に合わせて破壊的に変更した（マジック `RPC1`、KDF ソルト `TalkCompress/RulePeerCodec/v1`）。旧形式の封筒は復号できない。鍵の入力は `--key` / `--key-file` のみで、環境変数の鍵入力は廃止した。リポジトリ名 TalkCompress とパッケージ名 `talk-compress` も変更しない。

## 真親への登録はしない

[myon-bioinformatics/myon-bioinformatics](https://github.com/myon-bioinformatics/myon-bioinformatics) の `child-heads.json` / vendor-consumers などには**載せません**。共有ワークフロー（change-detection・junit-identity）は `uses:` で親リポの SHA にピン留めするだけです。

## 後から切るとき（メモ）

Aoi の [child-repositories.md](https://github.com/myon-bioinformatics/Aoi/blob/main/docs/child-repositories.md) と同じ系統:

1. `git subtree split --prefix=<Dir>` で履歴を切り出し
2. 子リポの main に push（force なし・merge commit）
3. 必要ならこちらへ `git subtree pull`（`--squash` なし）

独立の気配が出てからでよいです。
