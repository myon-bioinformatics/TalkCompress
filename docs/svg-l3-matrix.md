# SVG L3 を Actions でモデル別に回す（#87）

ワークフロー: `.github/workflows/svg-l3-matrix.yml`（GitHub 上の名前は `svg-l3-matrix`。ひとつの workflow と matrix。mcp-toolcall-lab #182 の方式）

モデルの key・pin（revision、bytes、SHA-256）は `shared/l3_models.json`。ヘルパーは `scripts/svg_l3_bench.py`（`matrix` と `summarize`）。

## 実行

- pull_request: 関連ファイルが変わったときだけ、既定の 1 モデル（`qwen-0.5b`）を回す。全モデルは回さない。手動の `workflow_dispatch` は置かない。

現在の 7 キー（`shared/l3_models.json` の順）:

`qwen-1.5b`, `qwen-0.5b`, `minicpm5-2b`, `lfm2.5-350m-qad`, `lfm2.5-1.2b-qad`, `lfm2.5-2.6b`, `lfm3-1.7b`

全モデル実行は、手動トリガーを戻す判断がいる。この文書は測定の範囲の記録であり、実行そのものではない。

## 設定

- `LLAMA_MAX_TOKENS=2048`、llama.cpp は `-c 4096`、CPU、reasoning off。
- モデルと pin（revision、bytes、SHA-256）は `shared/l3_models.json`。mcp-toolcall-lab の `fixtures/budget_compression/models.json` と同じ 7 件・同じ値（テンプレートのパスのみ本リポジトリ内）。キャッシュヒット時も再ハッシュする。
- キャッシュはモデルごとに 1 エントリ。7 件合計で約 6.86 GB（リポジトリ既定の上限 10 GB 未満）。

## 合否

- 品質の閾値はない。DSL 不通過、未完了の回答、低いスコアでもジョブは失敗しない。`shared/svg_l3.py` が DSL 不通過で返す exit 1 は記録するだけ。
- ジョブが失敗するのは計測そのものが完了しない場合だけ: ダウンロード/検証、llama-server の起動、推論の異常（execution_errors、run_error、サーバー不達）、トークナイザー（応答に token 数が無い）、図の欠落。

## 結果の場所

1. 対象の workflow run（Actions の `svg-l3-matrix`、または `gh run list --workflow=svg-l3-matrix --repo myon-bioinformatics/TalkCompress`）。
2. ジョブの Summary（`GITHUB_STEP_SUMMARY`）: 図ごとの生の数字。完了/未完了、DSL 通過、probe hits/total（往復と source control）、prompt/completion トークン数、リクエスト数。
3. Artifact（保持 30 日）。名前は `svg-l3-matrix-<model>-<run_id>-<run_attempt>`（例: `svg-l3-matrix-qwen-0.5b-1234567890-1`）。`all` のときはモデルごとに 1 つ付く。中身:
   - `l3-report.json`（生 JSON）
   - `requests.jsonl`
   - `summary.json` / `summary.md`
   - `model.gguf.provenance.json`
   - `run-provenance.json`
   - llama-server のログ（`llama-server.log`）と `container.json`
   - `svg_l3_exit_status.txt`（DSL 不通過時の exit 1 を失敗扱いにしないための記録）
4. 取得例: `gh run download <run-id> --repo myon-bioinformatics/TalkCompress`。計測が途中で落ちても `if: always()` で artifact を上げる（中身が空なら warn）。

L2（Chromium 描画）は対象外。
