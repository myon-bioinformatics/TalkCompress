# Focused test environment

Use `uv run --locked --only-group session-test --exact python -m pytest -q tests/test_session_cost.py tests/test_session_tokens.py` from the repository root.

This optional profile preserves pytest and the anyio plugin used by the full environment. It also preserves tiktoken and the existing terminal token-agreement report.

The default dependency groups and full CI remain unchanged. This command covers only the named tests; it does not replace the complete suite, Docker or real-browser checks.

## Local reference measurement (2026-11-03)

Linux x86_64, CPython 3.12.14, Node 26.13.0. Full source: 13bc33517ef7c974764f9ae439ee27f6cc33428c. Three new environments per profile, shared uv cache, alternating full/nano order. Same test identities/results, no skips, same plugin and common package versions. 10 tests passed per run.

Full to focused installed distributions: 26 to 14. Regular-file logical bytes after tests: 51,696,792 to 19,226,922. Excludes shared interpreter, symlinks and uv cache; includes bytecode. These measurements used an isolated explicitly pinned installation before this group was introduced, so they are reference values, not a measurement of the current lock command.

Install timing was not a fair cold-cache comparison (different sync/install paths and initial cache state); no installation or whole-CI speedup is claimed. Pytest-only was rejected because it dropped the anyio plugin and the tiktoken report.
