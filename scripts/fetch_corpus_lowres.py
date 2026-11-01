#!/usr/bin/env python3
"""Fetch the multilingual test corpus for ko/vi/th/id/tr/he/fa/sw/bn/ta.

Single file, stdlib only.  Every upstream archive is pinned by sha256 and the
script refuses to continue when a download does not match.

Buckets (``<category>``):
  short  -- Tatoeba sentences (OPUS-Tatoeba v2023-04-12 mono, CC BY 2.0 FR)
  medium -- FLORES-200 dev+devtest single sentences (CC BY-SA 4.0)
  long   -- FLORES-200 sentences joined per source article (CC BY-SA 4.0)

Usage:
  python scripts/fetch_corpus_lowres.py                 # full set -> build/corpus/
  python scripts/fetch_corpus_lowres.py --sample 20 --out tests/fixtures/corpus
  uv run python scripts/fetch_corpus_lowres.py --tokens  # add o200k counts (tiktoken)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

LANGS = ("ko", "vi", "th", "id", "tr", "he", "fa", "sw", "bn", "ta")
CATEGORIES = ("short", "medium", "long")

TATOEBA_URL = "https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/{code}.txt.gz"
TATOEBA_LICENSE = "CC-BY-2.0-FR"
TATOEBA_SOURCE = "Tatoeba (OPUS-Tatoeba v2023-04-12 mono)"
# ISO 639-1 -> OPUS file code, sha256 of the .txt.gz
TATOEBA = {
    "ko": ("ko", "72e21497f261ba7d174dfa4f191410e95fb3ec0b9f219c643672eace6df5f310"),
    "vi": ("vi", "3c4188d7d83870d9b684ed7d67c2c4381a2332e52021b05f3c11915f58e1f590"),
    "th": ("th", "874e4df516f2b14f6614b5aabff197778b0838f93ac5733d35b49565bdb2b174"),
    "id": ("id", "3e4f08eb043e95648cbe56d595a0ead3a4f351eb1414262bb0ccd07b073aca83"),
    "tr": ("tr", "61b2b4bb62f442f4af13111b1a897e6cd14bf20c713bf0692adfe5ea92ed96a2"),
    "he": ("he", "1934d66e4450358cad385ecb5a0583113120b14cd89e97348875dd7aa5713083"),
    "fa": ("pes", "f0159d67e05802efde95ffe3c4f1ec6c8b7fe6816dab2fc9a3a589d92561f052"),
    "sw": ("swh", "a922ba70a73015b68c5f2447f609040ea8b7492e05bc6e0337391b580ec87bda"),
    "bn": ("bn", "816f6d8d4d8f55304135385f0a23bf3494ee6972e80e34f76712bd236be60c95"),
    "ta": ("ta", "9bea4291a732f89c1cb0c4269da590d4c5764ec7dd36f20583042c953b94cb5d"),
}

FLORES_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
FLORES_SHA256 = "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6"
FLORES_LICENSE = "CC-BY-SA-4.0"
FLORES_SOURCE = "FLORES-200 (dev+devtest)"
FLORES = {
    "ko": "kor_Hang", "vi": "vie_Latn", "th": "tha_Thai", "id": "ind_Latn",
    "tr": "tur_Latn", "he": "heb_Hebr", "fa": "pes_Arab", "sw": "swh_Latn",
    "bn": "ben_Beng", "ta": "tam_Taml",
}

SHORT_MAX_CHARS = 60
SHORT_LIMIT = 500
MEDIUM_LIMIT = 500


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, sha256: str, cache: Path) -> bytes:
    path = cache / sha256
    if path.is_file():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 (pinned https)
            data = resp.read()
    got = _sha256(data)
    if got != sha256:
        raise SystemExit(f"sha256 mismatch for {url}: expected {sha256}, got {got}")
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def build_short(lang: str, cache: Path) -> list[dict]:
    code, sha = TATOEBA[lang]
    raw = gzip.decompress(fetch(TATOEBA_URL.format(code=code), sha, cache))
    seen: set[str] = set()
    out: list[dict] = []
    for line in raw.decode("utf-8").splitlines():
        text = line.strip()
        if not text or len(text) > SHORT_MAX_CHARS or text in seen:
            continue
        seen.add(text)
        out.append({"text": text, "source": TATOEBA_SOURCE, "license": TATOEBA_LICENSE})
        if len(out) >= SHORT_LIMIT:
            break
    return out


def _flores_members(cache: Path) -> dict[str, bytes]:
    data = fetch(FLORES_URL, FLORES_SHA256, cache)
    members: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            if m.isfile():
                f = tar.extractfile(m)
                if f is not None:
                    members[m.name.removeprefix("./")] = f.read()
    return members


def build_flores(lang: str, members: dict[str, bytes]) -> tuple[list[dict], list[dict]]:
    code = FLORES[lang]
    medium: list[dict] = []
    long: list[dict] = []
    for split in ("dev", "devtest"):
        sents = members[f"flores200_dataset/{split}/{code}.{split}"].decode("utf-8").splitlines()
        meta = members[f"flores200_dataset/metadata_{split}.tsv"].decode("utf-8").splitlines()[1:]
        urls = [row.split("\t", 1)[0] for row in meta]
        if len(urls) != len(sents):
            raise SystemExit(f"FLORES {split}/{code}: {len(sents)} sentences vs {len(urls)} metadata rows")
        doc: list[str] = []
        for i, (url, sent) in enumerate(zip(urls, sents)):
            medium.append({"text": sent.strip(), "source": f"{FLORES_SOURCE} {split}#{i}",
                           "license": FLORES_LICENSE})
            doc.append(sent.strip())
            if i + 1 == len(urls) or urls[i + 1] != url:
                long.append({"text": " ".join(doc), "source": f"{FLORES_SOURCE} {split} {url}",
                             "license": FLORES_LICENSE})
                doc = []
    return medium[:MEDIUM_LIMIT], long


def build_all(cache: Path) -> dict[tuple[str, str], list[dict]]:
    members = _flores_members(cache)
    result: dict[tuple[str, str], list[dict]] = {}
    for lang in LANGS:
        medium, long = build_flores(lang, members)
        result[("short", lang)] = build_short(lang, cache)
        result[("medium", lang)] = medium
        result[("long", lang)] = long
    for (cat, lang), rows in result.items():
        for n, row in enumerate(rows):
            row.update({"id": f"{cat}-{lang}-{n:04d}", "lang": lang, "category": cat})
    return result


def to_jsonl(rows: list[dict]) -> bytes:
    keys = ("id", "lang", "category", "text", "source", "license")
    return "".join(json.dumps({k: r[k] for k in keys}, ensure_ascii=False) + "\n"
                   for r in rows).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("build/corpus"))
    ap.add_argument("--cache", type=Path, default=Path("build/corpus-cache"))
    ap.add_argument("--sample", type=int, default=0, help="keep only the first N rows per file")
    ap.add_argument("--tokens", action="store_true", help="count o200k_base tokens (needs tiktoken)")
    ap.add_argument("--manifest", type=Path, help="write/merge entries into this manifest.json")
    args = ap.parse_args(argv)

    enc = None
    if args.tokens:
        import tiktoken  # dev dependency; not needed for fetching

        enc = tiktoken.get_encoding("o200k_base")

    entries = []
    for (cat, lang), rows in sorted(build_all(args.cache).items()):
        full_bytes = sum(len(r["text"].encode("utf-8")) for r in rows)
        full_tokens = sum(len(enc.encode(r["text"])) for r in rows) if enc else None
        kept = rows[: args.sample] if args.sample else rows
        blob = to_jsonl(kept)
        path = args.out / cat / f"{lang}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        entry = {
            "path": f"{cat}/{lang}.jsonl", "lang": lang, "category": cat,
            "source": kept[0]["source"].split(" dev")[0] if kept else "",
            "license": kept[0]["license"] if kept else "",
            "count": len(kept), "sha256": _sha256(blob),
            "text_bytes": sum(len(r["text"].encode("utf-8")) for r in kept),
            "o200k_tokens": sum(len(enc.encode(r["text"])) for r in kept) if enc else None,
            "full_count": len(rows), "full_text_bytes": full_bytes, "full_o200k_tokens": full_tokens,
            "fetch": "scripts/fetch_corpus_lowres.py",
        }
        entries.append(entry)
        print(f"{cat:6} {lang} rows={len(rows)} bytes={full_bytes} o200k={full_tokens}")

    if args.manifest:
        doc = {"schema": 1, "entries": []}
        if args.manifest.is_file():
            doc = json.loads(args.manifest.read_text(encoding="utf-8"))
        mine = {e["path"] for e in entries}
        doc["entries"] = sorted([e for e in doc.get("entries", []) if e.get("path") not in mine] + entries,
                                key=lambda e: e["path"])
        args.manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
