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
