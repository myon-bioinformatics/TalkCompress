from __future__ import annotations

from shared.keep_check import check, extract_exact


SOURCE = (
    "Deploy https://example.com/a?b=1 from shared/config.yml at 2026-10-30. "
    "Do not delete commit 3f9a2c1d. If the check fails, retry (see #40)."
)


def _kinds(report) -> set[str]:
    return {m["kind"] for m in report.missing}


def test_extract_finds_exact_items():
    items = extract_exact(SOURCE)
    assert "https://example.com/a?b=1" in items["url"]
    assert "2026-10-30" in items["date"]
    assert "3f9a2c1d" in items["sha"]
    assert "#40" in items["issue"]
    # The path inside the URL is not double-counted as a separate path.
    assert "shared/config.yml" in items["path"]
    assert not any("example.com" in p for p in items["path"])


def test_identical_text_is_ok():
    report = check(SOURCE, SOURCE, ids=())
    assert report.ok
    assert report.count_drops == []


def test_missing_url_is_reported():
    compressed = SOURCE.replace("https://example.com/a?b=1", "the site")
    report = check(SOURCE, compressed)
    assert not report.ok
    assert "url" in _kinds(report)


def test_dropped_negation_is_reported_as_count_drop():
    compressed = "Deploy https://example.com/a?b=1 from shared/config.yml at 2026-10-30. Delete commit 3f9a2c1d. If the check fails, retry (see #40)."
    report = check(SOURCE, compressed)
    assert {"kind": "negation", "source": 1, "compressed": 0} in report.count_drops


def test_dropped_condition_is_reported_as_count_drop():
    compressed = "Deploy https://example.com/a?b=1 from shared/config.yml at 2026-10-30. Do not delete commit 3f9a2c1d. Retry (see #40)."
    report = check(SOURCE, compressed)
    assert {"kind": "condition", "source": 1, "compressed": 0} in report.count_drops


def test_missing_id_pair_is_reported():
    report = check(SOURCE, "no ids here", ids=("#40 keep-check",))
    assert {"kind": "id", "item": "#40 keep-check"} in report.missing


def test_secret_in_compressed_fails_even_if_source_has_it():
    source = SOURCE + " key sk-abcdefghijklmnopqrstu123"
    compressed = SOURCE + " key sk-abcdefghijklmnopqrstu123"
    report = check(source, compressed)
    assert not report.ok
    assert report.secrets


def test_secret_removed_from_compressed_is_fine():
    source = SOURCE + " token=abc123secret"
    report = check(source, SOURCE)
    assert report.ok


def test_sha_pattern_ignores_plain_words():
    items = extract_exact("the decade and cafe and 1234567 are not hashes")
    assert items["sha"] == set()


def test_japanese_negation_drop_is_reported():
    report = check("削除しない。", "削除。")
    assert {"kind": "negation", "source": 1, "compressed": 0} in report.count_drops


def test_number_inside_larger_item_not_reported_twice():
    items = extract_exact("on 2026-10-30 see #40 and 7 files")
    assert items["number"] == {"7"}


def test_language_labels_are_not_paths_but_explicit_paths_remain():
    from shared.keep_check import extract_exact
    paths = extract_exact("ES/DE/FR EN/JA shared/config.yml ./ES/DE/FR")['path']
    assert paths == {'shared/config.yml', './ES/DE/FR'}



def test_overlap_suppression_uses_occurrence_positions():
    for enclosing in ('#142', 'https://example.com/142', 'abc142def', '2042-10-30', 'dir/142'):
        source = f'Budget 42; reference {enclosing}'
        assert '42' in extract_exact(source)['number']
        assert {'kind': 'number', 'item': '42'} in check(source, enclosing).missing
    assert extract_exact('42; issue #42')['number'] == {'42'}
    assert extract_exact('#142')['number'] == set()


def test_path_at_separate_position_is_not_suppressed_by_url():
    source = 'https://example.com/dir/file dir/file'
    assert 'dir/file' in extract_exact(source)['path']
    assert {'kind': 'path', 'item': 'dir/file'} in check(source, 'https://example.com/dir/file').missing


def test_complete_tokens_not_substrings():
    cases = [
        ('number', '42', '142'),
        ('number', '42', '#42'),
        ('number', '42', '42.5'),
        ('number', '42', 'abc42'),
        ('sha', 'abc1234', 'abc12345'),
        ('sha', 'abc1234', 'xabc1234'),
        ('date', '2026-10-30', '2026-10-300'),
        ('url', 'https://example.com/a', 'https://example.com/ab'),
        ('url', 'https://example.com/a', 'https://example.com/a?x=1'),
        ('issue', '#40', '#400'),
        ('issue', '#40', 'abc#40'),
        ('issue', '#40', '##40'),
        ('url', 'https://example.com/a', 'xhttps://example.com/a'),
        ('path', 'dir/file', 'dir/file2'),
    ]
    for kind, original, changed in cases:
        assert {'kind': kind, 'item': original} in check(original, changed).missing
        assert check(original, f'({original})').ok


def test_custom_identifier_boundaries():
    assert check('', '(#40 keep-check)', ids=('#40 keep-check',)).ok
    assert not check('', '#40 keep-checker', ids=('#40 keep-check',)).ok
    assert not check('', '#400', ids=('#40',)).ok


def test_number_followed_by_sentence_period_is_preserved():
    assert check('Budget 42', 'Budget 42.').ok
    assert extract_exact('Budget 42.')['number'] == {'42'}


def test_negation_counts_curly_apostrophe():
    from shared.keep_check import check, count_items

    assert count_items("I don\u2019t agree. I can\u2019t go.")["negation"] == 2
    assert count_items("I don't agree")["negation"] == 1
    report = check("We don\u2019t ship on Friday.", "We ship on Friday.")
    assert report.count_drops == [{"kind": "negation", "source": 1, "compressed": 0}]
