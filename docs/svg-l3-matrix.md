# SVG L3 を Actions でモデル別に回す（#87）

ワークフロー: `.github/workflows/svg-l3-matrix.yml`（ひとつの workflow と matrix。mcp-toolcall-lab #182 の方式）

## 実行
- pull_request: 関連ファイルが変わったときだけ、既定の 1 モデル（`qwen-0.5b`）を回す。全モデルは回さない。
- workflow_dispatch: `models` にモデルキー、カンマ区切りのキー、または `all`（7 件）を指定する。

## 設定
- `LLAMA_MAX_TOKENS=2048`、llama.cpp は `-c 4096`、CPU、reasoning off。
- モデルと pin（revision、bytes、SHA-256）は `shared/l3_models.json`。mcp-toolcall-lab の `fixtures/budget_compression/models.json` と同じ 7 件・同じ値（テンプレートのパスのみ本リポジトリ内）。キャッシュヒット時も再ハッシュする。
- キャッシュはモデルごとに 1 エントリ。7 件合計で約 6.86 GB（リポジトリ既定の上限 10 GB 未満）。

## 合否
- 品質の閾値はない。DSL 不通過、未完了の回答、低いスコアでもジョブは失敗しない。`shared/svg_l3.py` が DSL 不通過で返す exit 1 は記録するだけ。
- ジョブが失敗するのは計測そのものが完了しない場合だけ: ダウンロード/検証、llama-server の起動、推論の異常（execution_errors、run_error、サーバー不達）、トークナイザー（応答に token 数が無い）、図の欠落。

## 結果
- ジョブのサマリーに図ごとの生の数字: 完了/未完了、DSL 通過、probe hits/total（往復と source control）、prompt/completion トークン数、リクエスト数。
- artifact: `l3-report.json`（生 JSON）、`requests.jsonl`、`summary.json`/`summary.md`、`model.gguf.provenance.json`、`run-provenance.json`、サーバーログ。
- L2（Chromium 描画）は対象外。
