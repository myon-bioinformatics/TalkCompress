# トークナイザー互換レポート（report-only）

採点は o200k_base。各採用セルの勝者が英語の最安形（短縮形含む）に (tokens, utf8) で厳密に勝つトークナイザーを記録。負けても不採用にはしない。

生成: `uv run python scripts/tokenizer_compat.py --compat`

| tokenizer | pin | 勝ち | / 採用 |
|---|---|---|---|
| o200k_base | tiktoken@0.14.0 | 824 | 824 |
| cl100k_base | tiktoken@0.14.0 | 653 | 824 |
| qwen2.5 | Qwen/Qwen2.5-0.5B@060db6499f32 | 670 | 824 |
| qwen3 | Qwen/Qwen3-0.6B@c1899de289a0 | 670 | 824 |
| llama3.2 | unsloth/Llama-3.2-1B@9535bd9b1d1d | 664 | 824 |
| mistral-v0.3 | unsloth/mistral-7b-v0.3@9ea1b83f5ced | 585 | 824 |
| deepseek-v3 | deepseek-ai/DeepSeek-V3@e815299b0bcb | 664 | 824 |

| 区分 | セル数 |
|---|---|
| all | 564 |
| o200k only | 129 |
| 6/7 | 80 |
| 2/7 | 15 |
| 4/7 | 13 |
| 3/7 | 12 |
| 5/7 | 11 |
