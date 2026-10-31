"""roundtrip.norm: NFD の応答でアクセントが落ちて NFC の原文と不一致にならないこと。"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from roundtrip import norm  # noqa: E402


def test_nfd_reply_matches_nfc_source():
    src = "The café in Hà Nội is naïve."
    assert norm(unicodedata.normalize("NFD", src)) == norm(src) == "the café in hà nội is naïve"
