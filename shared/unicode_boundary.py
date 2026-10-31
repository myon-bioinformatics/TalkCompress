"""Unicode mark class for stdlib regular-expression word boundaries."""
from functools import lru_cache
import re
import sys
import unicodedata


@lru_cache(maxsize=1)
def mark_pattern() -> str:
    """Match one Mn/Mc/Me character using the running Python Unicode database.

    Group adjacent code points to keep compiled regexes small.
    """
    ranges: list[str] = []
    start = end = -1
    for cp in range(sys.maxunicode + 1):
        if not unicodedata.category(chr(cp)).startswith("M"):
            continue
        if cp == end + 1:
            end = cp
            continue
        if start >= 0:
            ranges.append(_range(start, end))
        start = end = cp
    if start >= 0:
        ranges.append(_range(start, end))
    return "[" + "".join(ranges) + "]"


def _range(start: int, end: int) -> str:
    first = re.escape(chr(start))
    return first if start == end else first + "-" + re.escape(chr(end))
