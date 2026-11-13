# Paragraph round-trip judge packs (run `para20261113`)

Judge input for the paragraph benchmark (`scripts/paragraph_roundtrip.py`, method in
`docs/paragraph-roundtrip.md`). 60 paragraphs × 3 judged methods (`control`, `CEF`, `BEF`) =
180 items per seed. Seeds 1–3 are three independent judgings of the same 180 prompts
(approved by myon on 2026-11-13, t1203: 3 seeds × 180 = 540 judge calls).

| file | what |
|---|---|
| `sources.json` | 60 source paragraphs with gold sentence lists and per-paragraph licence |
| `para20261113_items.json` | compressed text, o200k tokens and UTF-8 bytes for all 6 methods |
| `para20261113_seed<N>_pack.json` | **judge input for seed N** (list of 180 items) |
| `para20261113_seed<N>_raw.json` | judge answers for seed N (written by the helper) |
| `para20261113_seed<N>_blind.json` | `{id: answer}` made by `ingest` (replay source) |
| `para20261113_results.json` | scores made by `score` |

## Steps for a helper running seed N

You run **one seed only**. Use the same judge type as the other helpers:
**a fresh knowledgeWork-type subagent, one per item, with no other context.**

1. Open `para20261113_seed<N>_pack.json`. Each item is
   `{"id", "seed", "prompt", "compressed_text", "prompt_version", "prompt_sha256"}`.
2. For **each** of the 180 items, launch **one new** knowledgeWork subagent. Its whole task text
   is exactly `item["prompt"]`, nothing added: no id, no source text, no other items, no hints,
   no instruction about scoring. Any order and any parallelism are fine.
3. Record the subagent's final reply **verbatim** (only trim leading/trailing whitespace). Do not
   fix, reformat or re-ask because an answer looks wrong. Retry only on a technical failure
   (crash, empty reply, timeout); retry once with another fresh subagent and record
   `"attempts": 2`. If it fails again, record `"status": "timeout"` or `"error"` with `"answer": null`.
4. Write `para20261113_seed<N>_raw.json` in this directory:

```json
{
 "run": "para20261113",
 "seed": N,
 "judge": {"type": "knowledgeWork subagent (fresh, no context, one call per item)",
           "helper": "<your bot name>", "started_at": "<ISO 8601 with offset>",
           "finished_at": "<ISO 8601 with offset>"},
 "answers": [
  {"id": "en-pd-01|CEF", "prompt_sha256": "<copy from the pack item>",
   "status": "ok", "attempts": 1, "answer": "<verbatim reply>"}
 ]
}
```

   Every pack id must appear exactly once; `prompt_sha256` must be copied from the pack.
5. Validate and score (from the repository root):

```bash
uv run python scripts/paragraph_roundtrip.py ingest --seed N   # validates raw, writes _blind.json
uv run python scripts/paragraph_roundtrip.py score             # writes para20261113_results.json
uv run python scripts/paragraph_replay.py --check              # build/replay/results all reproducible
uv run pytest tests/test_paragraph_roundtrip.py
```

6. Do not edit `sources.json`, the items or the packs, and do not push. Report the raw file path,
   the number of `ok` / `timeout` / `error` answers and the judge type to the coordinator.

Replaying a recorded seed through the normal `--cmd` interface:

```bash
uv run python scripts/paragraph_roundtrip.py run --seed N --cmd 'uv run python scripts/paragraph_replay.py N'
```

(`run --cmd` sets `PARA_ITEM` to the pack item id so replay can distinguish methods that share a
prompt; this overwrites `_raw.json` with the replayed answers, so run it on a scratch copy).

## Sources and licences

* `*-flores-*` (de en es fr pt ja zh it nl el cs pl): FLORES-200 **devtest**, © Meta AI (NLLB Team),
  **CC BY-SA 4.0** (https://creativecommons.org/licenses/by-sa/4.0/), from
  `https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz`
  (sha256 `b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6`). Each record keeps the
  original Wikinews article URL and the devtest line numbers. One article = one paragraph; the same
  4 articles are used in every language (en has 2 more), so the languages are parallel.
* `en-pd-*`: public-domain (US) passages already in `tests/fixtures/pd_corpus/` (see its SOURCES.md).
* `la-caesar-*`: **FLORES-200 has no Latin.** Caesar, *De Bello Gallico* I, Project Gutenberg #218
  (public domain, US), file `https://www.gutenberg.org/cache/epub/218/pg218.txt`
  (sha256 `84ac8411841a4d8f5f4a49b6a2cd1f466917c6a5af72916d5e0b2b1ecb2f659c`), Gutenberg header and
  footer removed.
* Files in this directory that contain FLORES text, including compressed and restored versions
  (modified), are distributed under **CC BY-SA 4.0**. The code stays MIT.
* Rebuild / verify: `uv run python scripts/build_paragraph_sources.py [--check]` (downloads into the
  git-ignored `.cache/corpus/` and refuses a sha256 mismatch).
