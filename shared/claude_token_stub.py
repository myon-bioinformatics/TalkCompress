"""Claude token counting stub (G6): one interface, three backends, no network.

Claude's own tokenizer is not published, so nothing here reproduces it. This
module only lets the rest of TalkCompress ask "how many tokens for this model",
with the source of the answer named:

- ``estimate``: the stdlib estimator in TesseraTalk (calibrated toward o200k_base).
  A proxy, not a Claude count.
- ``scaled``: the estimate multiplied by a factor for models that use the newer
  tokenizer. The factor comes from Anthropic's documentation ("approximately 30
  percent more tokens" for Claude 4.7 and later, and Mythos). It is a rough
  rule, not a per-text count.
- ``fixture``: exact counts recorded by hand from internal runs, stored as JSON
  keyed by the SHA-256 of the text and the model. Unknown texts fall back to
  ``scaled``/``estimate``, and the result says so.

Which backend answers is always reported with the count, so a number is never
presented as more exact than it is.

Stdlib only. Nothing here calls the count_tokens endpoint or needs a key.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_TOKENIZER_FACTOR = 1.3  # docs: "approximately 30 percent more" on 4.7+ and Mythos

_MODEL_RE = re.compile(r"^claude-(?:(?P<family>[a-z]+)-)?(?P<major>\d+)(?:-(?P<minor>\d+))?", re.IGNORECASE)


@dataclass(frozen=True)
class Count:
    tokens: int
    source: str  # "estimate" | "scaled" | "fixture"
    model: str


def uses_new_tokenizer(model: str) -> bool:
    """True for Claude 4.7 and later, and for Mythos-class models.

    The docs name 4.7+ and Mythos. Other families (for example fable) are
    treated by version number, which is an assumption, not a documented fact.
    """
    lowered = model.lower()
    if "mythos" in lowered:
        return True
    m = _MODEL_RE.match(lowered)
    if not m:
        return False
    major = int(m.group("major"))
    minor = int(m.group("minor") or 0)
    return (major, minor) >= (4, 7)


def _estimate(text: str) -> int:
    tessera = ROOT / "TesseraTalk"
    if str(tessera) not in sys.path:
        sys.path.insert(0, str(tessera))
    from tessera_talk import estimate_tokens

    return estimate_tokens(text)


def text_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def load_fixture(path: Path | None) -> dict[str, int]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get("counts", {}).items()}


def count(text: str, model: str, fixture: dict[str, int] | None = None) -> Count:
    """Return a token count for ``text`` under ``model`` with its source named."""
    if fixture:
        key = text_key(text, model)
        if key in fixture:
            return Count(tokens=fixture[key], source="fixture", model=model)
    base = _estimate(text)
    if uses_new_tokenizer(model):
        return Count(tokens=round(base * NEW_TOKENIZER_FACTOR), source="scaled", model=model)
    return Count(tokens=base, source="estimate", model=model)
