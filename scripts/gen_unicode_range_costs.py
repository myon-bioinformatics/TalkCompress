"""Print the per-code-point o200k cost strings used by ``sentence_calibrated_mosaic._RANGE_COSTS``.

    uv run python scripts/gen_unicode_range_costs.py
"""

import tiktoken

RANGES = {"_FULLWIDTH_COSTS": (0xFF01, 0xFF5E), "_HALFWIDTH_COSTS": (0xFF61, 0xFF9F),
          "_MATH_ALNUM_COSTS": (0x1D400, 0x1D7FF)}

if __name__ == "__main__":
    enc = tiktoken.get_encoding("o200k_base")
    for name, (a, b) in RANGES.items():
        s = "".join(str(min(9, len(enc.encode(chr(c))))) for c in range(a, b + 1))
        print(f"{name} = (")
        for i in range(0, len(s), 80):
            print(f'    "{s[i:i + 80]}"')
        print(")")
