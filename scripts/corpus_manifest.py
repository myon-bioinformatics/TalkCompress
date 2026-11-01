#!/usr/bin/env python3
"""多言語テストコーパスの manifest を計測・検証する（stdlib のみ。o200k 計測だけ tiktoken を使う）。

使い方:
  uv run python scripts/corpus_manifest.py measure tests/fixtures/corpus/ja/short.jsonl
  uv run python scripts/corpus_manifest.py update   # 同梱ファイルの count/bytes/o200k_tokens/sha256 を再計算
  uv run python scripts/corpus_manifest.py check    # スキーマ検証 + 同梱ファイルの数値一致を確認

置き場所は tests/fixtures/corpus/<category>/<lang>.jsonl。
JSONL 1 行 = 1 レコード {"id","text","lang","tier","source","license","author","url"}（tier は short/medium/long）。
bytes は各 text の UTF-8 バイト数の合計、o200k_tokens は各 text を個別に
o200k_base でエンコードしたトークン数の合計、sha256 はファイル全体のハッシュ。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "tests" / "fixtures" / "corpus"
MANIFEST = CORPUS_DIR / "manifest.json"
SCHEMA_VERSION = 1

# docs/corpus.md の「許可ライセンス」と一致させること。NC / ND / 不明は不可。
ALLOWED_LICENSES = {
    "CC0 1.0",
    "Public domain",
    "CC BY 2.0 FR",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
}
TIERS = {"short", "medium", "long"}
UNMEASURED = "未測定"
REQUIRED = (
    "id", "category", "source", "url", "license", "license_url", "lang",
    "count", "bytes", "o200k_tokens", "sha256", "retrieved_at", "ai_roundtrip",
)
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def validate_entry(e: object, idx: int = 0) -> list[str]:
    p = f"entries[{idx}]"
    if not isinstance(e, dict):
        return [f"{p}: object ではない"]
    errs = [f"{p}: {k} がない" for k in REQUIRED if k not in e]
    if errs:
        return errs
    if ("path" in e) == ("fetch_url" in e):
        errs.append(f"{p}: path（同梱）か fetch_url（外部取得）のどちらか一方が必要")
    for k in ("id", "category", "source", "url", "license_url", "lang", "license", "ai_roundtrip"):
        if not isinstance(e[k], str) or not e[k]:
            errs.append(f"{p}: {k} は空でない文字列")
    if errs:
        return errs
    if e["license"] not in ALLOWED_LICENSES:
        errs.append(f"{p}: license {e['license']!r} は許可リスト外（NC/ND/不明は不可）")
    if not CAT_RE.match(e["category"]):
        errs.append(f"{p}: category は小文字英数・_・-")
    if not LANG_RE.match(e["lang"]):
        errs.append(f"{p}: lang は ISO 639 コード")
    for k in ("count", "bytes", "o200k_tokens"):
        v = e[k]
        if type(v) is not int or v < 0:
            errs.append(f"{p}: {k} は 0 以上の整数")
    if not isinstance(e["sha256"], str) or not SHA_RE.match(e["sha256"]):
        errs.append(f"{p}: sha256 は 64 桁の小文字 16 進")
    if not isinstance(e["retrieved_at"], str) or not DATE_RE.match(e["retrieved_at"]):
        errs.append(f"{p}: retrieved_at は YYYY-MM-DD")
    if "path" in e:
        path = e["path"]
        if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts:
            errs.append(f"{p}: path は corpus/ からの相対パス")
        elif Path(path).parts != (e["category"], f"{e['lang']}.jsonl"):
            errs.append(f"{p}: path は <category>/<lang>.jsonl")
    return errs


def validate_manifest(m: object) -> list[str]:
    if not isinstance(m, dict):
        return ["manifest は object"]
    errs: list[str] = []
    if m.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version は {SCHEMA_VERSION}")
    entries = m.get("entries")
    if not isinstance(entries, list):
        return errs + ["entries は配列"]
    seen: set = set()
    keys: set = set()
    for i, e in enumerate(entries):
        errs += validate_entry(e, i)
        if not isinstance(e, dict):
            continue
        if isinstance(e.get("id"), str):
            if e["id"] in seen:
                errs.append(f"entries[{i}]: id {e['id']!r} が重複")
            seen.add(e["id"])
        key = (e.get("category"), e.get("lang"), e.get("source"))
        if all(isinstance(x, str) for x in key):
            if key in keys:
                errs.append(f"entries[{i}]: (category, lang, source) {key} が重複")
            keys.add(key)
    return errs


def _encoder():
    import tiktoken  # dev 依存。o200k 計測時だけ使う

    return tiktoken.get_encoding("o200k_base")


def measure(path: Path, enc=None) -> dict:
    raw = path.read_bytes()
    texts = []
    for n, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        if not isinstance(rec.get("text"), str) or not rec["text"]:
            raise ValueError(f"{path}:{n}: text がない")
        if rec.get("tier") not in TIERS:
            raise ValueError(f"{path}:{n}: tier は short/medium/long")
        lic = rec.get("license")
        if lic not in ALLOWED_LICENSES:
            raise ValueError(f"{path}:{n}: license {lic!r} は許可リスト外")
        texts.append(rec["text"])
    enc = enc or _encoder()
    return {
        "count": len(texts),
        "bytes": sum(len(t.encode("utf-8")) for t in texts),
        "o200k_tokens": sum(len(enc.encode(t)) for t in texts),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def check(manifest_path: Path = MANIFEST, enc=None) -> list[str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    errs = validate_manifest(m)
    if errs:
        return errs
    base = manifest_path.parent
    listed = {e["path"] for e in m["entries"] if "path" in e}
    for f in sorted(base.rglob("*.jsonl")):
        rel = f.relative_to(base).as_posix()
        if rel not in listed:
            errs.append(f"{rel}: manifest に無い jsonl（孤児）")
    for i, e in enumerate(m["entries"]):
        if "path" not in e:
            continue
        f = base / e["path"]
        if not f.is_file():
            errs.append(f"entries[{i}]: {e['path']} がない")
            continue
        try:
            got = measure(f, enc)
        except ValueError as ex:
            errs.append(f"entries[{i}]: {ex}")
            continue
        for k, v in got.items():
            if e[k] != v:
                errs.append(f"entries[{i}]: {k} が実測と不一致（manifest={e[k]} 実測={v}）")
    return errs


def update(manifest_path: Path = MANIFEST) -> None:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    enc = _encoder()
    for e in m["entries"]:
        if "path" in e:
            e.update(measure(manifest_path.parent / e["path"], enc))
    manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sm = sub.add_parser("measure")
    sm.add_argument("path", type=Path)
    for name in ("check", "update"):
        sub.add_parser(name).add_argument("--manifest", type=Path, default=MANIFEST)
    a = ap.parse_args(argv)
    if a.cmd == "measure":
        print(json.dumps(measure(a.path), ensure_ascii=False))
        return 0
    if a.cmd == "update":
        update(a.manifest)
    errs = check(a.manifest)
    for e in errs:
        print(e, file=sys.stderr)
    print("OK" if not errs else f"NG: {len(errs)} 件")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
