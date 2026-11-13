"""Replay recorded paragraph judge answers (no LLM on the box).

As a restorer: reads a paragraph prompt on stdin and prints the answer recorded for it in
``<run>_seed<N>_blind.json`` (looked up by the prompt's sha256 in the seed's pack), so

    uv run python scripts/paragraph_roundtrip.py run --seed 1 \
        --cmd 'uv run python scripts/paragraph_replay.py 1'

reproduces the recorded run. ``--check`` verifies, without subprocesses, that

* with ``--rebuild``: items and packs are still what the current code builds (``build --check``;
  a later codec change makes them stale, which does not invalidate answers recorded against the
  committed packs, so this part is opt-in),
* every blind answer replays to itself through its pack prompt (0 mismatches),
* ``<run>_results.json`` equals a fresh ``score`` of the recorded answers.

    uv run python scripts/paragraph_replay.py --check [--rebuild]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import paragraph_roundtrip as pr  # noqa: E402


def replay(seed: int, prompt: str, d: Path | None = None) -> str | None:
    pack = pr.load_json(pr.path("pack", seed, d))
    blind = pr.load_blind(seed, d) or {"answers": {}}
    h = pr.sha256(prompt)
    for item in pack:
        if item["prompt_sha256"] == h:
            rec = blind["answers"].get(item["id"])
            return rec["answer"] if rec else None
    return None


def check(d: Path | None = None, *, rebuild: bool = False) -> list[str]:
    problems: list[str] = []
    if rebuild:
        for p, text in pr.build_all().items():
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                problems.append(f"stale: {p.name} (run paragraph_roundtrip.py build)")
    scored = 0
    for seed in pr.SEEDS:
        blind = pr.load_blind(seed, d)
        if blind is None:
            continue
        scored += 1
        pack = {p["id"]: p for p in pr.load_json(pr.path("pack", seed, d))}
        for iid, rec in blind["answers"].items():
            if iid not in pack:
                problems.append(f"seed {seed}: {iid} not in pack")
            elif rec["prompt_sha256"] != pack[iid]["prompt_sha256"]:
                problems.append(f"seed {seed}: {iid} answered a different prompt")
            elif replay(seed, pack[iid]["prompt"], d) != rec["answer"]:
                problems.append(f"seed {seed}: {iid} replay mismatch")
    res = pr.path("results", None, d)
    if scored:
        if not res.is_file() or res.read_text(encoding="utf-8") != pr.dumps(pr.current_results(d)):
            problems.append("results stale (run paragraph_roundtrip.py score)")
    return problems


def main(argv: list[str]) -> int:
    if argv[:1] == ["--check"]:
        problems = check(rebuild="--rebuild" in argv)
        print("paragraph replay: OK" if not problems else "\n".join(problems))
        return 1 if problems else 0
    seed = int(argv[0]) if argv else 1
    ans = replay(seed, sys.stdin.read())
    if ans is None:
        print("no recorded answer for this prompt", file=sys.stderr)
        return 2
    print(ans)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
