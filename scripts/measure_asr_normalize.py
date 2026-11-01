"""asr_normalize の o200k トークン数 → バイト数を測る。uv run python scripts/measure_asr_normalize.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import tiktoken
import asr_normalize as a

enc = tiktoken.get_encoding("o200k_base")
t = lambda s: len(enc.encode(s))
b = lambda s: len(s.encode())
J = "日本語のテキストです。ありがとうございます。café — “hi” ok"
cases = [
    ("不確実 [語?]", "I pushed it to [talk compress?] yesterday"),
    ("候補 {a|b}", "I pushed it to {TalkCompress|Talk Compress|talk compressor} yesterday"),
    ("信頼度", "I pushed it to TalkCompress{0.42} yesterday"),
    ("分かち書き", "we use mini match and depend a bot now"),
    ("化け cp1252", J.encode().decode("cp1252", "replace")),
    ("化け latin-1", J.encode().decode("latin-1")),
    ("化け cp932", J.encode().decode("cp932", "replace")),
    ("復元不能", "ok \ufffd\ufffd\ufffd \ufffd\x01\ufffd end"),
]
print("| ケース | 入力 tok/B | 出力 tok/B | 出力 |\n|---|---|---|---|")
for name, s in cases:
    o = a.normalize_uncertain(a.clean_mojibake(s), paren=True, alternatives=True)
    if name == "分かち書き":
        o = s.replace("mini match", a.keep_unknown("mini match")).replace("depend a bot", a.keep_unknown("depend a bot"))
    print(f"| {name} | {t(s)}/{b(s)} | {t(o)}/{b(o)} | `{o}` |")
print(f"\n原文 J: {t(J)}/{b(J)}")
for w in ["talk compress", "mini match", "depend a bot", "iron mate", "play wright"]:
    cam = a.join_word(w); low = w.replace(" ", "").lower()
    print(f"{w}: 分割 {t(' '+w)} / join_word {cam} {t(' '+cam)} / lower {low} {t(' '+low)}")
print("\nU+FFFD 連続:", {n: t("\ufffd" * n) for n in (1, 3, 8)}, "/ 空白まじり 3 個:", t("\ufffd \ufffd \ufffd"))
