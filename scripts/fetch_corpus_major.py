#!/usr/bin/env python3
"""主要10言語（en/zh/es/hi/ar/pt/fr/ru/ja/de）のテストコーパスを取得する（stdlib のみ）。

取得元はすべて sha256 で固定し、一致しなければ止まる。
  tatoeba/<lang>.jsonl   tier=short   Tatoeba（OPUS-Tatoeba v2023-04-12 mono、CC BY 2.0 FR）
  flores200/<lang>.jsonl tier=medium  FLORES-200 dev+devtest の1文（CC BY-SA 4.0）
                         tier=long    同じ元記事の文を連結したもの（CC BY-SA 4.0）

  python scripts/fetch_corpus_major.py                     # 全件 -> .cache/corpus/major/
  python scripts/fetch_corpus_major.py --sample 20 --out tests/fixtures/corpus
同梱サンプル（tier ごと先頭 20 件）の数値は scripts/corpus_manifest.py update で埋める。
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

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("en", "zh", "es", "hi", "ar", "pt", "fr", "ru", "ja", "de")

TATOEBA_URL = "https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/{code}.txt.gz"
# ISO 639-1 -> (OPUS ファイル名, .txt.gz の sha256)
TATOEBA = {
    "en": ("en", "a32c5500cd76b9479859764fb78537a4b9b53fab8fa3bdc0fc04dd70f28bf29b"),
    "zh": ("cmn", "7d8c04289d38802096685c567d81d7aba4f22c704a9483f475eff87997a5e8dc"),
    "es": ("es", "755ee3bdccfb8465ba8250a6626ee7b32faeb2d1f62eb7f185c34ba118073aa0"),
    "hi": ("hi", "6de9ff2cca108d04a41d9a3e09f1afebd4f8ada29a9c7178f05eb57ad7dd96c3"),
    "ar": ("ar", "7060d6d2b0b2313e9a9e4449ad976203f741e7729ab20a702051ed6d0ff6ed5d"),
    "pt": ("pt", "d47a3c64769a29cad793d98cf035974b5b13230657e151ef8151109d54be4bf1"),
    "fr": ("fr", "79a452df4bb738269822dad847ea5db44b8eb5d362d8d9ef7b66305f38098b5d"),
    "ru": ("ru", "c4128c01ad0746fd83699545f166c3645afa4593233a6335f7dbb5d296579c79"),
    "ja": ("ja", "61ef5f80aa418354c3b879088cc51d90c20970c921404bce7b17531b0059a4c9"),
    "de": ("de", "9a0c846db1a9847a6ded516ff107f0da09fb30dd4dda33c8dcfd6ec9fccc35d4"),
}
FLORES_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
FLORES_SHA256 = "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6"
FLORES = {
    "en": "eng_Latn", "zh": "zho_Hans", "es": "spa_Latn", "hi": "hin_Deva",
    "ar": "arb_Arab", "pt": "por_Latn", "fr": "fra_Latn", "ru": "rus_Cyrl",
    "ja": "jpn_Jpan", "de": "deu_Latn",
}
SHORT_MAX_CHARS = 60
SHORT_LIMIT = 500
MEDIUM_LIMIT = 500


def fetch(url: str, sha256: str, cache: Path) -> bytes:
    path = cache / sha256
    if path.is_file():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=300) as r:  # noqa: S310 固定 https
            data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise SystemExit(f"sha256 不一致 {url}: 期待 {sha256} 実際 {got}")
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def build_short(lang: str, cache: Path) -> list[dict]:
    code, sha = TATOEBA[lang]
    seen: set[str] = set()
    out: list[dict] = []
    for line in gzip.decompress(fetch(TATOEBA_URL.format(code=code), sha, cache)).decode("utf-8").splitlines():
        t = line.strip()
        if not t or len(t) > SHORT_MAX_CHARS or t in seen:
            continue
        seen.add(t)
        out.append({"id": f"tatoeba-{lang}-{len(out):04d}", "text": t, "lang": lang, "tier": "short",
                    "source": "Tatoeba (OPUS-Tatoeba v2023-04-12 mono)", "license": "CC BY 2.0 FR",
                    "author": "Tatoeba contributors", "url": "https://opus.nlpl.eu/Tatoeba/"})
        if len(out) >= SHORT_LIMIT:
            break
    return out


def flores_members(cache: Path) -> dict[str, bytes]:
    data = fetch(FLORES_URL, FLORES_SHA256, cache)
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            f = tar.extractfile(m) if m.isfile() else None
            if f is not None:
                out[m.name.removeprefix("./")] = f.read()
    return out


def build_flores(lang: str, members: dict[str, bytes]) -> tuple[list[dict], list[dict]]:
    code = FLORES[lang]
    base = {"lang": lang, "source": "FLORES-200 (dev+devtest)", "license": "CC BY-SA 4.0",
            "author": "FLORES-200 (NLLB Team, Meta AI)"}
    medium: list[dict] = []
    long: list[dict] = []
    for split in ("dev", "devtest"):
        sents = members[f"flores200_dataset/{split}/{code}.{split}"].decode("utf-8").splitlines()
        urls = [r.split("\t", 1)[0] for r in
                members[f"flores200_dataset/metadata_{split}.tsv"].decode("utf-8").splitlines()[1:]]
        if len(urls) != len(sents):
            raise SystemExit(f"FLORES {split}/{code}: 文 {len(sents)} 件とメタデータ {len(urls)} 行が不一致")
        doc: list[str] = []
        for i, (url, s) in enumerate(zip(urls, sents)):
            medium.append({**base, "tier": "medium", "text": s.strip(), "url": url})
            doc.append(s.strip())
            if i + 1 == len(urls) or urls[i + 1] != url:
                long.append({**base, "tier": "long", "text": " ".join(doc), "url": url})
                doc = []
    medium = medium[:MEDIUM_LIMIT]
    for n, r in enumerate(medium):
        r["id"] = f"flores200-{lang}-m{n:04d}"
    for n, r in enumerate(long):
        r["id"] = f"flores200-{lang}-l{n:04d}"
    return medium, long


KEYS = ("id", "text", "lang", "tier", "source", "license", "author", "url")


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({k: r[k] for k in KEYS}, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / ".cache" / "corpus" / "major")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "corpus" / "downloads")
    ap.add_argument("--sample", type=int, default=0, help="tier ごと先頭 N 件だけ書く（0 で全件）")
    a = ap.parse_args(argv)
    members = flores_members(a.cache)
    cut = (lambda rows: rows[: a.sample]) if a.sample else (lambda rows: rows)
    for lang in LANGS:
        short = build_short(lang, a.cache)
        medium, long = build_flores(lang, members)
        write(a.out / "tatoeba" / f"{lang}.jsonl", cut(short))
        write(a.out / "flores200" / f"{lang}.jsonl", cut(medium) + cut(long))
        print(f"{lang}: short={len(short)} medium={len(medium)} long={len(long)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
