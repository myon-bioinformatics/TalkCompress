# 文型ごとの圧縮表記 検証記録（2026-10-31 JST）

> **位置づけ:** これから検証する項目の事前共有です。実装はまだしていません。以下の方針はすべて暫定（未決）です。

評価軸: o200k_base トークン数（少ないほど良い）→ UTF-8 バイト数。数値は原文との差・1文あたり平均。

計測スクリプト（`scripts/syntax_encoding/`、リポジトリ直下から実行）:
- `measure.py`（句動詞15文・SVC/SVOO/SVOC 各12文）: `uv run python scripts/syntax_encoding/measure.py`
- `svoc2.py` / `svoc3.py`（SVOC 追加候補）: 同様に実行
- `llm_roundtrip.py`（小型 LLM 復元）: **リポジトリ外の依存あり**。`llama-cpp-python`（0.3.36 で確認、TalkCompress の依存には含まれない）と、SmolLM2-135M-Instruct Q4_K_M GGUF（mcp-toolcall-lab のピンと同一）が必要。GGUF のパスは環境変数 `SMOLLM_GGUF` で指定。

## 1. 句動詞・SVC・SVOO（measure.py）
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

## 2. SVOC 追加候補（svoc2.py / svoc3.py）
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
- 原文よりトークンが減る書き方は、どの文型にもなかった。
- `makeHappy him` は SVC の camelCase と同じ形になる。後ろに副詞が続く文（"It turnCold today."）では目的語と取り違えるため、採用は難しい。
- `make_him_happy` は目的語が2語以上だと補語との境目が分からず、元に戻せない。
- `make happy(him)` は目的語が1語だと `(h`+`im` に割れる。目的語が2語以上なら原文と同じトークン数になる（括弧内のスペースは残す）。

## 3. 暫定方針（未決）
- 句動詞: `look_up`（`_` 連結）。camelCase は `Up` などの大文字断片が大文字1字の扱いとぶつかるため見送り。
- SVC: camelCase（`becomeHappy`）。
- SVOO: スペースなしの括弧書き（`give(him,book)`）。
- SVOC: `make him:happy`（コロン形）。語順を入れ替えずに済み、小型 LLM で最も元に戻しやすかった（§4）。

### コロンの判定案
`:` の直前と直後がどちらも英字で、前後にスペースがない場合だけを SVOC と見なす。これで時刻（`10:30`、数字にはさまれる）や見出し（`Note: `、後ろにスペース）と区別できる。
なお、時刻や見出しとぶつかるという懸念は一般論であり、現在の TalkCompress には `:` を扱う専用の処理はない（コード中の `:` は JSON 出力の区切りのみ）。

### 注意点（未対応）
- 現行 ShorthandEdge は `give` を `prov` に置き換えるため、SVOO の文（"I prov him a book."）で意味がずれる恐れがある。
- SVOO と SVOC（括弧形を使う場合）は括弧内の `,` の有無で区別する想定だが、目的語に `,` を含む場合（"him, her" など）の決めごとはまだない。

## 4. AI 可読性（llm_roundtrip.py、参考値）
SmolLM2-135M-Instruct Q4_K_M GGUF（mcp-toolcall-lab のピンと同じもの、sha256 一致）を llama-cpp-python 0.3.36 で CPU 実行した。
条件: temperature 0、記法説明つき system プロンプト。SVOC 12文を元の英語に戻し、記号を除いて単語列が完全一致したら成功とした。
| 書き方 | 復元成功 |
|---|---|
| `make him:happy` | 8/12 |
| `make him=happy` | 7/12 |
| `make_happy him` | 1/12 |
| `make happy(him)` | 0/12（入力をそのまま返すだけ） |
| `make(happy(him))` | 0/12 |

135M の超小型モデルは、記号を消すことはできても、語順を入れ替えることがほぼできない。そのため、この結果は「大きな LLM が読めるか」を示すものではない。大きいモデルでの評価は未測定。

