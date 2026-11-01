"""ASR / 口語入力の「不明語」と文字化けを、o200k で安く残すための正規化（stdlib のみ）。

規則（docs/asr_unknown_mojibake.md に実測あり）:
1. 発音が似ている語・未知語は元のつづり（不明ならローマ字）で 1 語につなげて残す。括弧で包まない。
2. 不確実な語だけ ``<?語?>`` で包む。``[語?]`` ``(語?)`` ``{a|b}`` などの ASR 表記はこの形にそろえる。
3. 文字化けはまず復元を試み（UTF-8 を cp1252/latin-1 や cp932 で読んだもの）、
   復元できない連続は U+FFFD 1 文字にまとめる。
"""
from __future__ import annotations

import re
from itertools import product
import unicodedata

UNCERTAIN_OPEN = "<?"
UNCERTAIN_CLOSE = "?>"
FFFD = "\ufffd"


# ---------------------------------------------------------------- unknown words
def join_word(phrase: str) -> str:
    """'Talk Compress' -> 'TalkCompress'、'play wright' -> 'playwright'。

    大文字小文字は各部分のまま連結する（CamelCase 化より o200k で同数か少ない: 実測は docs）。
    """
    parts = [p for p in re.split(r"[\s\-_・·]+", phrase.strip()) if p]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return "".join(parts)


def keep_unknown(phrase: str, uncertain: bool = False) -> str:
    """未知語を 1 語に。不確実なときだけ ``<?…?>``。"""
    w = join_word(phrase)
    if not w:
        return w
    return f"{UNCERTAIN_OPEN}{w}{UNCERTAIN_CLOSE}" if uncertain else w


_ALT = re.compile(r"\{([^{}|]+)(?:\|[^{}]*)\}")  # {a|b|c} -> 先頭候補
_Q_BRACKET = re.compile(r"[\[(（［]\s*([^\[\]()（）［］?？]+?)\s*[?？]\s*[\])）］]")  # [語?] (語?)
_CONF = re.compile(r"(\S+?)\{0?\.\d+\}")  # 語{0.42}
_EXISTING = re.compile(r"<\?\s*([^<>?]+?)\s*\?>")


def normalize_uncertain(text: str, conf_threshold: float = 0.6) -> str:
    """ASR の不確実表記を ``<?語?>`` に統一する（語内の空白は 1 語につなぐ）。"""
    text = _EXISTING.sub(lambda m: keep_unknown(m.group(1), True), text)
    text = _ALT.sub(lambda m: keep_unknown(m.group(1), True), text)
    text = _Q_BRACKET.sub(lambda m: keep_unknown(m.group(1), True), text)

    def conf(m: re.Match) -> str:
        val = float(m.group(0)[m.group(0).index("{") + 1 : -1])
        return keep_unknown(m.group(1), True) if val < conf_threshold else m.group(1)

    return re.sub(r"(\S+?)\{(0?\.\d+|1(?:\.0+)?)\}", conf, text)


# ---------------------------------------------------------------- mojibake
# UTF-8 を 1 バイト系で読んだときに出やすい文字（Ã Â â€ ã‚ など）
_LATIN_MOJI = re.compile(r"(?:[\u00c2-\u00f4][\u0080-\u00bf\ufffd\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u203a\u20ac\u2122]+)+")
_SUSPECT = re.compile(r"[\u00c2-\u00f4][\u0080-\u00bf\u0152-\u2122]")


def _badness(s: str) -> int:
    return len(_SUSPECT.findall(s)) * 2 + s.count(FFFD) + sum(
        1 for c in s if unicodedata.category(c) in ("Cc", "Co", "Cn") and c not in "\n\r\t"
    )


def _mixed_bytes(s: str) -> bytes | None:
    out = bytearray()
    for c in s:
        try:
            out += c.encode("cp1252")
        except UnicodeEncodeError:
            if ord(c) < 256:
                out.append(ord(c))
            else:
                return None
    return bytes(out)


_CP1252_HOLES = ("\x81", "\x8d", "\x8f", "\x90", "\x9d")


def _fix_latin_run(run: str) -> str:
    # U+FFFD は cp1252 で未定義のバイト（0x81 0x8D 0x8F 0x90 0x9D）が置換された跡。
    # 穴が 3 個以下なら候補を総当たりし、いちばん自然な復元を選ぶ。
    holes = run.count(FFFD)
    cands = [()] if holes == 0 else (
        list(product(_CP1252_HOLES, repeat=holes)) if holes <= 3 else [("\x81",) * holes]
    )
    best, best_score = run, _badness(run)
    for fill in cands:
        it = iter(fill)
        b = _mixed_bytes("".join(next(it) if c == FFFD else c for c in run))
        if b is None:
            continue
        fixed = b.decode("utf-8", "replace")
        score = _badness(fixed) + sum(
            1 for c in fixed if (unicodedata.category(c) in ("Zs", "Cf") and c != " ") or c == "\u2010"
        )
        if score < best_score:
            best, best_score = fixed, score
    return best


_CP932_MOJI = re.compile(r"[\uff61-\uff9f\u7e3a\u7e67\u90e2\u8b5b\u8373\u8c3a\u9adc\u9a5b\u9a3e\u8b1a\u8708\u873b\u8dfe\u96b1\u8475\u7e5d\u86fb\u9695\u9b06]")


def _fix_cp932(text: str) -> str:
    """UTF-8 を cp932 で読んだ典型（縺ゅ… / 繧ｳ…）を全体単位で戻す。"""
    if len(_CP932_MOJI.findall(text)) < 2:
        return text
    out = bytearray()
    for c in text:
        try:
            out += c.encode("cp932")
        except UnicodeEncodeError:
            out += "\ufffd".encode("utf-8") if c == FFFD else c.encode("utf-8")
    fixed = out.decode("utf-8", "replace")
    return fixed if len(_CP932_MOJI.findall(fixed)) < len(_CP932_MOJI.findall(text)) else text


def repair_mojibake(text: str) -> str:
    """復元できる文字化けを戻す。戻せないものはそのまま（collapse は別関数）。"""
    text = _fix_cp932(text)
    # 二重化けにも 2 回まで対応
    for _ in range(2):
        new = _LATIN_MOJI.sub(lambda m: _fix_latin_run(m.group(0)), text)
        if new == text:
            break
        text = new
    return text


_UNRECOV = re.compile(r"(?:[\ufffd\ue000-\uf8ff]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f])+(?:\s*(?:[\ufffd\ue000-\uf8ff]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f])+)*")


def collapse_unrecoverable(text: str) -> str:
    """U+FFFD・私用領域・制御文字の連続（間の空白も含む）を U+FFFD 1 文字に。"""
    return _UNRECOV.sub(FFFD, text)


def clean_mojibake(text: str) -> str:
    return collapse_unrecoverable(repair_mojibake(text))


def normalize_asr(text: str) -> str:
    """文字化け復元 → 復元不能部の集約 → 不確実表記の統一。"""
    return normalize_uncertain(clean_mojibake(text))
