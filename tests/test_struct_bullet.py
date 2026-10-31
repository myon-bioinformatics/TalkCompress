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


import pytest


@pytest.mark.parametrize(
    "text",
    [
        "Use e.g. this.", "Use E.g. this.", "Use i.e. this.", "Use I.e. this.",
        "See cf. that.", "See Cf. that.", "Red vs. blue.", "Red Vs. blue.",
        "Ask Mr. Smith.", "Ask Mrs. Smith.", "Ask Ms. Smith.", "Ask Dr. Smith.",
        "Pack A, B, etc. and go.",
    ],
)
def test_each_abbreviation_guard_keeps_one_sentence(text):
    from shared.struct_bullet import to_bullets

    assert "\n" not in to_bullets(text), text


def test_etc_followed_by_capital_still_splits():
    from shared.struct_bullet import to_bullets

    assert to_bullets("A, B, etc. Then go.") == "- A, B, etc\n- Then go"


@pytest.mark.parametrize(
    "text",
    ["Café e.g. crème. Then go.", "Señor vs. José. Then go.", "Ask Dr. Müller. Then go.", "Zoë, Chloé, etc. Then go."],
)
def test_nfd_and_accented_input_splits_like_nfc(text):
    import unicodedata

    from shared.struct_bullet import to_bullets

    nfc = to_bullets(unicodedata.normalize("NFC", text))
    assert to_bullets(unicodedata.normalize("NFD", text)) == nfc
    assert nfc.count("\n") == 1, nfc


def test_to_bullets_capitalizes_non_ascii_initial():
    import unicodedata

    assert to_bullets("élan is key. elan is key.") == "- Élan is key\n- Elan is key"
    assert to_bullets(unicodedata.normalize("NFD", "élan is key.")) == "- Élan is key"
    assert to_bullets("øre. ñu.") == "- Øre\n- Ñu"
    # 1 文字で表せない大文字（ß→SS）は変えない
    assert to_bullets("ßtraße ist hier.") == "- ßtraße ist hier"
    # ǆ は文頭用のタイトルケース ǅ にする（大文字の Ǆ ではない）
    assert to_bullets("ǆungla.") == "- ǅungla"
    # すでに大文字の Ǆ はタイトルケースに変えない
    assert to_bullets("Ǆungla.") == "- Ǆungla"
    # ᾀ は大文字だと 2 文字（ἈΙ）だが、タイトルケースは 1 文字（ᾈ）
    assert to_bullets("ᾀ x.") == "- ᾈ x"
