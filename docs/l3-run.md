# L3 run procedure (SVG DSL v0)

L3 asks whether meaning survives a round trip: a model describes a drawing, writes
SVG from that description, and then answers questions about the SVG it wrote.
No API key is used. The model runs on a local llama.cpp server.

## 1. Start a local model

Use the official Qwen2.5-0.5B-Instruct Q4_K_M GGUF as a small, reproducible
candidate. This is an acquisition/startup candidate, not a claim of L3 quality.

- Publisher file page: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
- Direct download: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
- Checked publisher revision: `9217f5db79a29953eb74d5343926648285ec7e67`.
- File: `qwen2.5-0.5b-instruct-q4_k_m.gguf` (491,400,032 bytes).
- SHA-256: `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
  This is the file SHA-256, not the distinct Xet storage hash.

From the repository root (Linux):

```sh
mkdir -p /tmp/talkcompress-models
MODEL=/tmp/talkcompress-models/qwen2.5-0.5b-instruct-q4_k_m.gguf
curl --fail --location --retry 3 --connect-timeout 15 --max-time 600 \
  --continue-at - --output "$MODEL" \
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf
printf '%s  %s\n' \
  74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db \
  "$MODEL" | sha256sum --check -
# Continue only after sha256sum reports OK.
llama-server -m "$MODEL" --host 127.0.0.1 --port 8080 -c 4096 -t 4 -ngl 0
```

The official page also advertises
`llama serve -hf Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M` for the newer
llama CLI. This still downloads from Hugging Face; it does not bypass blocked
Hugging Face/Xet access. Prefer an explicitly verified local file for this run.
Do not commit model weights to this repository.

If Hugging Face is blocked, a real alternative publisher listing exists at
https://modelscope.cn/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF . Its existence alone
does not establish that a downloaded artifact is byte-identical: verify the
filename, byte count and SHA-256 above before using it. This route has not been
used for the measurement below. An approved machine can also download the
verified official file and transfer it offline; recheck SHA-256 after transfer.
Do not treat an unverified GitHub mirror as the publisher.

Check that it answers:

    curl -s http://127.0.0.1:8080/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":16}'

## 2. Run L3 on the example figures

    LLAMA_URL=http://127.0.0.1:8080/v1/chat/completions \
    LLAMA_MAX_TOKENS=1024 \
    python shared/svg_l3.py examples/figures/*.svg \
      --cmd "python shared/llama_cmd.py" \
      --model "Qwen2.5-0.5B-Instruct Q4_K_M" \
      -o l3-report.json

Notes:

- `LLAMA_MAX_TOKENS` must be large enough for an SVG (1024 is a safe start). The
  default of 128 cuts off long answers. A cut-off answer is rejected and counted
  as unfinished, not as a wrong answer.
- Use the same settings for every model you compare. Changing the model label
  alone does not make two runs comparable if the prompt or limit changed.

## 3. What the report contains

- `meta`: model label, endpoint, token limit, DSL version, prompt version,
  scorer version, Python version.
- `reports[]` per figure: the description, the generated SVG, whether it passed
  DSL v0 (`dsl_ok`), the validation errors, and the probe results (`hits`, `total`,
  `score`, and each question with the answer).
- `source_sha256`: fingerprint of the input figure, so a later run can prove it used the same file.

Exit status is 0 only when every figure passes DSL v0. This does not guarantee
complete probe answers or full retention: also inspect each report status and
unscorable probes.

## 4. How to read the score

- Prompt/scorer version **2** requires a complete typed JSON array for each
  requested attribute list. It never searches a question, prose answer or copied
  SVG for a matching number. Questions contain no original coordinates or other
  expected values. This fixes version 1's question-echo false hits.
- `score` is the share of source items correctly returned in those arrays. Radius,
  rectangle width, line x2 and text values are compared in document order. Explicit
  non-`none` colors are compared as a unique unordered list. Numbers compare as
  exact decimals, without rounding the answer; text compares as complete strings.
  An omitted radius, rectangle width or line x2 supplies SVG's zero default.
- This is an attribute-retention metric, not drawing quality or semantic shape
  matching. Reordering same-kind shapes/text can change the score even if a drawing
  looks equivalent. Paths, computed inherited colors, and full layout are not
  measured by these probes.
- A missing, malformed, truncated or wrong-length list earns no hits for that
  category and records `status: unscorable` and an error per affected item.
  A report with any such item has overall `status: incomplete`; its hit ratio
  must not be read as a completed model-quality measurement.
  Completed wrong values record `status: scored` with `ok: false`. Think-block
  contents are excluded. No magic replacement text is ever treated as an answer.
- A valid drawing with no probes has `score: null`, `status: not_applicable` and
  `total: 0`, not a perfect or zero-quality result.
- Version 1 and version 2 scores are **not comparable**. Preserve old reports and
  their provenance; do not reinterpret old scores as version-2 results. Each new
  figure report and its metadata carry the prompt/scorer versions.
- A figure that fails DSL v0 scores 0 by definition. Count those separately
  (`dsl_ok` false) before comparing scores.
- The probes come from the original figure's own attributes. Each probe is one
  number, text, or color; duplicates in ordered lists remain separate items.
- Small sample: six figures give a few dozen probes. A difference of a few points
  is noise until it repeats across runs.

## 5. What to send back

Send `l3-report.json`. It contains the model label and settings. Do not send
other logs unless a run fails before the report is written.

## Checks before a run

    uv run pytest -q tests/test_svg_l3.py tests/test_svg_dsl.py tests/test_svg_figure.py

## Verified acquisition and smoke run (2026-10-31)

Official Hugging Face download completed and its local SHA-256 matched the
publisher value above (491,400,032 bytes). The first attempt hit a 30-second
limit at 438,819,624 bytes; resuming with `curl --continue-at -` succeeded.
No alternative mirror was needed. The repository revision checked through the
publisher API was `9217f5db79a29953eb74d5343926648285ec7e67`; the measured download
used `resolve/main`, while the reproducible command above pins that revision.

llama.cpp `5047748f114564fcf271e6a648f60e2d2eae6264` was built locally with
`GGML_NATIVE=OFF`, CPU inference, context 4096 and four threads. The server
returned health OK and answered a short smoke prompt with `OK` using the
unchanged `shared/llama_cmd.py` completion checks. On this host, cross-exec-session
localhost connections were refused; starting the server and client in the same
exec session worked. This was an execution-environment issue, not a weight error.

The exact section-2 command ran all six existing SVG samples once, using Python
3.12.14, temperature 0 (the adapter default), `LLAMA_MAX_TOKENS=1024`, DSL v0,
prompt v2 and scorer v2. Runtime was about 248 seconds on Linux x86_64 / AMD EPYC
9V74, with cgroup limits of 8 GiB memory and eight CPU equivalents. No renderer,
scorer, prompts, completion checks or token limits were changed.

| Figure | DSL passed | Status | Recorded hits/total (incomplete) |
| --- | --- | --- | --- |
| chart_auto.svg | no (description failed) | incomplete | 0/0 |
| chart_line.svg | no (description failed) | incomplete | 0/0 |
| chart_two.svg | no (description failed) | incomplete | 0/0 |
| flow_basic.svg | yes | incomplete | 5/11 |
| flow_center.svg | yes | incomplete | 0/9 |
| polyline_only.svg | yes | incomplete | 1/5 |

L3 exited **1**. Three generated SVGs passed DSL validation, but **no figure
completed all probes**. Some answers wrapped JSON in Markdown fences, which the
strict v2 array contract correctly marked unscorable. Other model-command
failures appear in the raw report; its existing error truncation omits the tail
of the Python traceback. A description-only diagnostic rerun of chart_auto.svg
with the same settings confirmed `ValueError: answer did not complete: 'length'`;
the 1024-token cap was retained and the unfinished answer was rejected. This
diagnostic does not establish the exact exception for every other failed call.
These incomplete hit ratios are diagnostics, not
completed quality scores, and the three description failures are not completed
zero-quality measurements. Do not claim L3 acceptance or compare model quality
from this run. Chromium rendering/pixel equivalence was not measured here.

Saved evidence:

- [Raw L3 report](results/svg-l3-qwen-20261031.json), including input hashes,
  generated SVGs, answers, errors and v2 metadata.
- [Provenance and execution conditions](results/svg-l3-qwen-20261031-provenance.json).
- [Description-only diagnostic rerun stderr](results/svg-l3-qwen-20261031-describe-error.txt),
  using the same model and limits; supplementary evidence, not a replacement run.

Before measurement, the documented test command produced 139 passed and 1
skipped (optional tiktoken unavailable). This test result does not establish
model quality.
