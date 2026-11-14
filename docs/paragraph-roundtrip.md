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
has an LLM *judge* re-read every aligned sentence pair. The rules stay the baseline; the judge is
reported next to them with its agreement, because rule scoring alone is not rock-solid (synonyms,
word order and paraphrases fail the rules even when the meaning is kept). `report.json` carries
`ai_readability: {"status": "measured", "restorer": <key>, "judges": ["rule", <key>...]}`.

| piece | where |
|---|---|
| restorer and judge models, weights pins (revision, bytes, SHA-256) | catalog keys in `shared/l3_models.json` (shared with SVG L3) |
| defaults | `DEFAULTS` at the top of the script: restorer `qwen-1.5b` (Qwen2.5-1.5B-Instruct Q4_K_M); judge `lfm2.5-1.2b-qad` (LiquidAI LFM2.5-1.2B, **暫定**: the judge choice is still open, non-Qwen candidates are being evaluated) |
| llama.cpp | `image`: official b12004 by OCI digest (commit `3c809f44`); `build`: `build-llama` compiles `llama-server` from pinned commit `b1b770d9` (v1.0.0, CPU, portable AVX2), cached by commit, for models that need newer support |
| decoding | CPU, all runner cores, context 4096, temperature 0, seed 42; restore `max_tokens` 1024, judge 8 |
| workflow | `.github/workflows/ai-readability.yml`: `plan` → `weights` (each GGUF downloaded once, cached) + `llama` (build once if `build`) → `restore` (matrix of shards, round-robin over sorted item ids) → `merge` → `judge` (matrix judge × shard) → `report` |

**Judge metrics** (`report`, per method, in sentences): `judge_equivalent_rate` (judge YES),
`agreement_rate` with `notation_tolerant`, `rule_pass_judge_no` (rules accept, judge rejects) and
`rule_fail_judge_yes` (rules reject, judge accepts: candidate rule gaps or judge leniency). The
judge prompt is `sentence-equivalence-v1` (YES/NO, numbers/symbols/punctuation ignored). A
missing answer is a loss for both. A judge from the restorer's own family is not independent.

**Triggers.** Pull requests that touch the pipeline run 1 paragraph per language (39 items),
4 shards, the default judge and `llama=build` (so both llama.cpp paths stay exercised);
`workflow_dispatch` takes `restorer`, `judges`, `shards`, `per_lang` (0 = all 180 items) and `llama`.
Normal `ci.yml` only runs the offline plumbing test (`tests/test_ai_readability.py`, a fake
server). Low scores never fail a job.

**Traceability (artifacts, 30 days; nothing is committed).** `air-shard-N`: `shard-N.json` with,
per item id, the prompt, prompt sha256, compressed text, raw server response and answer, plus the
pins (model revision + SHA-256, llama image digest or build commit + binary sha256, git SHA, run
URL, sha256 of `sources.json` / items / pack), the weights receipt and the server log.
`air-merged`: `readability.json` (rule scores, every sentence pair, failures with reasons, sha256 of
each shard file). `air-judge-<key>-N`: every verdict with prompt sha256 and raw response, judge
pins and log. `air-report`: `report.json` and `summary.md` (sha256 of the merged and judge files).
`merge`, `judge` and `report` are pure functions of those files, so any number can be re-derived:

```
uv run python scripts/ai_readability.py merge 'shards/shard-*.json' --out merged/readability.json
uv run python scripts/ai_readability.py report merged/readability.json 'judges/judge-*.json' --out report.json
```

Local or from olnm (`serve` uses docker, or `--llama-bin` for a built server):

```
uv run python scripts/fetch_l3_model.py qwen-1.5b models/qwen-1.5b/model.gguf
uv run python scripts/ai_readability.py serve --model qwen-1.5b
uv run python scripts/ai_readability.py restore --per-lang 1 --out out/shard-0.json
uv run python scripts/ai_readability.py stop
```

To swap a model, add it to `shared/l3_models.json` (revision, bytes, SHA-256) and pass its key.
Greedy decoding repeats answers, so this pipeline has one seed.
