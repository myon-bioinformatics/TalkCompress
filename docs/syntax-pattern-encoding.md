# 文型ごとの圧縮表記 検証記録（2026-10-31 JST）

> **位置づけ:** 文型の新しい圧縮・復元規則は未実装で、以下の方針はすべて暫定（未決）です。表の数値は #103 に残された**著者報告・未検証の履歴**です。生出力・モデル来歴の検証記録はコミットされておらず、この安全化では再測定も再採点もしていません。

評価軸: o200k_base トークン数（少ないほど良い）→ UTF-8 バイト数。数値は原文との差・1文あたり平均。

計測スクリプト（`scripts/syntax_encoding/`、リポジトリ直下から実行）:
- `measure.py`（句動詞15文・SVC/SVOO/SVOC 各12文）: `uv run python scripts/syntax_encoding/measure.py --run`
- `svoc2.py` / `svoc3.py`（SVOC 追加候補）: 同様に `--run` が必要
- `llm_roundtrip.py`（小型 LLM 復元）: **リポジトリ外の依存あり**。著者報告では `llama-cpp-python` 0.3.36 を使用（TalkCompress の依存には含まれない）。現行スクリプトは明示的な `--run` と既存のローカル GGUF、期待 SHA-256、取得元の記述、新規出力先が必要。`SMOLLM_GGUF` や `m.gguf` への暗黙のフォールバックはしない。

いずれも import・`--help`・`--run` なしでは tokenizer/model を読み込まず、計測しない。tokenizer 側の明示実行はキャッシュ未取得時に辞書を取得し得る。CI は偽 tokenizer・偽モデルのみで安全性を検査し、これらの実測 CLI を呼ばない。

## 1. 句動詞・SVC・SVOO（measure.py、著者報告）
| 文型 | 書き方 | トークン差 | バイト差 |
|---|---|---|---|
| 句動詞 | 現行TC | −0.27 | −2.00 |
| 句動詞 | `look_up` | +0.07 | ±0 |
| 句動詞 | `look-up` | +0.13 | ±0 |
| 句動詞 | `lookUp` | ±0 | −1.00 |
| SVC | `become_happy` | +0.50 | ±0 |
| SVC | `become-happy` | +0.67 | ±0 |
| SVC | `becomeHappy` | +0.17 | −1.00 |
| SVOO | `give(him, book)` | +0.75 | −0.42 |
| SVOO | `give(him,book)` | +0.50 | −1.42 |
| SVOC | `make(him→happy)` | +1.42 | +3.00 |
| SVOC | `make(him->happy)` | +1.42 | +2.00 |
| SVOC | `make_happy him` | +0.42 | ±0 |

注意: SVOO 候補は表記変更に加えて目的語先頭の `a` / `an` / `the` も除去している。差は純粋な表記変更だけの効果ではなく、冠詞削除との混合比較である。例文は手作りの小標本で、一部は語形を簡略化している。自然文全般の圧縮率や意味保持を示さない。

## 2. SVOC 追加候補（svoc2.py / svoc3.py、著者報告）
| 書き方 | 全体 | 目的語1語 | 目的語2語以上 |
|---|---|---|---|
| `makeHappy him` | +0.08 / −1 | – | – |
| `make happy(him)` | +0.25 / +1 | +0.50 / +1 | ±0 / +1 |
| `make happy(the_room)` | +0.42 / +1 | +0.50 / +1 | +0.33 / +1 |
| `make_happy him` | +0.42 / ±0 | +0.83 / ±0 | ±0 / ±0 |
| `make(happy(him))` | +0.83 / +2 | +1.50 / +2 | +0.17 / +2 |
| `make_him_happy` | +0.83 / ±0 | – | – |
| `make him:happy` | +1.08 / ±0 | +1.33 / ±0 | +0.83 / ±0 |
| `make him=happy` | +1.08 / ±0 | +1.33 / ±0 | +0.83 / ±0 |
| `make him->happy` | +1.17 / +1 | – | – |
| `make_him->happy` | +1.58 / +1 | – | – |

（「トークン差 / バイト差」）

所見:
- この小標本の**新規候補の平均値**では原文よりトークンが減る書き方はなかった（既存 TC の句動詞行は −0.27）。個々の文や他の文型への一般化はしない。
- `makeHappy him` は SVC の camelCase と同じ形になる。後ろに副詞が続く文（"It turnCold today."）では目的語と取り違えるため、採用は難しい。
- `make_him_happy` は目的語が2語以上だと補語との境目が分からず、元に戻せない。
- `make happy(him)` は目的語が1語だと `(h`+`im` に割れる。目的語が2語以上なら原文と同じトークン数になる（括弧内のスペースは残す）。

## 3. 暫定方針（未決）
- 句動詞: `look_up`（`_` 連結）。camelCase は `Up` などの大文字断片が大文字1字の扱いとぶつかるため見送り。
- SVC: camelCase（`becomeHappy`）。
- SVOO: スペースなしの括弧書き（`give(him,book)`）。
- SVOC: `make him:happy`（コロン形）。語順を入れ替えずに済み、著者報告の小型 LLM 参考値では最高だった（§4、未検証）。

### コロンの判定案
`:` の直前と直後がどちらも英字で、前後にスペースがない場合だけを SVOC と見なす。これで時刻（`10:30`、数字にはさまれる）や見出し（`Note: `、後ろにスペース）と区別できる。
これは **SVOC コロン構文の未実装案**であり、TalkCompress にコロン処理が一切ないという意味ではない。既存 MorphoZip は `[[keep:...]]` / `` `keep:...` `` 保護スパンを処理する（`MorphoZip/morpho_zip.py` の `_KEEP_SPAN` / `_KEEP_BT`）。`Note:foo` や `mailto:x` のような文字に挟まれたコロンとの衝突も未解決で、提案条件だけで安全性は保証できない。

### 注意点（未対応）
- 現行 ShorthandEdge は `give` を `prov` に置き換えるため、SVOO の文（"I prov him a book."）で意味がずれる恐れがある。
- SVOO と SVOC（括弧形を使う場合）は括弧内の `,` の有無で区別する想定だが、目的語に `,` を含む場合（"him, her" など）の決めごとはまだない。

## 4. AI 可読性（著者報告の履歴・未検証）
著者は SmolLM2-135M-Instruct Q4_K_M GGUF（mcp-toolcall-lab のピンと同一、sha256 一致と報告）を llama-cpp-python 0.3.36 で CPU 実行したとしている。ただし具体的な hash・取得元の検証記録・全生出力はコミットされておらず、独立には確認できない。
報告条件: temperature 0、記法説明つき system プロンプト、SVOC 12文。旧スクリプトは応答の先頭行だけを取り出し、ASCII 小文字化・記号除去後の単語列を比較していた。finish_reason や実行失敗の完了性は判定していない。下表はその旧手順の著者報告をそのまま保存したもので、完全応答の検証済み成功率ではない。
| 書き方 | 復元成功 |
|---|---|
| `make him:happy` | 8/12 |
| `make him=happy` | 7/12 |
| `make_happy him` | 1/12 |
| `make happy(him)` | 0/12（入力をそのまま返すだけ） |
| `make(happy(him))` | 0/12 |

著者はこの小標本で記号除去より語順変更が難しかったと解釈している。未検証の少数例からモデル一般の能力は結論できず、「大きな LLM が読めるか」も示さない。大きいモデルでの評価は未測定。

## 5. 今後の明示実行と証跡（今回の実測はなし）

```sh
uv run python scripts/syntax_encoding/llm_roundtrip.py --run \
  --model /path/to/pinned.gguf --model-sha256 EXPECTED_64_HEX_SHA256 \
  --model-source "trusted source URL and revision" --output new-roundtrip.jsonl
```

重みはダウンロードせず、指定ローカルファイルの SHA-256 が期待値と一致してから読み込む。取得元は呼び出し側の申告であり、スクリプトは URL に接続して来歴を独立検証しない。既存出力への上書きは拒否する。

JSONL はモデル hash/バイト数、取得元申告、ソース・ケース・プロンプト hash、Python/llama-cpp-python 版、モデル metadata/chat format、明示した設定、全 60 試行の入力・正解・全応答・finish_reason・エラー、完了 summary を逐次保存する。ライブラリ内部の未指定既定値は記録した版に依存する。途中で中断し summary がない証跡は未完了として扱う。

新手順 `syntax-roundtrip/2-full-completion` は `finish_reason=stop` かつ非空応答だけを採点し、先頭行だけでなく全文を比較する。length・壊れた応答・実行エラーは成功扱いしない。終了コード 2 は実行未完了を表し、品質の不一致だけでは失敗終了にしない。旧表とは別手順であり、旧数値を書き換えたり比較可能と主張したりしない。新たな実モデル計測・tokenizer 辞書取得は、この修正・検証では行っていない。

