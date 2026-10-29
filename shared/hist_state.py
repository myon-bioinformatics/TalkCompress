"""G2 hist-state: replace old chat turns with a fixed-slot state block.

Rule-based, stdlib only, no model calls. Old rows (everything except system
rows and the last ``keep_recent`` rows) are not dropped. They are read into
four slots and written as one system row:

- 決定 (decided): rows that state a decision or agreement
- 未決 (open): rows that ask a question or leave something pending
- 識別子・数値 (ids): exact items (URL, path, SHA, date, #N, number) from keep_check
- 次の一手 (next): the last user row among the old rows
- tool results: old ``role=tool`` rows are cleared to a count (G9, rule form)

Usage::

    uv run python shared/hist_state.py --file chat.jsonl --keep-recent 3 [--check]

``--check`` runs keep_check (G3) between the old text and the state block and
prints the report. Exit status is 0 when the check passes or is not requested.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from keep_check import check, extract_exact

DECIDED_RE = re.compile(
    r"\b(?:decided|agreed|go with|will use|chose|adopt(?:ed)?)\b|決定|採用|合意|にする|で行く",
    re.IGNORECASE,
)
OPEN_RE = re.compile(
    r"\?|？|\bTODO\b|\bTBD\b|\bpending\b|\bunclear\b|\bopen question\b|未決|保留|確認",
    re.IGNORECASE,
)


def _unique(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def build_state(old_rows: list[dict]) -> tuple[str, int]:
    """Return (state text, number of cleared tool rows) for the old rows."""
    decided: list[str] = []
    open_items: list[str] = []
    texts: list[str] = []
    cleared = 0
    next_step = ""

    for row in old_rows:
        role = str(row.get("role") or "").lower()
        text = str(row.get("text") or "").strip()
        if role == "tool":
            cleared += 1
            continue
        if not text:
            continue
        texts.append(text)
        if role == "user":
            next_step = text
        if DECIDED_RE.search(text):
            decided.append(text)
        if OPEN_RE.search(text):
            open_items.append(text)

    ids: list[str] = []
    for kind_items in extract_exact("\n".join(texts)).values():
        ids.extend(sorted(kind_items))

    lines = ["[state]", "決定:"]
    lines.extend(f"- {t}" for t in _unique(decided) or ["なし"])
    lines.append("未決:")
    lines.extend(f"- {t}" for t in _unique(open_items) or ["なし"])
    lines.append("識別子・数値: " + (", ".join(_unique(ids)) if ids else "なし"))
    lines.append("次の一手: " + (next_step if next_step else "なし"))
    if cleared:
        lines.append(f"ツール結果: {cleared} 件を削除（件数のみ残す）")
    lines.append("[/state]")
    return "\n".join(lines), cleared


def summarize_old(rows: list[dict], keep_recent: int) -> tuple[list[dict], str, int]:
    """Replace old non-system rows with one state row.

    Returns (new rows, state text, cleared tool rows). System rows stay at the
    top in their original order; the last ``keep_recent`` non-system rows stay
    verbatim after the state row.
    """
    system = [r for r in rows if str(r.get("role") or "").lower() == "system"]
    body = [r for r in rows if str(r.get("role") or "").lower() != "system"]
    if keep_recent < 0:
        raise ValueError("keep_recent must be >= 0")
    if len(body) <= keep_recent:
        return list(rows), "", 0

    old = body[: len(body) - keep_recent] if keep_recent else body
    recent = body[len(body) - keep_recent :] if keep_recent else []
    state, cleared = build_state(old)
    state_row = {"role": "system", "text": state}
    return system + [state_row] + recent, state, cleared


def _old_text(rows: list[dict], keep_recent: int) -> str:
    body = [r for r in rows if str(r.get("role") or "").lower() != "system"]
    old = body[: len(body) - keep_recent] if keep_recent else body
    return "\n".join(str(r.get("text") or "") for r in old if str(r.get("role") or "").lower() != "tool")


def _load(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        rows.append({"role": obj.get("role"), "text": obj.get("text", "")})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--keep-recent", type=int, default=3)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows = _load(args.file)
    new_rows, state, cleared = summarize_old(rows, args.keep_recent)
    for row in new_rows:
        json.dump(row, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")

    if not args.check:
        return 0
    report = check(_old_text(rows, args.keep_recent), state)
    print(
        json.dumps(
            {"ok": report.ok, "missing": report.missing, "count_drops": report.count_drops, "cleared_tool_rows": cleared},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
