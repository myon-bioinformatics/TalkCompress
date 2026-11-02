"""MorphoZip 日本語の既存崩れ（あれこれ / かれこれ / それにしても / 「えーと」 / 最後に、）と、
#132 の変異テストで生き残った箇所を殺す実値テスト。"""
import pytest

from shared import lex_policy as L
from tests._helpers import load

m = load("morpho_zip", "MorphoZip/morpho_zip.py")


def c(s: str) -> str:
    return m.compress(s, aggressive_fillers=True)


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
