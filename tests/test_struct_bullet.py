from __future__ import annotations

from shared.keep_check import check
from shared.struct_bullet import strip_fillers, to_bullets


def test_each_sentence_becomes_one_bullet():
    text = "Deploy the build. Run the tests! Check the logs?"
    assert to_bullets(text) == "- Deploy the build\n- Run the tests!\n- Check the logs?"


def test_leading_fillers_are_removed():
    assert strip_fillers("Um, so basically we ship it") == "we ship it"
    assert strip_fillers("Also run the check") == "run the check"


def test_japanese_sentences_split_on_full_width_stop():
    assert to_bullets("設定を確認する。テストを走らせる。") == "- 設定を確認する\n- テストを走らせる"


def test_negation_and_condition_are_kept_when_present():
    source = "Do not delete the branch. If the check fails, retry."
    bullets = to_bullets(source)
    report = check(source, bullets)
    assert report.ok
    assert report.count_drops == []


def test_url_and_sha_survive_bullets():
    source = "Use https://example.com/spec and commit 3f9a2c1d."
    report = check(source, to_bullets(source))
    assert report.ok


def test_empty_input_gives_empty_output():
    assert to_bullets("") == ""
    assert to_bullets("   \n  ") == ""


def test_first_ascii_letter_is_capitalized_after_filler_removal():
    assert to_bullets("Um, so basically we ship it.") == "- We ship it"


def test_marker_can_be_empty_for_plain_lines():
    assert to_bullets("Deploy the build. Run the tests.", marker="") == "Deploy the build\nRun the tests"


def test_abbreviation_does_not_split_sentence():
    from shared.struct_bullet import to_bullets

    assert to_bullets("See e.g. the file. Use i.e. this one.") == "- See e.g. the file\n- Use i.e. this one"
