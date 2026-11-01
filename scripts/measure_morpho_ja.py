"""MorphoZip を日本語口語サンプル（324 字）にかけ、o200k トークン数とバイト数を測る。

    uv run python scripts/measure_morpho_ja.py [--ref origin/main]

--ref を付けると、その git ref の MorphoZip/morpho_zip.py と比べる。
"""
import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SAMPLE = ROOT / "tests/fixtures/ja_colloquial_324.txt"
ENC = tiktoken.get_encoding("o200k_base")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stat(s: str) -> str:
    return f"{len(ENC.encode(s))} / {len(s.encode())}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref")
    args = ap.parse_args()
    text = SAMPLE.read_text().strip()
    print(f"字数 {len(text)}")
    print(f"原文            {stat(text)}")
    mods = {"この版": load(ROOT / "MorphoZip/morpho_zip.py", "mz_cur")}
    if args.ref:
        src = subprocess.run(["git", "show", f"{args.ref}:MorphoZip/morpho_zip.py"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
        tmp = Path(tempfile.mkdtemp()) / "morpho_zip.py"
        tmp.write_text(src)
        mods = {args.ref: load(tmp, "mz_ref"), **mods}
    for label, mz in mods.items():
        out = mz.compress(text, aggressive_fillers=True)
        print(f"{label:<15} {stat(out)}")
        print(f"  {out}")


if __name__ == "__main__":
    main()
