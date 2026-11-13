"""Build the 60 source paragraphs for the paragraph round-trip benchmark.

Output: ``SentenceCalibratedMosaic/fixtures/paragraph_judge/sources.json``. Each paragraph keeps
its gold sentence list (FLORES gives the boundaries; PD and Latin passages are segmented here and
the result is pinned in the fixture), so scoring never has to guess where the source sentences are.

Sources (licence rules: docs/corpus.md):

* FLORES-200 devtest (CC BY-SA 4.0), ``flores200_dataset.tar.gz`` pinned by sha256 (same pin as
  scripts/fetch_corpus_major.py). One article = one paragraph (all its devtest sentences, 4-6 of
  them). The same articles are used for every FLORES language, so the languages are parallel.
  en: 6 wikinews articles; de es fr pt ja zh it nl el cs pl: the first 4 of those 6.
* English narrative / dialogue (Public domain, US): the 6 passages listed in ``PD_EN`` from
  ``tests/fixtures/pd_corpus/`` (already committed and attributed in its SOURCES.md).
* Latin (Public domain, US): FLORES-200 has no Latin, so 4 paragraphs of Caesar, De Bello Gallico I
  (Project Gutenberg #218, plain-text UTF-8 file pinned by sha256; Gutenberg header/footer removed).

Article choice is deterministic: wikinews articles with 4-6 devtest sentences, shuffled with
``random.Random(SELECT_SEED)``, first 6 taken. Network and the cache are only needed to rebuild:

    uv run python scripts/build_paragraph_sources.py          # write sources.json
    uv run python scripts/build_paragraph_sources.py --check  # rebuild and compare

Files go to ``.cache/corpus/<sha256>`` (git-ignored); a sha256 mismatch is never saved.
"""
from __future__ import annotations

import argparse, hashlib, io, json, random, re, sys, tarfile, unicodedata, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SentenceCalibratedMosaic/fixtures/paragraph_judge/sources.json"
CACHE = ROOT / ".cache/corpus"

FLORES_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
FLORES_SHA256 = "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6"
FLORES_LICENSE = "CC BY-SA 4.0"
FLORES_SOURCE = "FLORES-200 (devtest)"
FLORES_AUTHOR = "FLORES-200 (NLLB Team, Meta AI)"
FLORES = {"en": "eng_Latn", "de": "deu_Latn", "es": "spa_Latn", "fr": "fra_Latn", "pt": "por_Latn",
          "ja": "jpn_Jpan", "zh": "zho_Hans", "it": "ita_Latn", "nl": "nld_Latn", "el": "ell_Grek",
          "cs": "ces_Latn", "pl": "pol_Latn"}
SELECT_SEED = "paragraph-roundtrip-20261113"
EN_FLORES = 6
OTHER_FLORES = 4

LA_URL = "https://www.gutenberg.org/cache/epub/218/pg218.txt"
LA_SHA256 = "84ac8411841a4d8f5f4a49b6a2cd1f466917c6a5af72916d5e0b2b1ecb2f659c"
LA_EBOOK = "https://www.gutenberg.org/ebooks/218"
# Gutenberg paragraph indices (blank-line split of the body). Chosen because each is 3-4 plain
# narrative sentences with past-tense verbs and no editorial [brackets]: 14 Orgetorix's trial and
# death, 19 the embassy to Dumnorix, 26 the cavalry skirmish, 27 the march after it.
LA_PARAS = (14, 19, 26, 27)

# (file stem, first sentence index, sentence count). The PD splitter below is a plain regex, so
# sentences that it cuts after "Mr." / "Mrs." are rejoined; the result is pinned in sources.json.
PD_EN = (
    ("aesop-tortoise-hare", 0, 6),   # dialogue, quotation spans two sentences
    ("austen-pp-01", 0, 5),          # narration + dialogue, reported speech ("he had not")
    ("twain-huck-01", 0, 5),         # first-person colloquial past ("I never seen")
    ("grimm-hansel-01", 0, 5),       # narrative past + direct question
    ("kipling-jungle-01", 0, 5),     # narrative past + short exclamations
    ("bronte-jane-01", 0, 3),        # first-person past perfect ("had been wandering")
)
PD_LICENSE = "Public domain"
LANG_JOIN = {"ja": "", "zh": ""}


def fetch(url: str, sha256: str) -> bytes:
    path = CACHE / sha256
    data = path.read_bytes() if path.is_file() else urllib.request.urlopen(url, timeout=300).read()  # noqa: S310 pinned https
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise SystemExit(f"sha256 mismatch for {url}: expected {sha256}, got {got}")
    if not path.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def join(lang: str, sentences: list[str]) -> str:
    return LANG_JOIN.get(lang, " ").join(sentences)


_ABBR_END = re.compile(r"(?:^|[\s\"“(])(?:Mr|Mrs|Ms|Dr|St)\.$|(?:^|\s)(?:[A-Z]|Cn|Sex|Ti|Ser|Sp|Ap)\.$")


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[“\"‘A-Z])|(?<=[.!?][”\"’])\s+(?=[“\"‘A-Z])", text)
    out: list[str] = []
    for p in parts:
        if out and _ABBR_END.search(out[-1]):
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def flores_paragraphs() -> list[dict]:
    with tarfile.open(fileobj=io.BytesIO(fetch(FLORES_URL, FLORES_SHA256)), mode="r:gz") as tar:
        def read(name: str) -> list[str]:
            f = tar.extractfile("./flores200_dataset/" + name)
            assert f is not None
            return f.read().decode("utf-8").splitlines()
        meta = [r.split("\t") for r in read("metadata_devtest.tsv")[1:]]
        texts = {lang: read(f"devtest/{code}.devtest") for lang, code in FLORES.items()}
    arts: dict[str, list[int]] = {}
    for i, row in enumerate(meta):
        arts.setdefault(row[0], []).append(i)
    cands = [u for u, idx in arts.items() if meta[idx[0]][1] == "wikinews" and 4 <= len(idx) <= 6]
    random.Random(SELECT_SEED).shuffle(cands)
    chosen = cands[:EN_FLORES]
    out = []
    for lang in FLORES:
        n = EN_FLORES if lang == "en" else OTHER_FLORES
        for k, url in enumerate(chosen[:n], 1):
            sents = [unicodedata.normalize("NFC", texts[lang][i]).strip() for i in arts[url]]
            out.append({"id": f"{lang}-flores-{k:02d}", "lang": lang, "group": "flores-wikinews",
                        "sentences": sents, "text": join(lang, sents), "source": FLORES_SOURCE,
                        "license": FLORES_LICENSE, "author": FLORES_AUTHOR, "url": url,
                        "upstream": {"url": FLORES_URL, "sha256": FLORES_SHA256,
                                     "devtest_lines": [i + 1 for i in arts[url]]}})
    return out


def pd_paragraphs() -> list[dict]:
    manifest = {e["id"]: e for e in json.loads((ROOT / "tests/fixtures/pd_corpus/manifest.json").read_text(encoding="utf-8"))["passages"]}
    out = []
    for k, (stem, start, n) in enumerate(PD_EN, 1):
        e = manifest[stem]
        raw = (ROOT / "tests/fixtures/pd_corpus" / e["file"]).read_text(encoding="utf-8")
        sents = split_sentences(" ".join(unicodedata.normalize("NFC", raw).split()))[start:start + n]
        assert len(sents) == n, stem
        out.append({"id": f"en-pd-{k:02d}", "lang": "en", "group": "pd-narrative",
                    "sentences": sents, "text": join("en", sents), "source": f"{e['title']} ({stem})",
                    "license": PD_LICENSE, "author": e["author"], "url": e["source_url"],
                    "upstream": {"path": f"tests/fixtures/pd_corpus/{e['file']}",
                                 "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}})
    return out


def la_paragraphs() -> list[dict]:
    body = fetch(LA_URL, LA_SHA256).decode("utf-8").replace("\r\n", "\n")
    body = body.split("*** START OF", 1)[1].split("\n", 1)[1].split("*** END OF", 1)[0]
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body)]
    out = []
    for k, idx in enumerate(LA_PARAS, 1):
        sents = split_sentences(unicodedata.normalize("NFC", paras[idx]))
        assert 3 <= len(sents) <= 6, idx
        out.append({"id": f"la-caesar-{k:02d}", "lang": "la", "group": "pd-caesar-bg1",
                    "sentences": sents, "text": join("la", sents),
                    "source": "C. Iuli Caesaris De Bello Gallico, I-IV (Project Gutenberg #218)",
                    "license": PD_LICENSE, "author": "Gaius Julius Caesar", "url": LA_EBOOK,
                    "upstream": {"url": LA_URL, "sha256": LA_SHA256, "paragraph_index": idx}})
    return out


def build() -> dict:
    paras = flores_paragraphs()
    en = [p for p in paras if p["lang"] == "en"] + pd_paragraphs()
    rest = [p for p in paras if p["lang"] != "en"] + la_paragraphs()
    return {"schema_version": 1, "select_seed": SELECT_SEED,
            "licence_note": "FLORES-derived records are CC BY-SA 4.0 (NLLB Team, Meta AI; "
                            "https://creativecommons.org/licenses/by-sa/4.0/); en-pd-* and la-* are public domain. "
                            "Files under paragraph_judge/ that contain FLORES text (including compressed or "
                            "restored versions, which are modified) are distributed under CC BY-SA 4.0.",
            "paragraphs": en + rest}


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    text = dumps(build())
    if a.check:
        ok = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("sources.json up to date" if ok else "sources.json is stale")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
