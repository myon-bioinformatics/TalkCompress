# Paragraph round-trip benchmark

Until now every AI round-trip gave the judge **one sentence per call** (`scripts/roundtrip.py`,
`roundtrip_judge/*`, `reaudit_*`, `remaining_20261110*`), and the multi-sentence tests
(`test_pd_corpus_smoke.py`, `test_pd_corpus_extended.py`, `test_mid_split_smoke.py`,
`test_pd20_examples.py`) only check that compression does not crash or still gives the fixed output.
This benchmark measures, for a whole paragraph (3–6 sentences), **how much it shrinks** and
**how accurately a blind AI judge restores it**.

## Material

60 paragraphs (`SentenceCalibratedMosaic/fixtures/paragraph_judge/sources.json`, built by
`scripts/build_paragraph_sources.py`):

| lang | paragraphs | source |
|---|---|---|
| en | 12 | FLORES-200 devtest Wikinews ×6, public-domain narrative/dialogue ×6 |
| de es fr pt ja zh it nl el cs pl | 4 each | FLORES-200 devtest, same 4 Wikinews articles in every language |
| la | 4 | Caesar, *De Bello Gallico* I (Gutenberg #218); FLORES-200 has no Latin |

Gold sentence boundaries are stored per paragraph (FLORES segments; one FLORES segment can hold two
sentences, e.g. en-flores-05).

## Methods

DensityFacadeRoute with CLI defaults: `control` (uncompressed), `C`, `E`, `CE`, `CEF` (= C,E,B-final-zh-de,
what `--auto` picks for Latin-script prose), `BEF` (B,E,B-final-zh-de). Only `control`, `CEF` and
`BEF` are judged; the others are tokens/bytes only. `control` measures how much the judge rewrites a
paragraph that was not compressed at all. A `CEF` item whose output equals the source is still
judged (it is then a second control). In this run that happens for 16 paragraphs, so the control
and CEF *prompts* are identical (same sha256). They are still judged independently — one fresh
judge per item, because the two answers can differ even when the prompt is the same — and recorded
answers are keyed by item id (`<paragraph>|<method>`), not by prompt sha256.

## Official prompt (`PROMPT`, version `paragraph-restore-v1`, approved 2026-11-13)

```
The following paragraph was written in {lang} and may have been compressed: some words may be
abbreviated, replaced by symbols, or swapped for short forms from other languages, and subject
pronouns may be dropped. It may also be unchanged. Rewrite it as the original plain {lang}
paragraph, one sentence per line, in the original order. Reply with the paragraph only.

{compressed paragraph}
```

(one line in the code; `{lang}` is the English language name). The language is named because the
non-English paragraphs must be restored in their own language. "It may also be unchanged" keeps the
control fair. Changing the wording is a new version: bump `PROMPT_VERSION` and rebuild the packs.

## Judging

One fresh, independent knowledgeWork subagent call per item, nothing but the prompt; 3 seeds
× 180 items = 540 calls. Procedure for helpers: `paragraph_judge/README.md`.

## Metrics (`score`, all offline, stdlib)

1. **Compression**: o200k tokens of the whole paragraph first, then UTF-8 bytes; deltas in %.
2. **Sentence exact**: answer split by lines (fallback: regex sentence split, recorded as
   `format_followed: false`), aligned to the gold sentences with an order-preserving DP over
   `difflib` similarity (1-1, 2-1 merge, 1-2 split, drop, add). A gold sentence is exact when
   `roundtrip.norm` of gold and restored content are equal; a merge/split with equal content still
   counts as exact and is labelled `merge_split`.
3. **Paragraph exact**: every gold sentence exact and the same number of sentences.
4. **Semantic (rule-based)**: exact, or equal after English contractions are expanded and
   articles/determiners removed. This is not an AI judgement.
5. **Notation-tolerant** (`notation_tolerant`): applied *on top of* `semantic_rule`. A sentence
   passes if it already passes `semantic_rule`, or if `loose()` of the two sides matches after a
   closed, stdlib-only normalisation table (`notation_form` in `scripts/paragraph_roundtrip.py`).
   The invariant is `notation_tolerant >= semantic_rule >= exact` (always). This is the third
   sentence metric, reported per method and per language alongside `exact` and `semantic_rule`.
   Sentence *exact* is unchanged and stays strict. The table folds only newspaper-style
   *notation*, not wording:
   - English number words ↔ digits, 0–99, plus the simple forms *a/one hundred* and
     *a/one thousand* (also hyphen or space: *twenty-one* / *twenty one* ↔ *21*);
   - matching English ordinals (*eighteen* stays distinct from *eighteenth*; *eighteenth* ↔
     *18th*);
   - *per cent* / *percent* / *per-cent* (optional plural) ↔ `%` — not *percentage*;
   - typographic quotes and apostrophes ↔ ASCII (`'` / `"`), including U+2019 vs `'`;
   - dash / minus variants ↔ ASCII hyphen;
   - fullwidth digits and `%`;
   - whitespace, trailing or separator punctuation (word-internal apostrophes and hyphens
     are kept), and spaces next to CJK characters (*从 1959 年* ↔ *从1959年*). Fullwidth
     parentheses (*（Liggins）* ↔ * (Liggins) *) already fold as separator punctuation.
   Lexical synonyms still fail (*at least* ≉ *about*, *Antwort* ≉ *Reaktion*). Differences
   that `semantic_rule` already accepts (English contractions, articles/determiners) also
   pass `notation_tolerant`. When two sentences match by the notation table itself, they are
   not labelled as errors in the taxonomy (the difference is notation, not meaning).
   Number-word and percent-word lists are English; typographic folding applies to every
   language. Roman numerals and other lexical number names (*XV*, *quindecim*) are outside
   the table.
   Rationale (myon, 2026-11-13, t1208): 「厳密であることと正確であることは別」— symbols and
   digits that survive or are substituted in newspaper-style English (*per cent* ↔ `%`,
   *eighteen* ↔ *18*, U+2019 ↔ ASCII `'`) should not count as errors.
6. **Error taxonomy** (per aligned pair, word tokens, punctuation ignored): `tense_swap`
   (English auxiliaries / same-stem verb change), `inflection_change` (same stem, other languages),
   `added_subject_object`, `dropped_subject_object`, `article_demonstrative`, `synonym_drift`
   (≤3-word replacement), `rewrite`, `added_content`, `dropped_content`, `merge_split`,
   `added_sentence`, `dropped_sentence`, `leftover_foreign` (a compressed-only word kept in the
   answer), `leftover_kanji_symbol` (CJK in a non-CJK paragraph or a symbol such as ○ → & kept),
   and the benign `contraction_or_variant`.
7. **Per-rule attribution**: each `source span → compressed span` edit the codec made is marked
   restored or not (an error overlapping its source span); `rules` in the results lists them by
   number of failures. Errors with no codec edit nearby are `unattributed` (judge noise; compare
   with `control`).
8. **AI readability**: 未測定 (not approved for this run).

## Reproducibility

`paragraph_roundtrip.py build --check` (sources → items → packs), `ingest` (raw → blind with
validation against the pack's prompt sha256), `score --check`, and `paragraph_replay.py --check`
(rebuild, replay every recorded answer *by item id*, re-score). Replay looks up the answer by
`<paragraph>|<method>` and then checks that the stored prompt sha256 matches the pack's sha256
for that same id. Looking up by sha256 alone would pick the first of two methods that share a
prompt (the 16 unchanged-CEF paragraphs) and report a false mismatch when their independent
judges gave different answers. `run --cmd` therefore sets `PARA_ITEM` to the item id, in addition
to `PARA_SEED`. `tiktoken` is used only by `build` (dev group); everything else is stdlib.

## Results (2026-11-13)

Three seeds have been judged and scored. The aggregate tables, per-language commentary, provenance
and disclosures are in [`docs/paragraph-roundtrip-results-20261113.md`](paragraph-roundtrip-results-20261113.md).
AI readability remains 未測定.


## AI readability on CI (nano environment, model-agnostic)

`scripts/ai_readability.py` (one CLI, JSON on stdout, stdlib only) replays the same
`paragraph-restore-v1` pack through a small local model (the *restorer*) instead of a subagent,
scores it with the same rules (`exact`, `semantic_rule`, `notation_tolerant`, error labels), and
has a *judge* model score every aligned sentence pair. The rules stay the baseline; the judge is
reported next to them with its agreement, because rule scoring alone is not rock-solid (synonyms,
word order and paraphrases fail the rules even when the meaning is kept). `report.json` carries
`ai_readability: {"status": "measured", "restorer": <key>, "judges": ["rule", <key>...]}`.

| piece | where |
|---|---|
| restorer and judge models, weights pins (revision, bytes, SHA-256) | catalog keys in `shared/l3_models.json` (shared with SVG L3) |
| defaults | `DEFAULTS` at the top of the script: judge `mdeberta-xnli-onnx` (MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 @`b5113eb3`, fp32 ONNX, **暫定**: not decided by myon; 3bot's comparison (judge-model/3bot `9c8d7d8`) found 88.2% agreement with its reference labels and 0 output tokens) |
| presets (models per purpose) | `PRESETS` in the script, see below; restorer default `qwen3-0.6b` (Qwen3-0.6B Q8_0, **暫定**, from 2bot's restorer bench; Qwen2.5-1.5B paraphrased even the control) |
| llama.cpp | `image`: official b12004 by OCI digest (commit `3c809f44`); `build`: `build-llama` compiles `llama-server` from pinned commit `9d925e7c` (b12381, the build 2bot used for Qwen3; CPU, portable AVX2), cached by commit. Presets use `build` |
| decoding | CPU, all runner cores, context 4096, temperature 0, seed 42, thinking off (`--reasoning off` and `chat_template_kwargs.enable_thinking=false`); restore `max_tokens` 1024, judge 8 |
| workflow | `.github/workflows/ai-readability.yml`: `plan` → `weights` (each GGUF downloaded once, cached) + `llama` (build once if `build`) → `restore` (matrix restorer × shard, round-robin over sorted item ids) → `merge` (per restorer) → `judge` (restorer × judge × shard) → `report` (per restorer) |

**One sentence per line (restorer prompt `paragraph-restore-numbered-v1`).** With the pack prompt,
small restorers answered almost every paragraph on one line, so sentences were re-split by
punctuation and `merge_split` rose. The restorer therefore sends its own prompt (`RESTORE_PROMPT`):
the same instructions, the input sentences numbered one per line, "keep the number, one sentence per
line", and "write them in <language>; do not translate" (without it the Latin paragraph came back in
English). Numbers are stripped before scoring (`unnumber`; the raw reply is kept as `raw`). The
sentences are split from the compressed text the model is given (`input_sentences` =
`split_compressed(text, 0)`: B mosaic tiles, otherwise the sentence-end splitter), never from the
gold, so the count can differ from the gold (Latin `;`, a gold sentence holding two sentences) and
those merge/split labels remain. Answers are still checked against the pack prompt sha256; each also
records `restore_prompt_sha256`, and `merge` refuses shards from another restorer prompt version.
4bot's comparison (Qwen2.5-1.5B Q4_K_M, 39 items, `96ff64f`): pack prompt format 6/39, exact 0.531,
notation_tolerant 0.573, merge_split 30; numbered 39/39, 0.656, 0.766, 13. A llama.cpp JSON schema of
exactly N strings and a GBNF grammar of N lines keep the pack prompt byte-for-byte but were rejected
(the model put the whole paragraph in the first item and repeated it until `max_tokens`; JSON 3/39
unanswered, GBNF 8/18 answered), and one call per sentence lost the context (exact 0.17 on 18 items).
The rule table reports `format_followed` ("one sentence per line") and `label:merge_split`.

**Judges are numeric and pluggable.** A judge returns only a confidence in [0, 1] per aligned
sentence pair; YES/NO is derived later in `report` from a threshold (the catalog entry's
`threshold`, default 0.5, or `report --threshold`), so a threshold change needs no re-run. No
judgement is read from generated text. The catalog entry's `backend` picks the plug-in
(`JUDGE_BACKENDS`):

| backend | score | dependencies |
|---|---|---|
| `nli-onnx` (default judge) | min(P(entailment) gold→restored, restored→gold), ONNX cross-encoder on CPU | onnxruntime, tokenizers, numpy: uv group `judge`, imported lazily, installed only in the judge job (`uv sync --locked --only-group judge`) |
| `llm-logprob` | P(YES) / (P(YES) + P(NO)) of the first token from llama-server's top logprobs (`sentence-equivalence-v2`) | none (stdlib; GGUF via llama.cpp) |

A catalog entry may fix its own shard count (`shards`; the NLI judge uses 1 job, about 0.2 s per
pair) and list extra pinned files (`files`: tokenizer, config), all checked by `fetch` (bytes and
SHA-256, also on cache hits). To add another backend, write `fn(pairs, entry, model_dir, url) ->
[{"score": float | None, ...}]` and register it in `JUDGE_BACKENDS`.

**Judge metrics** (`report`, per method, in sentences): `mean_score`, `judge_equivalent_rate`
(score above the threshold), `agreement_rate` with `notation_tolerant`, `rule_pass_judge_no`
(rules accept, judge rejects) and `rule_fail_judge_yes` (rules reject, judge accepts: candidate
rule gaps or judge leniency). A missing answer is a loss for both. A judge from the restorer's own
family is not independent.

**Presets** (`PRESETS`; every field can be overridden per run):

| preset | restorers | paragraphs | items per restorer | shards | use |
|---|---|---|---|---|---|
| `pr-smoke` | `qwen3-0.6b` | 1 per language | 39 | 4 | pull requests: the pipeline still works end to end |
| `accuracy` | `qwen3-1.7b` | 2 per language | 78 | 8 | accuracy check with the larger Qwen3 |
| `full` | `qwen3-0.6b` | all | 180 | 8 | the full measurement |
| `full-pair` | `qwen3-0.6b`, `qwen3-1.7b` | all | 180 each | 8 each | both restorers side by side in one matrix |

**Triggers (no manual runs).** The GitHub event picks the preset (`EVENT_PRESETS` in the script;
the workflow only passes `--event "$GITHUB_EVENT_NAME"`):

| event | preset | why |
|---|---|---|
| `pull_request` touching the pipeline (path filter) | `pr-smoke` | proves the pipeline still works, about 5 minutes |
| `push` to `main` touching the same paths | `accuracy` | each merged change gets the larger-restorer check |
| `schedule`, weekly (Sunday 03:17 JST) | `full` | all 180 items without a manual trigger and without tying it to every merge |

`full` runs on a schedule rather than on push because one weekly full measurement is enough to
follow drift, keeps merge-time cost small, and needs no inputs or extra env vars. `full-pair` and any
override (`--restorers`, `--judges`, `--shards`, `--per-lang`, `--llama`) are for the CLI (local,
olnm, agents): `plan --preset <name>` prints the same matrices. Normal `ci.yml` only runs the
offline plumbing test (`tests/test_ai_readability.py`, a fake server). Low scores never fail a job.

The Qwen3 and mDeBERTa catalog entries carry `"lanes": ["readability"]`, so the SVG L3 lane's `all` stays at
its 7 models (`scripts/svg_l3_bench.py svg_models`).

**Traceability (artifacts, 30 days; nothing is committed).** `air-shard-<restorer>-N`: `shard-<restorer>-N.json` with,
per item id, the prompt, prompt sha256, compressed text, raw server response and answer, plus the
pins (model revision + SHA-256, llama image digest or build commit + binary sha256, git SHA, run
URL, sha256 of `sources.json` / items / pack), the weights receipt and the server log.
`air-merged-<restorer>`: `readability.json` (rule scores, every sentence pair, failures with reasons, sha256 of
each shard file). `air-judge-<restorer>-<judge>-N`: every score with its components (entailment both ways, or
YES/NO token probabilities with the raw response and prompt sha256), judge pins and log. `air-report-<restorer>`: `report.json` and `summary.md` (sha256 of the merged and judge files).
`merge`, `judge` and `report` are pure functions of those files, so any number can be re-derived:

```
uv run python scripts/ai_readability.py merge 'shards/shard-*.json' --out merged/readability.json
uv run python scripts/ai_readability.py report merged/readability.json 'judges/judge-*.json' --out report.json
```

Local or from olnm (`serve` uses docker, or `--llama-bin` for a built server):

```
uv run python scripts/ai_readability.py fetch qwen3-0.6b
uv run python scripts/ai_readability.py serve --model qwen3-0.6b
uv run python scripts/ai_readability.py restore --per-lang 1 --out out/shard-0.json
uv run python scripts/ai_readability.py stop
```

To swap a model, add it to `shared/l3_models.json` (revision, bytes, SHA-256) and pass its key.
Greedy decoding repeats answers, so this pipeline has one seed.
