# 文字数予算の形式検証

`formal/Budget.lean` は、`DensityFacadeRoute/density_facade_route.py` の
`run_budget()` が行う候補評価と最短候補の選択をモデル化します。
通常実行の依存を増やさず、共通の Lean 実行・公理監査は
[親の `lean_verify.py`](https://github.com/myon-bioinformatics/myon-bioinformatics/blob/main/lean_verify.py)
に集約します。Lean は `formal/lean-toolchain` で固定し、Mathlib は使いません。

## 証明と Python の接続点

モデルは候補の型、文字数を返す `size`、次の候補を返す `step` を引数に取ります。
非負の予算と評価回数上限を受け取り、予算到達・縮小停止・回数上限で候補評価を終了します。
観測した候補列から、元の入力も含めて最初の最短候補を選びます。

| Lean の命題 | 内容 | Python の接続点 |
| --- | --- | --- |
| `candidate_count_bounded` | 評価した候補数は与えた上限以下 | `max_rounds = 8` のループ |
| `shortest_not_larger` | 選択結果は元の最良候補より長くならない | `best` の更新 |
| `shortest_is_minimum` | 選択結果は全ての観測候補以下の文字数 | `len(nxt) < len(best)` の比較 |
| `no_improvement_keeps_original` | より短い候補がなければ元の内容を保持 | 同長・増大時の元入力保持 |
| `within_budget_skips_pipeline` | 既に予算内なら候補を評価しない | 先頭の早期 return |
| `budget_result_not_larger` | 候補評価と選択を合わせても入力より長くならない | `run_budget()` の返り値 |

名前空間は全て `TalkCompress` です。式では、入力を `x`、実際に評価した候補列を
`V` としたとき、返り値の文字数は `x` と `V` の最小値です。
同長の候補では先に観測した内容を維持します。評価回数は最大 8 回です。

`tests/test_formal_budget_bridge.py` は実際の `run_budget()` を呼び出します。
制御した候補変換で 4,096 通りの小さな状態を列挙し、同長、増大、縮小停止、上限到達、
Unicode の境界条件を確認します。さらに C/E の実際の変換を呼び出す 18 通りの実行で、
観測した出力に対する選択規則を確認します。制御用の変換はルーターを模擬実装したものではなく、
既存のパイプライン呼び出し境界に渡すテスト入力です。

## 保証範囲

`size` は Python の `len(str)` に対応する Unicode コードポイント数です。UTF-8 バイト数、UTF-16 の単位数、
実 tokenizer のトークン数、意味保持とは別の尺度です。対象は plain text の予算処理で、
JSONL の古い行を削除する予算処理はこのモデルに含めません。

各変換が文字列を返して正常終了することを前提とします。外部処理が停止しない場合や
例外を投げる場合まで、8 回の上限で実行時間を保証するものではありません。
モデルの予算は非負の整数です。状態付きの台帳、I/O、暗号化や自然言語の復元は
この証明の対象外です。

最短なのは **評価済みの候補の中** です。途中で長くなった先にある候補を探索する仕様ではなく、
8 回で必ず予算に達する保証もありません。Python の `under_budget` は別に確認します。
有限個の接続テストは Python 実装全体の形式証明ではなく、意味保持や LLM の理解度は
既存の keep-check・QA fidelity・実測で別途評価します。

## 実行

通常の接続テストは Lean や追加パッケージなしで実行できます。

```sh
python -S -m unittest discover -s tests -p test_formal_budget_bridge.py -v
```

親リポジトリを隣の `myon-bioinformatics` に配置した場合、共通ラッパーで実行します。

```sh
python -S ../myon-bioinformatics/lean_verify.py \
  --cwd formal --required --json-output build/lean-verification.json \
  --theorem TalkCompress.candidate_count_bounded \
  --theorem TalkCompress.shortest_not_larger \
  --theorem TalkCompress.shortest_is_minimum \
  --theorem TalkCompress.no_improvement_keeps_original \
  --theorem TalkCompress.within_budget_skips_pipeline \
  --theorem TalkCompress.budget_result_not_larger \
  Budget.lean
```

専用 CI は共通ワークフローを固定コミットで呼び出します。Lean 未導入は未検証であり、
専用 CI では失敗として扱います。証明失敗・警告・`sorryAx`・許可外の公理依存も失敗です。
通常の unittest/pytest と形式検証の結果は、それぞれの証跡として確認します。
