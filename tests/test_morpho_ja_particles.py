"""JA 助詞ピボットが語の中（ひらがな直後）を壊さないこと。"""
import pytest

from tests._helpers import load

m = load("morpho_zip", "MorphoZip/morpho_zip.py")


@pytest.mark.parametrize("word", [
    "ちょっと", "あと", "まとめて", "なので", "かなと", "もらえれば", "意見をもらえれば",
    "思っています。", "行きました。", "もっと", "もちろん",
])
def test_hiragana_internal_particles_kept(word):
    out = m.compress(word, aggressive_fillers=True)
    assert "&" not in out and "+" not in out and " in " not in out and " to " not in out
    if word.endswith("。"):
        assert out == word


def test_noun_particles_still_pivot():
    assert m.compress("猫は魚を食べる。学校に行く。") == "猫魚食べる。学校 to 行く。"
    assert m.compress("猫も行く") == "猫+行く"


def test_ja_sample_does_not_grow():
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    s = ("えーと、正直ちょっと怪しいかなと思っています。あと、全部まとめて出すか、"
         "意見をもらえれば、今日中に決めましょう。")
    out = m.compress(s, aggressive_fillers=True)
    assert len(enc.encode(out)) <= len(enc.encode(s))
    for w in ("ちょっと", "かなと", "まとめて", "もらえれば", "思っています"):
        assert w in out
