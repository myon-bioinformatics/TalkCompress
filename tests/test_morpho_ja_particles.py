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


# 実値テスト: 各助詞について「ひらがな直後は不変」「漢字/カタカナ直後は置換」を固定する。
@pytest.mark.parametrize("src", [
    "のに行く", "のへ行く", "そこで", "のは", "のを", "のが", "あとから", "ほどまで",
    "かなと", "なにも",
])
def test_each_particle_after_hiragana_unchanged(src):
    assert m.compress(src) == src


@pytest.mark.parametrize("src,out", [
    ("学校に行く", "学校 to 行く"), ("駅へ行く", "駅 to 行く"), ("家で", "家 in"),
    ("家から", "家←"), ("駅まで", "駅 until"), ("友と", "友&"), ("猫も行く", "猫+行く"),
    ("猫を", "猫"), ("猫が", "猫"), ("猫は", "猫"), ("テストも", "テスト+"),
])
def test_each_particle_after_kanji_katakana_pivots(src, out):
    assert m.compress(src) == out


@pytest.mark.parametrize("src,out", [("猫もとても", "猫+とても"), ("犬もとうとう", "犬+とうとう")])
def test_mo_before_to_word_still_pivots(src, out):
    assert m.compress(src) == out


@pytest.mark.parametrize("src", [
    "猫もともと好き", "データもとに戻す", "法律もとで", "計画もとの形", "本人もとより",
])
def test_moto_words_kept(src):
    assert m.compress(src) == src


@pytest.mark.parametrize("src", ["猫もらう", "猫もう", "猫もし", "猫もの", "猫もっと", "猫もちろん", "猫もどる"])
def test_mo_word_starts_kept(src):
    # 既知の限界: 猫もうれしい のような「も+う…」も置換しない
    assert m.compress(src) == src


@pytest.mark.parametrize("src", ["山もと", "山もと。", "山もと、川沿い", "「山もと」", "山もと 太郎"])
def test_moto_at_end_or_before_punct_kept(src):
    assert m.compress(src) == src
    assert m.compress(src, aggressive_fillers=True) == src


@pytest.mark.parametrize("src,out", [
    ("田中もともに行く", "田中+ともに行く"),  # ともに = 一緒に。「も」+「ともに」
    ("彼もともに", "he+ともに"),
    ("猫もとても", "猫+とても"),
])
def test_tomoni_pivots(src, out):
    assert m.compress(src) == out


@pytest.mark.parametrize("src", ["猫もともと好き", "データもとに戻す", "本人もとより"])
def test_moto_words_still_kept(src):
    assert m.compress(src) == src
