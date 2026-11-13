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
judged (it is then a second control).

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
5. **Error taxonomy** (per aligned pair, word tokens, punctuation ignored): `tense_swap`
   (English auxiliaries / same-stem verb change), `inflection_change` (same stem, other languages),
   `added_subject_object`, `dropped_subject_object`, `article_demonstrative`, `synonym_drift`
   (≤3-word replacement), `rewrite`, `added_content`, `dropped_content`, `merge_split`,
   `added_sentence`, `dropped_sentence`, `leftover_foreign` (a compressed-only word kept in the
   answer), `leftover_kanji_symbol` (CJK in a non-CJK paragraph or a symbol such as ○ → & kept),
   and the benign `contraction_or_variant`.
6. **Per-rule attribution**: each `source span → compressed span` edit the codec made is marked
   restored or not (an error overlapping its source span); `rules` in the results lists them by
   number of failures. Errors with no codec edit nearby are `unattributed` (judge noise; compare
   with `control`).
7. **AI readability**: 未測定 (not approved for this run).

## Reproducibility

`paragraph_roundtrip.py build --check` (sources → items → packs), `ingest` (raw → blind with
validation against the pack's prompt sha256), `score --check`, and `paragraph_replay.py --check`
(rebuild, replay every recorded answer through its prompt, re-score). `tiktoken` is used only by
`build` (dev group); everything else is stdlib.
