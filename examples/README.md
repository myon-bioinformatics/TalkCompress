# TalkCompress examples

## Sample chat

[`sample_chat.jsonl`](sample_chat.jsonl) — short multi-role fake chat for ConvoZip demos.

## Copy-paste commands

```bash
# Pipeline C→E on plain text
uv run python ConvoZip/convo_zip.py --pipeline C,E --text "um thank you for your information"

# Budget: keep shrinking with default C,E until ≤40 chars (or no further shrink)
uv run python ConvoZip/convo_zip.py --budget 40 --stats --text "um thank you for your information please let me know"

# Role-aware JSONL: user→C, assistant→E, system unchanged
uv run python ConvoZip/convo_zip.py --jsonl --role-layers 'user=C,assistant=E,system=identity' --file examples/sample_chat.jsonl

# Pipeline + JSONL (same layers every line)
uv run python ConvoZip/convo_zip.py --pipeline C,E --jsonl --file examples/sample_chat.jsonl

# Compare layer densities
uv run python ConvoZip/convo_zip.py --compare --text "I have 3 animals and 2 people"

# Auto heuristic (B/C/E)
uv run python ConvoZip/convo_zip.py --auto --stats --text "Hello. こんにちは。Thanks a lot for your information."

# Trace steps to stderr
uv run python ConvoZip/convo_zip.py --pipeline C,E --trace --text "um thank you"

# Lex policy override (process-local)
uv run python ConvoZip/convo_zip.py --layer E --lex-policy /path/to/policy.json --text "um hello"
```

## Window chat

[`window_chat.jsonl`](window_chat.jsonl) — longer multi-role chat for `--window` / `--keep-system` demos.

```bash
uv run python ConvoZip/convo_zip.py --pipeline C,E --jsonl --window 3 --keep-system \
  --file examples/window_chat.jsonl

uv run python ConvoZip/convo_zip.py --profile mcp-short --jsonl --file examples/sample_chat.jsonl
```
