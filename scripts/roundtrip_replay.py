"""Replay restorer for scripts/roundtrip.py --cmd (no LLM API on the box).

Reads the round-trip prompt on stdin and prints the restoration recorded in
TesseraTalk/fixtures/roundtrip_judge/<lang>_blind.json. Those answers were written by an
AI judge (Grok Bot) reading ONLY the converted sentence (blind, no access to the source
English); the judge is deterministic, so every ROUNDTRIP_SEED gives the same answer.

    uv run python scripts/roundtrip.py --run --lang nl \
        --cmd 'uv run python scripts/roundtrip_replay.py nl'
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lang = sys.argv[1] if len(sys.argv) > 1 else "nl"
answers = json.loads((ROOT / f"TesseraTalk/fixtures/roundtrip_judge/{lang}_blind.json").read_text(encoding="utf-8"))
conv = sys.stdin.read().rsplit("\n\n", 1)[-1].strip()
print(answers.get(conv, ""))
