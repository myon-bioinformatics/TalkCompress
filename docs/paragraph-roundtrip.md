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
5. **Notation-tolerant** (`notation_tolerant`): exact, or equal after a closed, stdlib-only
   normalisation table (`notation_form` in `scripts/paragraph_roundtrip.py`). This is the third
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
   - whitespace, and trailing or separator punctuation (word-internal apostrophes and hyphens
     are kept).
   Lexical synonyms and other meaning-changing edits still fail (*at least* ≉ *about*,
   *Antwort* ≉ *Reaktion*, adding or dropping *the*). When two sentences match only by this
   table, they are not labelled as errors in the taxonomy (the difference is notation, not
   meaning). Number-word and percent-word lists are English; typographic folding applies to
   every language. Roman numerals and other lexical number names (*XV*, *quindecim*) are
   outside the table.
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
