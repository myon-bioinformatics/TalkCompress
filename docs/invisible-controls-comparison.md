# Invisible controls in token estimation (#147)

Baseline: `adf9fcf49e2f7ee8695819e00929f9bd0673c6ae` (main, includes #145).
Evaluation: CPython 3.14.9, tiktoken 0.14.0, `o200k_base`, raw strings with no
added leading space. Both receive identical text. Estimator retains its existing
NFC policy. This changes estimates only; it does not change `_PRETOKEN`, corpus,
calibration tables, script rates, or compression/expansion code.

## Comparison and selected rule

Candidates use the existing block rates, with no word exceptions or fitted constants:

- `include_all`: merge interior U+200B–200D into an `i` run, exclude them from
  the length, round once for the whole run.
- `correct_all`: retain fragmented runs and their rounding, subtract the control's
  existing estimate between `i` fragments.
- `selected`: retain fragmentation; omit the charge for a **single** ZWSP between
  characters in the same Khmer or Lao block, or ZWJ within the Sinhala block.
  Leading, trailing, repeated controls, cross-block boundaries, ZWNJ and other
  scripts remain unchanged. Emoji ZWJ sequences remain unchanged.

The selection uses fit MAE and boundary regressions. Generic inclusion and generic
correction undercount Bengali conjuncts and Oriya examples. Myanmar's selected
(single-control, same-block) correction slightly worsened fit MAE (1.765→1.770),
so Myanmar was excluded before accepting the scoped rule. No parameters were
optimized against held-out. Held-out is a final gate, not proof of universal accuracy.

| Constructed example | o200k | main | include_all | correct_all | selected |
|---|---:|---:|---:|---:|---:|
| Sinhala `ශ්‍රී` | 2 | 5 | 3 | 4 | 4 |
| Bengali `ক্‍ষ` (ZWJ) | 4 | 3 | 1 | 2 | 3 |
| Bengali `ক্‌ষ` (ZWNJ) | 4 | 3 | 1 | 2 | 3 |
| Khmer `កម្ពុជា​ជាប្រទេស​ដ៏ស្រស់ស្អាត` (ZWSP) | 15 | 21 | 18 | 19 | 19 |
| Oriya `ଓଡ଼ିଆ` | 7 | 2 | 2 | 2 | 2 |
| Emoji `👨‍👩‍👧‍👦` | 11 | 11 | 11 | 11 | 11 |

The natural Khmer sentence [1172554](https://tatoeba.org/en/sentences/show/1172554)
also reproduces the issue: o200k=41, main=57, selected=43.

Exact code points, o200k token IDs and additional mixed-script/boundary cases are
in [the JSON report](invisible-controls-comparison.json). Sinhala's residual
error and Oriya's existing underestimation are intentionally not hidden by word
exceptions. Oriya's ZWSP/ZWNJ/ZWJ examples are unchanged by the selected rule.

## Tatoeba evaluation

Same procedure as #145: deduplicate text, sort, shuffle with a fresh
`random.Random(1104)` per language, first `min(200, n//2)` for fit and the next
same-sized disjoint slice for held-out. Ratio = sum(estimates)/sum(o200k).
Input hashes, source export URLs, sentence IDs, split membership and per-row
counts are recorded in the JSON. Controls are naturally present, not inserted
into the corpus. The 400 sampled Bengali sentences contain **no** controls;
therefore their unchanged result is not evidence of control accuracy.

| Language | n per split | fit MAE main→selected | held MAE main→selected | held ratio main→selected |
|---|---:|---:|---:|---:|
| Bengali | 200 | 1.810→1.810 | 1.570→1.570 | .9710→.9710 |
| Sinhala | 37 | 1.378→1.243 | .892→.838 | .9668→.9616 |
| Khmer | 200 | 1.805→1.500 | 2.180→1.580 | 1.0760→1.0200 |
| Lao | 115 | 4.817→4.417 | 4.200→4.174 | 1.0797→1.0792 |
| Thai | 200 | .360→.360 | .310→.310 | .9716→.9716 |
| Tamil | 200 | 1.630→1.630 | 1.660→1.660 | .9717→.9717 |
| Myanmar | 200 | 1.765→1.765 | 1.615→1.615 | 1.0318→1.0318 |
| Oriya (ori) | 200 | 8.280→8.280 | 9.215→9.215 | .3842→.3842 |

All sampled languages pass the held-out MAE gate. Sinhala's aggregate ratio moves
slightly farther below 1 while MAE improves: improvement is not uniform across
metrics or sentences. Sinhala has only 5 control-containing sentences per split;
Lao only 4 fit and 1 held-out. More independent data is needed for stronger claims.

For Khmer held-out, inclusion MAE=1.630, generic correction=1.590, selected=1.580.
Fit: 1.575 / 1.535 / 1.500, respectively. This supports retaining fragmentation.

A separate **diagnostic**, not another held-out set, evaluates all natural control
sentences in each downloaded export. For Bengali (14 sentences), MAE is
2.143 main, 2.857 inclusion, 2.571 generic correction, and 2.143 selected.
For Sinhala (10), selected MAE 1.400→.700; Khmer (322), 5.848→2.065;
Lao (5), 24.600→14.800. These subsets overlap fit/held-out; do not count them as
independent validation. The `ory` export returned HTTP 404, but the `ori` export is available and is
included above. Oriya has a substantial pre-existing underestimation; this PR
preserves its outputs rather than extending the correction to an uncalibrated block.

## Reproduction

From the repository root:

```sh
uv run python scripts/compare_invisible_controls.py \
  --data-dir /tmp/tatoeba-147 --download \
  --expected docs/invisible-controls-comparison.json \
  --output /tmp/invisible-controls-comparison.json
uv run pytest -q
uv run python scripts/tokenizer_compat.py --agreement
uv run python scripts/tense_matrix.py --check
```

The exports are mutable: `--expected` **fails explicitly** if an input hash changes.
Preserve the eight downloaded `.tsv.bz2` inputs for an exact replay. Without
`--expected`, a later export can be measured as a new experiment, not represented
as reproducing this snapshot. No raw corpus text is redistributed; sentence IDs
can be resolved at `https://tatoeba.org/en/sentences/show/<ID>`.

## Validation

- 25 focused boundary tests pass; expected estimates are frozen independently of
  the evaluation implementation.
- Winner flips: **0/1178**; natural sample exact 29/37; matrix exact 3057/3064.
- `tense_matrix.py --check`: up to date.
- Compression/expansion baseline comparison covers all 2,704 fit/held-out strings
  and 29 examples, each with RLE on, RLE off/newline preservation, and fixture
  translation minification on: 8,199 comparisons. Outputs and their expansions
  must match baseline byte for byte. This is a measured corpus guarantee, not a
  claim about all possible future translation candidate rankings.
