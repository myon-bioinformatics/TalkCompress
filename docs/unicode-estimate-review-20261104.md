# Unicode estimator review — 2026-11-04

Baseline: main `d2510ee82853e0d8cef9edcf7c9808c977381f91` (#143 merged). Candidate: `fc07aee5d4046483295f9e3b994f2b8d508e93c5`. Python 3.14.9, tiktoken 0.14.0, o200k_base. Raw input, no added leading space.

Recommendation: adopt as a heuristic for natural text, with the limitations below. It is not a safe token-budget upper bound. No runtime changes were needed in this review.

## Reproduction

```sh
git worktree add ../baseline d2510ee82853e0d8cef9edcf7c9808c977381f91
uv run python scripts/audit_unicode_estimate.py --baseline ../baseline --output /tmp/unicode-audit.json
uv run python scripts/tokenizer_compat.py --agreement
uv run pytest -q tests/test_estimate_unicode_boundaries.py
```

The corpus is every `text` field under `tests/fixtures/corpus/**/*.jsonl` (4,734 rows). The 42,954-string set also counts metadata (IDs, language labels, licensing and source strings); it must not be described as 42,954 natural sentences. The original 42,980 denominator was not reproduced. Results below supersede the older aggregate for this pinned comparison.

| Set | N | Exact main → PR | MAE main → PR | Bias main → PR | Sum estimate / actual main → PR | Over rows main → PR | Under rows main → PR |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_jsonl_strings | 42954 | 0.4996 → 0.5000 | 1.719 → 1.561 | 0.061 → -0.111 | 1.0064 → 0.9883 | 7353 → 7274 | 14142 → 14203 |
| corpus | 4734 | 0.3504 → 0.3542 | 4.917 → 3.476 | -1.121 → -2.683 | 0.9651 → 0.9165 | 886 → 807 | 2189 → 2250 |
| arabic | 140 | 0.0643 → 0.0929 | 7.186 → 6.479 | -6.886 → -6.136 | 0.8760 → 0.8895 | 11 → 13 | 120 → 114 |
| bengali | 60 | 0.0167 → 0.1167 | 43.200 → 4.850 | 43.100 → -0.450 | 1.6321 → 0.9934 | 58 → 18 | 1 → 35 |
| deva | 114 | 0.0263 → 0.0702 | 26.684 → 6.719 | 18.333 → -4.246 | 1.2647 → 0.9387 | 56 → 20 | 55 → 86 |
| hebrew | 66 | 0.0152 → 0.0303 | 14.758 → 14.455 | -14.000 → -14.424 | 0.7642 → 0.7571 | 3 → 1 | 62 → 63 |
| tamil | 60 | 0.0167 → 0.1333 | 79.000 → 5.733 | 78.900 → -2.167 | 1.9977 → 0.9726 | 58 → 19 | 1 → 33 |
| random_bn | 3000 | 0.0597 → 0.0617 | 4.369 → 4.504 | -4.247 → -4.504 | 0.4505 → 0.4172 | 153 → 0 | 2668 → 2815 |
| random_ta | 3000 | 0.1330 → 0.0713 | 2.600 → 4.700 | -2.264 → -4.700 | 0.7135 → 0.4051 | 382 → 0 | 2219 → 2786 |
| random_km_my | 3000 | 0.0250 → 0.1127 | 6.674 → 3.227 | -6.649 → -3.227 | 0.2814 → 0.6513 | 37 → 0 | 2888 → 2662 |

MAE is mean absolute error in tokens per input. Bias is mean (estimate − actual). Aggregate ratio can conceal offsetting errors. Hebrew MAE improves slightly while its negative bias worsens. Natural-text MAE improves materially even though underestimation becomes more common.

Synthetic sets are 3,000 random code-point sequences each, seed 1203, length 1–16; they are not the original PR syllable generator and their scores must not be compared directly to its table. Random Tamil MAE worsens (2.600 → 4.700); Bengali worsens slightly (4.369 → 4.504). Random mixed Khmer/Myanmar improves under this generator, illustrating distribution sensitivity rather than proving generality. No threshold was fitted to these results.

## Boundaries and behavior

45 distinct NFC/NFD and context inputs are committed as regression cases, with separate frozen estimates and measured o200k references. Includes combining accents, Hebrew/Arabic marks, Devanagari nukta/conjuncts, ZWJ/ZWNJ, VS16, IVS and archaic jamo. Reference tests check actual tokenizer counts rather than claiming estimates are exact.

Known errors remain: NFD `x 한국어 y` 26 vs 27 and NFD `안녕하세요 세계` 48 vs 49 (already in main/#143); mixed contexts can differ by 2. Tamil `க்ஷ` 1 vs 3; contextual `x ☺️ y` 4 vs 5; IVS and archaic jamo byte-count fallback can overestimate because BPE may merge bytes. NFC/NFD inputs are deliberately not forced to have equal token estimates. These are approximate counts of raw strings, not normalization equivalence assertions.

SentenceCalibratedMosaic, ShorthandSessionEdge and MorphoGrammarMinimal compress/expand outputs were compared to main on 64 boundary inputs each (16 strings × NFC/NFD × bare/context): all 192 compressed and expanded outputs identical. This checks equality to baseline, not exact round-trip recovery of every source: existing normalization remains. The estimator change is outside compressor/expander implementations.

`tokenizer_compat.py --agreement`: natural sample 29/37, matrix 3057/3064, winner flips 0/1178 against o200k. This covers the committed matrix, not every possible future candidate. `calibrate_estimate.py --report`: train 2464/2464, held-out 593/600, flips 0/1122 (this script filters a different cell set).

Prior candidate CI run 41661705013: Python 3.11, 3.12, 3.13, 3.14 all successful. New commit checks must be reviewed separately before merge.

AI readability was not evaluated; tested compressed and expanded text is unchanged in the 192 comparisons.
