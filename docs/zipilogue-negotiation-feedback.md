# Zipilogue negotiation failure diagnosis and structured feedback

## Saved evidence

`Zipilogue/results/negotiation-failure-diagnosis.json` classifies the original
four-round reports without modifying them. Qwen2.5-1.5B records one
"unobserved phrase" validator error and three unlocalized peer rejections.
However, all eight proposed long forms actually occur in its saved training
prompt. Replaying each rule through the current validator finds six length
violations (103–113 characters), not an unobserved phrase. The saved error is
therefore inconsistent with its prompt/proposal; historical validator behavior
cannot be inferred from the error alone. The JSON separates saved classifications
from current per-rule replay. MiniCPM nonthinking v2 has four
length violations and never reaches peer review. A peer's vague claim of ambiguity
is not evidence that a particular rule corrupts meaning. The historic reports
cannot resolve that question. Neither original run evaluated held-out receivers.

## Changes

The sender receives up to 40 repeated word spans extracted deterministically from
training texts only. These are suggestions, not adopted rules. Codes remain the
sender's choice, every proposal passes the original validator, and every peer must
approve the frozen proposal. The held-out data never enters negotiation prompts.

Peer JSON now requires `accept` (boolean), a nonempty `reason`, and `issues`.
Approval requires an empty issues list. Rejection requires at least one object:

```json
{"rule_index":0,"category":"ambiguity","reason":"Describe the concrete alternate reading for this exact rule."}
```

Indices refer to the zero-based frozen mapping. Categories are `meaning`,
`ambiguity`, `collision`, and `decodability`. These are peer-asserted concerns,
not automatically verified defects. Structural validation cannot determine whether
free-text reasoning is persuasive. Missing/invalid issue localization is a
`peer_vote_contract` failure and remains a veto. No repair turns a rejection into
approval. The next sender sees the previous mapping plus indexed issues or exact
contract/validation error; critiques no longer float free of their proposal.

Failures are separated as `proposal_output`, `proposal_validation`, `peer_output`,
`peer_vote_contract`, and `peer_semantic_rejection`. Invalid proposals never reach
peer review. Model output/transport errors consume bounded rounds and retain logs.
Failed negotiations retain costs and `not_run_no_agreement`; tokenizer failure is
explicitly recorded with null cost, never estimated. No receiver summary is created
without agreement.

Successful runs retain the 20-case raw/shared/unshared comparison. Each arm reports
success rate and total prompt + completion content tokens plus negotiation.
Dictionary tokens are already included in each shared receiver prompt. These totals
exclude chat-template overhead and are distinct from the one-book wire-amortization
metric. Server usage remains in raw calls. Negotiation cost is charged to each arm
for comparison; summing those arm totals would triple-count that shared cost.

## Live observations, 2026-10-31

Both pre-existing local GGUF files were inspected for metadata; model hashes and
server commit/settings are in the corresponding provenance JSON. Download origin
was not independently established. Both are Q4_K_M, seed 42, one group, two peers,
four rounds, with unchanged proposal output budget 512.

| Model | Result | Held-out receiver evaluation |
| --- | --- | --- |
| Qwen2.5-0.5B Instruct | Four incomplete proposal outputs | Not run |
| Qwen2.5-1.5B Instruct | Four incomplete proposal outputs | Not run |

Both models repeated content until the output limit. The reports retain raw output
and `finish_reason=length`; no truncated JSON is rescued into a valid proposal.
Candidate availability and structured-feedback behavior are verified by tests, but
these live runs do **not** establish improved agreement or semantic restoration.
No successful rulebook or receiver-quality result is claimed. The MiniCPM model
was not available for a new run. A next experiment can isolate candidate selection
by index or compare constrained output against free generation; that would be a
new experimental condition, not a reinterpretation of these failures.

Reproduce with a local llama.cpp server, then:

```sh
python -m Zipilogue.dialogue_lab --groups 1 --peers 2 --rounds 4 --output report.json
python -m pytest -x -q tests/test_dialogue_lab.py tests/test_rulebook.py tests/test_meaning_preserve_dialogue.py
```

Independent code review found a lost-report risk when tokenization failed; it was
fixed and covered with a regression. Reviewer independently verified all 28 dialogue
unit tests and found no remaining blocking issues. Tests use scripted clients and
are protocol evidence only, not live-model evidence.
