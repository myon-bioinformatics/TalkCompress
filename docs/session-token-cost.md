# Shared dictionary: bytes versus GGUF tokenizer tokens

PR #119's `measure_session` is unchanged. `Zipilogue.session_tokens` injects
llama.cpp's `/tokenize` counter and compares the **same** frozen dictionary,
32 messages, message order, and retry policy in both units.

`examples/session-cost.json` deliberately reproduces the original synthetic
phrase-reuse experiment. Token counts obtained from a real model tokenizer are
real tokenizer measurements **on synthetic messages**, not natural-conversation
or model-quality measurements.

## Reproduce

The existing `shared/l3_models.json` pins Qwen2.5-0.5B-Instruct Q4_K_M to
revision `9217f5db79a29953eb74d5343926648285ec7e67`, 491400032 bytes and
SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
`fetch_l3_model.prepare` verifies size and SHA-256, including cache hits.

```sh
python scripts/fetch_l3_model.py qwen-0.5b models/model.gguf
```

Start the same pinned server image used by the existing dialogue-lab workflow:

```sh
LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:b32890309c1a33a534a01b0b461e953dc2c5a6bac20213abcf48e22847a19c85
docker run --rm --name session-token-model -p 127.0.0.1:8080:8080 \
  -v "$PWD/models:/models:ro" "$LLAMA_IMAGE" \
  -m /models/model.gguf --host 0.0.0.0 --port 8080 -c 512 -t 2 -ngl 0
```

After `/health` returns success, in another terminal:

```sh
python -m Zipilogue.session_tokens --model qwen-0.5b \
  --model-path models/model.gguf \
  --runtime-id ghcr.io/ggml-org/llama.cpp@sha256:b32890309c1a33a534a01b0b461e953dc2c5a6bac20213abcf48e22847a19c85 \
  --output out/session-token-cost.json
python -m unittest discover -s tests -p 'test_session*.py'
```

The supplied URL must point to the server started with those verified weights;
checking a local model file does not authenticate a remote server's identity.
`--runtime-id` records the operator's pinned runtime identifier. For a native
build, use llama.cpp commit `3c809f44383bcebc318b8cddd8c6d11aaa861e9b`
(b12004), build `llama-server`, and record that full commit as the runtime ID.
A native reproduction can build the pinned source as follows (CMake and a C++
compiler are build tools only):

```sh
git clone https://github.com/ggml-org/llama.cpp.git llama.cpp
git -C llama.cpp checkout 3c809f44383bcebc318b8cddd8c6d11aaa861e9b
cmake -S llama.cpp -B llama.cpp/build -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build llama.cpp/build --target llama-server -j 4
llama.cpp/build/bin/llama-server -m models/model.gguf \
  --host 127.0.0.1 --port 8080 -c 512 -t 2 -ngl 0 --parallel 1
```

No text generation, external API credential, or Python tokenizer dependency is
needed. The manual `session-token-cost` Actions workflow automates the fixed
Qwen experiment and uploads source commit, catalog, verified model receipt,
server/container logs and report even when execution fails. A new manual
workflow must exist on the default branch before GitHub exposes dispatch.

## Accounting policy

- The compact `export_rules()` JSON is distributed once; each original,
  encoded message, and nonempty retransmission is a separate tokenization.
- Requests explicitly set `add_special=false`, `parse_special=false`, and
  `with_pieces=false`. User text resembling a special token is ordinary text.
- No chat template, BOS/EOS, assistant generation, transport headers, or
  repeated prompt history is included. These are payload token counts, not
  total inference billing. Concatenated prompts can have different BPE counts.
- `one_turn` uses the first message. `repeated` uses all 32. `full_resend`
  additionally retransmits the full original on **each** turn, a deliberately
  specified policy rather than an inferred model failure rate.
- `setup`, `encoded_total`, `recovery_total`, and `compressed_total` are
  separate. `first_saving_turn` is the first strict cumulative saving (equality
  is not a saving), not a guarantee of later savings.
- The report includes each unique text and its token IDs, fixture and source
  hashes, and verified model provenance. Request errors, malformed token IDs,
  or model hash failures yield exit 1 and `status=unmeasured`, with no fabricated
  token result or byte-count fallback.

`exact_roundtrip` compares deterministic codec output with the original using a
separately imported dictionary. It does not establish LLM understanding.
`semantic_understanding` and `task_success` remain explicitly **unmeasured**,
with null success rates. Mock word counts in regression tests are test doubles
only and are never experiment evidence.

## Checked-in experiment

See `experiments/session-token-cost/` for the tokenizer report and runtime
receipt. The native b12004 server loaded the verified GGUF and completed `/tokenize`
requests. The checked-in report contains the returned token IDs, not estimated
or mocked counts. `runtime.json` records the native binary hash, version,
command, and measurement time; `llama-server.log` records model startup.

| Unit | Dictionary once | One turn, raw → total | 32 turns, raw → total | First saving turn | 32 turns with full resend | Net saving with resend |
|---|---:|---:|---:|---:|---:|---:|
| UTF-8 bytes | 191 | 46 → 193 | 1472 → 255 | 5 | 1727 | −255 |
| Qwen tokenizer tokens | 57 | 7 → 59 | 224 → 121 | 12 | 345 | −121 |

For tokens, the 32 encoded messages cost 64, dictionary setup costs 57, and
full retransmission adds 224. In the no-retry case the saving is 103 tokens
(about 46.0%); bytes save 1217 (about 82.7%). Byte savings substantially
overstate token savings for this fixture. All scenarios have exact codec
roundtrip; neither LLM comprehension nor task success was tested. These
results apply to this one repeated-phrase fixture and token-boundary policy,
not arbitrary conversations, models, or full chat prompts.

Regression check: `python -m unittest discover -s tests -p 'test_session*.py'`
passes all 10 tests, including request flags, Unicode, cached counts, malformed
responses, timeout failure evidence, per-turn accounting, and collision loss.
