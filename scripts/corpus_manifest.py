#!/usr/bin/env python3
"""多言語テストコーパスの manifest を計測・検証する。

依存: 共有ツールは stdlib のみが原則だが、本スクリプトは o200k トークン数の計測のためだけに
tiktoken（dev 依存）を使う明示的な例外とする（docs/corpus.md 参照）。tiktoken は
measure/update/check で o200k を数えるときにだけ遅延 import し、それ以外は stdlib のみ。

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
MAX_FILE_BYTES = 256 * 1024  # 同梱 1 ファイルの上限
MAX_TOTAL_BYTES = 5 * 1024 * 1024  # corpus/ 全体の上限
RECORD_KEYS = ("id", "text", "lang", "tier", "source", "license", "author", "url")


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
    if "BY" in e["license"]:
        a = e.get("attribution")
        if not isinstance(a, str) or not a.strip():
            errs.append(f"{p}: license {e['license']!r} は BY 系なので attribution（空でない文字列）が必要")
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
    paths: set = set()
    for i, e in enumerate(entries):
        errs += validate_entry(e, i)
        if not isinstance(e, dict):
            continue
        if isinstance(e.get("id"), str):
            if e["id"] in seen:
                errs.append(f"entries[{i}]: id {e['id']!r} が重複")
            seen.add(e["id"])
        src = e.get("source")
        key = (e.get("category"), e.get("lang"), src.casefold() if isinstance(src, str) else src)
        if all(isinstance(x, str) for x in key):
            if key in keys:
                errs.append(f"entries[{i}]: (category, lang, source) {key} が重複")
            keys.add(key)
        if isinstance(e.get("path"), str):
            if e["path"] in paths:
                errs.append(f"entries[{i}]: path {e['path']!r} が重複")
            paths.add(e["path"])
    return errs


def _encoder():
    import tiktoken  # dev 依存。o200k 計測時だけ使う

    return tiktoken.get_encoding("o200k_base")


def validate_records(path: Path, entry: dict | None = None) -> tuple[list[str], list[str]]:
    """JSONL を 1 行ずつ検証し (errs, texts) を返す。entry があれば lang/license の一致も見る。"""
    errs: list[str] = []
    texts: list[str] = []
    ids: set = set()
    seen_text: dict = {}
    for n, line in enumerate(path.read_bytes().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        p = f"{path.name}:{n}"
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as ex:
            errs.append(f"{p}: JSON として読めない（{ex.msg}）")
            continue
        if not isinstance(rec, dict):
            errs.append(f"{p}: レコードが JSON object ではない")
            continue
        bad = [k for k in RECORD_KEYS if not isinstance(rec.get(k), str) or not rec[k]]
        if bad:
            errs.append(f"{p}: {', '.join(bad)} がない（空でない文字列が必要）")
            continue
        if rec["tier"] not in TIERS:
            errs.append(f"{p}: tier は short/medium/long")
        if rec["license"] not in ALLOWED_LICENSES:
            errs.append(f"{p}: license {rec['license']!r} は許可リスト外")
        if entry is not None:
            for k in ("lang", "license"):
                if rec[k] != entry.get(k):
                    errs.append(f"{p}: {k} {rec[k]!r} が manifest（{entry.get(k)!r}）と不一致")
            if rec["source"].casefold() != str(entry.get("source", "")).casefold():
                errs.append(f"{p}: source {rec['source']!r} が manifest（{entry.get('source')!r}）と不一致")
        if rec["id"] in ids:
            errs.append(f"{p}: id {rec['id']!r} がファイル内で重複")
        ids.add(rec["id"])
        if rec["text"] in seen_text:
            errs.append(f"{p}: text が {seen_text[rec['text']]} 行目と重複")
        seen_text.setdefault(rec["text"], n)
        texts.append(rec["text"])
    return errs, texts


def _record_ids(path: Path) -> list[str]:
    """検証済みファイルのレコード id 一覧。"""
    return [json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def measure(path: Path, enc=None, entry: dict | None = None) -> dict:
    errs, texts = validate_records(path, entry)
    if errs:
        raise ValueError("; ".join(errs))
    enc = enc or _encoder()
    return {
        "count": len(texts),
        "bytes": sum(len(t.encode("utf-8")) for t in texts),
        "o200k_tokens": sum(len(enc.encode(t)) for t in texts),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def check_sizes(base: Path, max_file: int | None = None, max_total: int | None = None) -> list[str]:
    max_file = MAX_FILE_BYTES if max_file is None else max_file
    max_total = MAX_TOTAL_BYTES if max_total is None else max_total
    errs: list[str] = []
    total = 0
    for f in sorted(x for x in base.rglob("*") if x.is_file()):
        size = f.stat().st_size
        total += size
        if size > max_file:
            errs.append(f"{f.relative_to(base).as_posix()}: {size} バイトで 1 ファイル上限 {max_file} を超過")
    if total > max_total:
        errs.append(f"corpus 合計 {total} バイトで上限 {max_total} を超過")
    return errs


def check(manifest_path: Path = MANIFEST, enc=None) -> list[str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    errs = validate_manifest(m)
    if errs:
        return errs
    base = manifest_path.parent
    errs += check_sizes(base)
    listed = {e["path"] for e in m["entries"] if "path" in e}
    for f in sorted(base.rglob("*.jsonl")):
        rel = f.relative_to(base).as_posix()
        if rel not in listed:
            errs.append(f"{rel}: manifest に無い jsonl（孤児）")
    id_owner: dict = {}
    for i, e in enumerate(m["entries"]):
        if "path" not in e:
            continue
        f = base / e["path"]
        if not f.is_file():
            errs.append(f"entries[{i}]: {e['path']} がない")
            continue
        try:
            got = measure(f, enc, e)
        except ValueError as ex:
            errs.append(f"entries[{i}]: {ex}")
            continue
        for rid in _record_ids(f):
            other = id_owner.setdefault(rid, e["path"])
            if other != e["path"]:
                errs.append(f"entries[{i}]: {e['path']}: レコード id {rid!r} が {other} と重複（ファイル間）")
        for k, v in got.items():
            if e[k] != v:
                errs.append(f"entries[{i}]: {k} が実測と不一致（manifest={e[k]} 実測={v}）")
    return errs


def update(manifest_path: Path = MANIFEST) -> None:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    enc = _encoder()
    for e in m["entries"]:
        if "path" in e:
            e.update(measure(manifest_path.parent / e["path"], enc, e))
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
