"""大文字1文字語 A–Z の監査: 例文の型 × 26文字 × 全規則経路を機械的に総当たりする。

型の ``_`` に A–Z を入れ、MorphoZip / ShorthandEdge の各経路に通したあと、その文字が
単独記号（前に英字なし・後ろに小文字なし）として入力と同数残るかを判定する。
意図的に残さない組み合わせは ``EXEMPT`` の明示一覧だけ（文頭の冠詞 A）。

``--md`` で PR 用の表（型 × 経路ごとの失敗文字）を出す。``--hyphen`` でハイフン連結案
（``Plan A`` → ``Plan-A``）の o200k トークン/バイトと往復可否を測る。
"""
from __future__ import annotations

import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from MorphoZip.morpho_zip import compress as morpho  # noqa: E402
from ShorthandEdge.shorthand_edge import compress as shorthand  # noqa: E402

LETTERS = string.ascii_uppercase

# (型名, 例文の型)。``_`` が大文字1文字の位置。
TEMPLATES: list[tuple[str, str]] = [
    ("label", "Then Plan _ failed."),
    ("label_end", "We chose Plan _."),
    ("vitamin", "Take vitamin _ daily."),
    ("type_grade", "Type _ blood got grade _ marks."),
    ("subj_said", "_ said no."),
    ("subj_is", "_ is larger than B."),
    ("subj_mid", "Then _ said no."),
    ("choose", "Choose _ or B now."),
    ("ifthen", "If _ then Y holds."),
    ("mid", "We chose _ over the rest."),
    ("start_and", "_ and B are fine."),
    ("enum", "Take _, B, and C."),
    ("paren", "Use option (_) here."),
    ("paren_start", "Use it (_ is best)."),
    ("quote", 'Mark it "_" now.'),
    ("quote_start", 'He said "_ or B".'),
    ("alnum", "Use _4 paper."),
    ("slash", "Run _/B tests."),
    ("abbr", "He joined the _.S. army."),
    ("initial", "Then J. _. Smith came."),
    ("start_article", "_ cat sat."),
    ("after_stop_article", "Hi. _ cat sat."),
]

# 意図的に残さない組み合わせ（文頭の冠詞 A）。ここ以外の失敗はすべて不具合。
EXEMPT: frozenset[tuple[str, str]] = frozenset(
    {("A", "start_article"), ("A", "after_stop_article")}
)

PIPES = {
    "MorphoZip": morpho,
    "MorphoZip(strip+aggr+spelled)": lambda t: morpho(
        t, strip=True, aggressive_fillers=True, spelled_nums=True
    ),
    "ShorthandEdge(ledger)": shorthand,
    "ShorthandEdge(precision)": lambda t: shorthand(t, prefer_precision=True),
}


def standalone_count(letter: str, text: str) -> int:
    return len(re.findall(rf"(?<![A-Za-z]){letter}(?![a-z])", text))


def check(letter: str, template: str, fn) -> tuple[bool, str]:
    src = template.replace("_", letter)
    got = fn(src)
    return standalone_count(letter, got) == standalone_count(letter, src), got


def run() -> list[tuple[str, str, str, str]]:
    fails = []
    for tname, tpl in TEMPLATES:
        for L in LETTERS:
            if (L, tname) in EXEMPT:
                continue
            for pname, fn in PIPES.items():
                ok, got = check(L, tpl, fn)
                if not ok:
                    fails.append((tname, pname, L, got))
    return fails


def md_table(fails) -> str:
    rows = ["| 型 | 例文 | " + " | ".join(PIPES) + " |", "|---|---|" + "---|" * len(PIPES)]
    for tname, tpl in TEMPLATES:
        cells = []
        for p in PIPES:
            bad = "".join(L for t, pp, L, _ in fails if t == tname and pp == p)
            cells.append(f"NG: {bad}" if bad else "26/26 保持")
        ex = "".join(L for L in LETTERS if (L, tname) in EXEMPT)
        note = f" (除外: {ex})" if ex else ""
        rows.append(f"| {tname}{note} | `{tpl}` | " + " | ".join(cells) + " |")
    return "\n".join(rows)


# --- ハイフン連結案 ---------------------------------------------------------
_HYPHEN_JOIN = re.compile(r"(?<=[A-Za-z]) (?=[A-Z](?![\w.'/-]))")


def hyphen_join(text: str) -> str:
    """前の語に続く大文字1文字を ``-`` でつなぐ（``Plan A`` → ``Plan-A``）。"""
    return _HYPHEN_JOIN.sub("-", text)


def main() -> int:
    fails = run()
    if "--md" in sys.argv:
        print(md_table(fails))
    for f in fails:
        print(*f, sep="\t")
    total = len(TEMPLATES) * len(LETTERS) - len(EXEMPT)
    print(f"NG {len(fails)} / {total * len(PIPES)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
