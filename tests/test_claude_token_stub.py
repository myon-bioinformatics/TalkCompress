from __future__ import annotations

import json

from shared.claude_token_stub import (
    NEW_TOKENIZER_FACTOR,
    count,
    load_fixture,
    text_key,
    uses_new_tokenizer,
)


def test_new_tokenizer_families_by_version_and_name():
    assert uses_new_tokenizer("claude-opus-4-7")
    assert uses_new_tokenizer("claude-opus-4-8")
    assert uses_new_tokenizer("claude-haiku-5-5")
    assert uses_new_tokenizer("claude-sonnet-5-5")
    assert uses_new_tokenizer("claude-mythos-preview")
    assert not uses_new_tokenizer("claude-opus-4-6")
    assert not uses_new_tokenizer("claude-sonnet-4-6")
    assert not uses_new_tokenizer("claude-haiku-4-5-20251001")


def test_unknown_model_strings_are_not_new_tokenizer():
    assert not uses_new_tokenizer("gpt-4o")
    assert not uses_new_tokenizer("")


def test_scaled_count_is_labelled_and_uses_documented_factor():
    text = "Deploy the build and run the tests."
    old = count(text, "claude-sonnet-4-6")
    new = count(text, "claude-opus-4-7")
    assert old.source == "estimate"
    assert new.source == "scaled"
    assert new.tokens == round(old.tokens * NEW_TOKENIZER_FACTOR)


def test_fixture_wins_and_is_labelled(tmp_path):
    text = "https://example.com/spec"
    model = "claude-haiku-5-5"
    path = tmp_path / "calib.json"
    path.write_text(json.dumps({"counts": {text_key(text, model): 7}}), encoding="utf-8")
    fixture = load_fixture(path)
    result = count(text, model, fixture)
    assert result.source == "fixture"
    assert result.tokens == 7


def test_fixture_is_keyed_by_model(tmp_path):
    text = "same text"
    path = tmp_path / "calib.json"
    path.write_text(json.dumps({"counts": {text_key(text, "claude-haiku-5-5"): 3}}), encoding="utf-8")
    fixture = load_fixture(path)
    assert count(text, "claude-sonnet-4-6", fixture).source == "estimate"


def test_missing_fixture_file_is_empty():
    assert load_fixture(None) == {}
