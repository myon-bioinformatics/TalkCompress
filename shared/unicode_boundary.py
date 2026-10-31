"""Unicode mark class for stdlib regular-expression word boundaries."""
from functools import lru_cache
import re
import sys
import unicodedata


@lru_cache(maxsize=1)
def mark_pattern() -> str:
    """Match one Mn/Mc/Me character using the running Python Unicode database."""
    return "[" + "".join(
        re.escape(chr(cp)) for cp in range(sys.maxunicode + 1)
        if unicodedata.category(chr(cp)).startswith("M")
    ) + "]"
