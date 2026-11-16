"""MorphoGrammarMinimal (E): 日本語の崩れ回帰と助詞ピボット。

- morpho_ja_breakages: MorphoGrammarMinimal の既存の日本語崩れ（それから→esoから / してから→しら / えーと削除後の「。、」）。
- morpho_ja_followup: MorphoGrammarMinimal 日本語の既存崩れ（あれこれ / かれこれ / それにしても / 「えーと」 / 最後に、）と、
- morpho_ja_particles: JA 助詞ピボットが語の中（ひらがな直後）を壊さないこと。
"""

from shared import lex_policy as L
from tests._helpers import load

import pytest


# ──── morpho_ja_breakages ─────────────────────────────────────────

"""MorphoGrammarMinimal の既存の日本語崩れ（それから→esoから / してから→しら / えーと削除後の「。、」）。"""


m = load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")


def c(s: str) -> str:
    return m.compress(s, aggressive_fillers=True)


@pytest.mark.parametrize("src", [
    "それから、行く", "それぞれ違う", "これから始める", "それでは始めます",
    "それでも行く", "これまでの話", "それなりに良い", "それほど高くない", "おそれがある",
    "では、始めます",
])
def test_deixis_heads_of_conjunctions_kept(src):
    assert c(src) == src


@pytest.mark.parametrize("src,out", [
    ("それは猫", "eso猫"), ("それを見て", "eso見て"), ("これが答え", "ça答え"), ("それ無理", "eso無理"),
    ("東京では雨", "東京 in 雨"),
])
def test_deixis_pronoun_still_compressed(src, out):
    assert c(src) == out


@pytest.mark.parametrize("src", [
    "確認してから報告します", "してから", "あの人は来た", "まあまあです", "なんかいも",
])
def test_fillers_not_stripped_inside_words(src):
    out = c(src)
    assert "しら" not in out and out.replace("は", "").startswith(src.replace("は", "")[:2])


@pytest.mark.parametrize("src,out", [
    ("えーと、ちょっと", "ちょっと"),
    ("今日は、えーと、雨。", "今日、雨。"),
    ("テストです。えーと、次。", "テスト。次。"),
    ("えーと今日は雨", "今日雨"),
    ("まあ、いいか", "いいか"),
    ("てか、無理", "無理"),
    ("そうですよね", "そう"),
])
def test_filler_removal_leaves_no_stray_comma(src, out):
    r = c(src)
    assert r == out
    assert "。、" not in r and "、、" not in r and not r.startswith("、")


def test_ja_sample_324():
    from pathlib import Path
    text = (Path(__file__).parent / "fixtures/ja_colloquial_324.txt").read_text().strip()
    out = c(text)
    for bad in ("esoから", "しら", "。、", "、、"):
        assert bad not in out
    assert "それから" in out and "してから" in out


# ──── morpho_ja_followup ──────────────────────────────────────────

"""MorphoGrammarMinimal 日本語の既存崩れ（あれこれ / かれこれ / それにしても / 「えーと」 / 最後に、）と、
#132 の変異テストで生き残った箇所を殺す実値テスト。"""


@pytest.mark.parametrize("src", [
    "あれこれ考える", "かれこれ一年", "それにしても暑い", "それにしろ無理", "「えーと」と言った",
    "最後に、よろしく", "特に、問題ない", "これに、する", "これで、終わり", "それとも行く？",
    "書かれた本", "すごーいと言う",
])
def test_kept_as_is(src):
    assert c(src) == src


@pytest.mark.parametrize("src,out", [
    ("東京に行く", "東京 to 行く"), ("かれは来た", "he来た"), ("コーヒーと紅茶", "コーヒー&紅茶"),
    ("ゲームも好き", "ゲーム+好き"), ("それは猫", "eso猫"), ("これが答え", "ça答え"),
])
def test_still_compressed(src, out):
    assert c(src) == out


def test_deixis_surface_re_guard():
    # インベントリ用の正規表現も置換ルールと同じガードを使う
    found = m._DEIXIS_SURFACE_RE.findall("それから それぞれ あれこれ それにしても それとも それは これ")
    assert found == ["それは", "これ"]


@pytest.mark.parametrize("src,out", [
    ("してから", "してから"),            # てか の左境界
    ("あの人は来た", "あの人は来た"),      # あの の左右境界
    ("それ、なんか", "それ"),
    ("雨、えーと。", "雨。"),             # 、 が 。 の直前に残らない
    ("うーん、、雨", "雨"),
    ("、えーと、雨", "雨"),               # 文頭の 、 を消す
    ("テスト。、えーと次", "テスト。次"),  # 。 の直後の 、 を消す
    ("ok、えーと、", "ok"),
])
def test_strip_fillers_exact(src, out):
    assert L.strip_fillers(src) == out


# ──── morpho_ja_particles ─────────────────────────────────────────

"""JA 助詞ピボットが語の中（ひらがな直後）を壊さないこと。"""


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
