"""MorphoZip の既存の日本語崩れ（それから→esoから / してから→しら / えーと削除後の「。、」）。"""
import pytest

from tests._helpers import load

m = load("morpho_zip", "MorphoZip/morpho_zip.py")


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
