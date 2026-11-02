#!/usr/bin/env python3
"""manifest の外部取得エントリ（fetch_url あり）を取ってきて sha256 を照合する（stdlib のみ）。

urlopen には TIMEOUT 秒のタイムアウトを付け、id は ID_RE で検証して
保存先が cache ディレクトリの外に出ないことを確認する。

  uv run python scripts/corpus_fetch.py            # 全外部エントリを取得
  uv run python scripts/corpus_fetch.py --id X     # 1 件だけ

保存先は既定で .cache/corpus/<lang>/<id>（git 管理外）。sha256 が manifest と
一致しなければ保存せずに失敗する。ネットワークを使うので CI からは呼ばない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_manifest import MANIFEST, ROOT, validate_manifest  # noqa: E402

CACHE = ROOT / ".cache" / "corpus"
TIMEOUT = 60  # 秒。urlopen が無期限に固まらないように
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def cache_path(e: dict, cache: Path) -> Path:
    """id / lang を検証し、cache 配下に収まる保存先を返す（パストラバーサル防止）。"""
    for k in ("id", "lang"):
        v = e.get(k)
        if not isinstance(v, str) or not ID_RE.match(v):
            raise ValueError(f"{k} {v!r} は保存先に使えない（英数・._:- のみ、先頭は英数）")
    root = cache.resolve()
    dest = (root / e["lang"] / e["id"]).resolve()
    if not dest.is_relative_to(root):
        raise ValueError(f"保存先 {dest} が cache の外")
    return dest


def verify_bytes(data: bytes, expected: str) -> None:
    got = hashlib.sha256(data).hexdigest()
    if got != expected:
        raise ValueError(f"sha256 不一致: 期待 {expected} 実際 {got}")


def fetch_entry(e: dict, cache: Path = CACHE, opener=urllib.request.urlopen) -> Path:
    dest = cache_path(e, cache)
    if dest.is_file():
        verify_bytes(dest.read_bytes(), e["sha256"])
        return dest
    with opener(e["fetch_url"], timeout=TIMEOUT) as r:
        data = r.read()
    verify_bytes(data, e["sha256"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--id")
    ap.add_argument("--cache", type=Path, default=CACHE)
    a = ap.parse_args(argv)
    m = json.loads(a.manifest.read_text(encoding="utf-8"))
    errs = validate_manifest(m)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    rc = 0
    for e in m["entries"]:
        if "fetch_url" not in e or (a.id and e["id"] != a.id):
            continue
        try:
            print(fetch_entry(e, a.cache))
        except (OSError, ValueError) as ex:
            print(f"{e['id']}: {ex}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
