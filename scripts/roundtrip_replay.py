"""Replay restorer for scripts/roundtrip.py --cmd (no LLM API on the box).

Reads the round-trip prompt on stdin and prints the restoration recorded in
SentenceCalibratedMosaic/fixtures/roundtrip_judge/<lang>_blind.json. Those answers were written by an
AI judge (Grok Bot) reading ONLY the converted sentence (blind, no access to the source
English); the judge is deterministic, so every ROUNDTRIP_SEED gives the same answer.

    uv run python scripts/roundtrip.py --run --lang nl \
        --cmd 'uv run python scripts/roundtrip_replay.py nl'
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def answers(lang="nl"):
    return json.loads((ROOT / f"SentenceCalibratedMosaic/fixtures/roundtrip_judge/{lang}_blind.json").read_text(encoding="utf-8"))


def replay(prompt, lang="nl"):
    """Restoration recorded for the converted sentence at the end of ``prompt`` ("" when unknown)."""
    conv = prompt.rsplit("\n\n", 1)[-1].strip()
    return answers(lang).get(conv, "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog="Reads the prompt from stdin.")
    parser.add_argument("name", nargs="?", default="nl", help="replay to use (default: nl)")
    print(replay(sys.stdin.read(), parser.parse_args(argv).name))


if __name__ == "__main__":
    raise SystemExit(main())
