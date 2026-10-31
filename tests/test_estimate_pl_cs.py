from TesseraTalk.tessera_talk import estimate_tokens

# o200k_base reference counts (tiktoken, measured 2026-10-31)
CASES = [
    ("Przepraszam, gdzie jest najbliższy przystanek autobusowy?", 18),
    ("Děkuji za pomoc, přijdu zítra.", 13),
    ("Zażółć gęślą jaźń.", 12),
    ("Příliš žluťoučký kůň úpěl ďábelské ódy.", 22),
]


def test_pl_cs_estimate_within_25_percent():
    for text, ref in CASES:
        est = estimate_tokens(text)
        assert abs(est - ref) <= max(2, ref // 4), (text, est, ref)


# o200k merges ı ğ ş İ đ well: no +1 for them (3bot review on #108)
TR_VI = [
    ("Bugün hava çok sıcak.", 6),
    ("yazılım", 3),
    ("başka", 2),
    ("Tôi muốn đi Hà Nội.", 7),
]


def test_tr_vi_not_overestimated():
    for text, ref in TR_VI:
        assert estimate_tokens(text) <= ref + 1, (text, estimate_tokens(text), ref)


def test_tr_vi_match_o200k():
    tiktoken = __import__("pytest").importorskip("tiktoken")
    e = tiktoken.get_encoding("o200k_base")
    for text, ref in TR_VI:
        assert len(e.encode(text)) == ref, text
