"""Replay recorded paragraph judge answers (no LLM on the box).

As a restorer: looks up the answer recorded for a pack item id in
``<run>_seed<N>_blind.json``. The id is taken from the second argument or from
``PARA_ITEM`` (``run --cmd`` sets this per item). The prompt may be supplied on
stdin; when it is, its sha256 must match the pack item. Lookup is by item id
(``<paragraph>|<method>``), not by prompt sha256: CEF can leave a paragraph
unchanged, so the control and CEF prompts are then identical, but each item was
judged independently and may have a different answer.

    uv run python scripts/paragraph_roundtrip.py run --seed 1 \
        --cmd 'uv run python scripts/paragraph_replay.py 1'

reproduces the recorded run. ``--check`` verifies, without subprocesses, that

* with ``--rebuild``: items and packs are still what the current code builds (``build --check``;
  a later codec change makes them stale, which does not invalidate answers recorded against the
  committed packs, so this part is opt-in),
* every blind answer replays to itself through its pack item id (0 mismatches), and the stored
  prompt sha256 still matches the pack's sha256 for that id,
* ``<run>_results.json`` equals a fresh ``score`` of the recorded answers.

    uv run python scripts/paragraph_replay.py --check [--rebuild]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import paragraph_roundtrip as pr  # noqa: E402


def replay(seed: int, item_id: str, d: Path | None = None, prompt: str | None = None) -> str | None:
    """Return the recorded answer for pack item ``item_id``.

    The stored prompt sha256 must match the pack's sha256 for that id. If ``prompt``
    is given, its sha256 must also match the pack item.
    """
    pack = {p["id"]: p for p in pr.load_json(pr.path("pack", seed, d))}
    item = pack.get(item_id)
    if item is None:
        return None
    if prompt is not None and pr.sha256(prompt) != item["prompt_sha256"]:
        return None
    rec = (pr.load_blind(seed, d) or {"answers": {}})["answers"].get(item_id)
    if not rec or rec["prompt_sha256"] != item["prompt_sha256"]:
        return None
    return rec["answer"]


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
            elif replay(seed, iid, d) != rec["answer"]:
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
    seed = int(argv[0]) if argv else int(os.environ.get("PARA_SEED", "1"))
    iid = argv[1] if len(argv) > 1 else os.environ.get("PARA_ITEM")
    if not iid:
        print("item id required (argv or PARA_ITEM)", file=sys.stderr)
        return 2
    prompt = sys.stdin.read() if not sys.stdin.isatty() else None
    ans = replay(seed, iid, prompt=prompt if prompt else None)
    if ans is None:
        print("no recorded answer for this item", file=sys.stderr)
        return 2
    print(ans)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
