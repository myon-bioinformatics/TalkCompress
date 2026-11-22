# G4 live round-trip on the current low-speaker-count forms

The November 22 run used all Czech (8), Dutch (8) and Polish (2) winners from the tense matrix at bea8a88. Each form had three existing templates and seeds 1, 2 and 3. The local Qwen2.5-1.5B-Instruct Q4_K_M model received only the mixed-language sentence and restoration instruction. The scorer used the existing NFC normalization and official English sources. At temperature 0.2 all 162 requests completed. Czech restored 3/72, Dutch 3/72, Polish 0/18. No form met the 0.9 threshold. These are model-specific measurements. Production selection continues to use its existing evidence.

The [per-trial report](g4-live-20261122.json) records the model revision, weight checksum, llama.cpp build, policy, input, seed, answer and score. To reproduce on Linux, download and verify the weights with the existing fetcher, then start llama.cpp b12004. Run the scorer from the repository root with the server running.

```sh
python scripts/fetch_l3_model.py qwen-1.5b models/model.gguf
llama-server -m models/model.gguf --host 127.0.0.1 --port 8080 --parallel 2 -t 4 -tb 4 -c 4096 -ngl 0
# In another terminal
uv run --locked --group session-test python scripts/live_roundtrip.py \
  --model-receipt models/model.gguf.provenance.json --runtime 'llama.cpp b12004 CPU' \
  --output build/g4-live.json
```
