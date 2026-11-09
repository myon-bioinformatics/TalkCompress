"""asr_normalize の o200k トークン数 → バイト数を測る。uv run python scripts/measure_asr_normalize.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import tiktoken
import asr_normalize as a

J = "日本語のテキストです。ありがとうございます。café — “hi” ok"
CASES = [
    ("不確実 [語?]", "I pushed it to [talk compress?] yesterday"),
    ("候補 {a|b}", "I pushed it to {TalkCompress|Talk Compress|talk compressor} yesterday"),
    ("信頼度", "I pushed it to TalkCompress{0.42} yesterday"),
    ("分かち書き", "we use mini match and depend a bot now"),
    ("化け cp1252", J.encode().decode("cp1252", "replace")),
    ("化け latin-1", J.encode().decode("latin-1")),
    ("化け cp932", J.encode().decode("cp932", "replace")),
    ("復元不能", "ok ��� �\x01� end"),
]
WORDS = ["talk compress", "mini match", "depend a bot", "iron mate", "play wright"]


def measure(cases=CASES, words=WORDS):
    """Rows of (name, input, output, in_tokens, in_bytes, out_tokens, out_bytes) plus word and U+FFFD counts."""
    enc = tiktoken.get_encoding("o200k_base")
    t = lambda s: len(enc.encode(s))
    b = lambda s: len(s.encode())
    rows = []
    for name, s in cases:
        o = a.normalize_uncertain(a.clean_mojibake(s), paren=True, alternatives=True, confidence=True)
        if name == "分かち書き":
            o = s.replace("mini match", a.keep_unknown("mini match")).replace("depend a bot", a.keep_unknown("depend a bot"))
        rows.append((name, s, o, t(s), b(s), t(o), b(o)))
    word_rows = [(w, t(" " + w), a.join_word(w), t(" " + a.join_word(w)), w.replace(" ", "").lower(), t(" " + w.replace(" ", "").lower())) for w in words]
    fffd = {n: t("�" * n) for n in (1, 3, 8)}
    return {"rows": rows, "J": (t(J), b(J)), "words": word_rows, "fffd": fffd, "fffd_spaced": t("� � �")}


def main(argv=None):
    m = measure()
    print("| ケース | 入力 tok/B | 出力 tok/B | 出力 |\n|---|---|---|---|")
    for name, s, o, ts, bs, to, bo in m["rows"]:
        print(f"| {name} | {ts}/{bs} | {to}/{bo} | `{o}` |")
    print(f"\n原文 J: {m['J'][0]}/{m['J'][1]}")
    for w, tw, cam, tcam, low, tlow in m["words"]:
        print(f"{w}: 分割 {tw} / join_word {cam} {tcam} / lower {low} {tlow}")
    print("\nU+FFFD 連続:", m["fffd"], "/ 空白まじり 3 個:", m["fffd_spaced"])


if __name__ == "__main__":
    raise SystemExit(main())
