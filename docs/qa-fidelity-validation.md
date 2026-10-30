# QA fidelity scoring correction (2026-10-30)

## Historical measurements

[Original validation](https://github.com/myon-bioinformatics/TalkCompress/pull/43#issuecomment-6514000115)
used head `db035aa04fa0d2e7b47ab18878e44347fcfd735f`.
The unmodified scorer accepted substring matches, reasoning text and truncated
HTTP output. Its scores must not be interpreted as completed-answer fidelity.
The previously returned local correction ran 1646 tests successfully (1 xfailed),
and Qwen2.5 1.5B completed 29/29 requests with `finish_reason=stop`.
That correction reported 6/7 for each of prose, bullets and newline-only text.
Those are historical local-patch measurements, not fresh inference on this commit.

## Incorporated correction

The original four-file patch was reused. Questions enumerate values by kind
without embedding expected identifiers. Calendar dates accept validated ISO,
slash-separated, Japanese and English full-month forms. Exact values use
boundaries; paths, URLs and supplied identifiers retain case sensitivity.
Reasoning blocks are excluded. Empty or reasoning-only answers raise errors.
The HTTP wrapper requires `finish_reason=stop`; length, null and other reasons
are errors, not incorrect answers. Arbitrary commands must themselves reject
incomplete generation: stdout alone cannot convey a model's finish reason.

Language labels such as `ES/DE/FR` no longer create path probes. This is a
limited explicit language-code heuristic (ES, DE, FR, EN, JA, PT, IT, ZH, KO).
Use an explicit `./` prefix for a real path consisting only of these codes.
Zero probes produce `status=not_applicable`, `score=null`, `total=0`, with no
model call. A scored zero remains `status=scored`, `score=0.0`.

## Offline replay after correction

`qa-fidelity-replay.json` records offline rescoring of existing Qwen2.5 answers,
including the source answer-log SHA-256. No model was rerun. All surviving
questions are identical to the previous local-patch questions.

| Form | Previous local-patch score | Current offline replay |
| --- | --- | --- |
| Prose | 6/7 | 6/6 |
| Bullets | 6/7 | 6/6 |
| Newlines only | 6/7 | 6/6 |

The denominator changed because the spurious language-label path was removed;
this is not evidence of improved model capability. Samples s2, s3 and s4 now
have zero probes and are not applicable. Existing s1 results stay 4/4 in each
form. Historical empty-context and value-removal controls remain historical
0/4 results; no new inference is claimed here. This metric tests retrieval of
protected values, not general meaning, negation, conditions or answer precision.

## Review and verification

Regression tests cover longer identifiers, numeric boundaries, case-sensitive
paths/URLs, equivalent and invalid dates, think blocks, incomplete HTTP responses,
answer leakage through questions, language labels and zero-probe behavior.
Independent review found additional numeric/case/URL boundary issues, which were
fixed; re-review ran 28 relevant tests successfully and found no blocking issue.
Full pytest and GitHub Actions results are recorded on the PR for the final head.

