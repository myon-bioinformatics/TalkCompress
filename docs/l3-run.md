# L3 run procedure (SVG DSL v0)

L3 asks whether meaning survives a round trip: a model describes a drawing, writes
SVG from that description, and then answers questions about the SVG it wrote.
No API key is used. The model runs on a local llama.cpp server.

## 1. Start a local model

Any GGUF chat model works. Record the exact file name and quantization, because
the report stores the label you give it.

    llama-server -m /path/to/model.gguf --port 8080

Check that it answers:

    curl -s http://127.0.0.1:8080/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":16}'

## 2. Run L3 on the example figures

    LLAMA_URL=http://127.0.0.1:8080/v1/chat/completions \
    LLAMA_MAX_TOKENS=1024 \
    python shared/svg_l3.py examples/figures/*.svg \
      --cmd "python shared/llama_cmd.py" \
      --model "LFM3-1.7B Q4_K_M" \
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

Exit status is 0 only when every figure passes DSL v0.

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
