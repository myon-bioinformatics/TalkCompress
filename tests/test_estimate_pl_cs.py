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
