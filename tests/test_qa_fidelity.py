from __future__ import annotations

from shared.qa_fidelity import build_probes, make_prompt, score


SOURCE = "Deploy https://example.com/a from shared/config.yml on 2026-10-30 for #40, commit 3f9a2c1d."


def test_probes_cover_each_exact_item_kind():
    probes = build_probes(SOURCE, ids=("#40 keep-check",))
    expected = {p.expected for p in probes}
    assert "https://example.com/a" in expected
    assert "shared/config.yml" in expected
    assert "2026-10-30" in expected
    assert "#40" in expected
    assert "3f9a2c1d" in expected
    assert "#40 keep-check" in expected


def test_prompt_contains_only_compressed_context_and_question():
    prompt = make_prompt("compressed text", "Which date is mentioned?")
    assert "Context:\ncompressed text" in prompt
    assert "Question: Which date is mentioned?" in prompt
    assert "2026-10-30" not in prompt


def test_perfect_answerer_scores_one():
    probes = build_probes(SOURCE)

    def answer(prompt: str) -> str:
        # Answers with every expected item, so every probe is hit.
        return " ".join(p.expected for p in probes)

    result = score(probes, SOURCE, answer)
    assert result["score"] == 1.0
    assert result["hits"] == result["total"] == len(probes)


def test_unknown_answerer_scores_zero():
    probes = build_probes(SOURCE)
    result = score(probes, SOURCE, lambda prompt: "unknown")
    assert result["hits"] == 0
    assert result["score"] == 0.0


def test_empty_source_has_no_probes_and_no_division_error():
    result = score([], "", lambda prompt: "")
    assert result["total"] == 0
    assert result["score"] is None


def test_dates_allow_equivalent_calendar_forms_but_not_wrong_dates():
    from shared.qa_fidelity import Probe, matches
    p = Probe('date', 'List dates', '2026-10-30')
    for answer in ['October 30, 2026', '30 October 2026', '2026/10/30', '2026年10月30日']:
        assert matches(p, answer)
    for answer in ['October 31, 2026', 'October 30, 2025', '2026-10-300', '12026-10-30']:
        assert not matches(p, answer)


def test_identifiers_do_not_match_longer_values():
    from shared.qa_fidelity import Probe, matches
    for kind, expected, wrong in [
        ('issue', '#40', '#400'), ('number', '3', '30'),
        ('number', '3', '3.5'), ('number', '3', 'o3'),
        ('sha', '3f9a2c1d', '3f9a2c1d0'),
        ('path', 'shared/config.yml', 'shared/config.yml.bak'),
        ('url', 'https://example.com/a', 'https://example.com/ab'),
        ('url', 'https://example.com/a', 'https://example.com/a?x=1'),
        ('url', 'https://example.com/a', 'https://example.com/a:8080'),
    ]:
        p = Probe(kind, 'List values', expected)
        assert not matches(p, wrong)
        assert matches(p, f'The value is {expected}.')


def test_id_question_does_not_reveal_answer_to_empty_context():
    probes = build_probes('Keep project_alpha.', ids=('project_alpha',))
    assert all('project_alpha' not in p.question for p in probes)
    assert score(probes, '', lambda prompt: 'project_alpha' if 'project_alpha' in prompt else 'unknown')['hits'] == 0


def test_multiple_values_use_an_exhaustive_question():
    probes = build_probes('Keep #40 and #41.')
    assert len(probes) == 2
    assert all('all' in p.question for p in probes)
    assert score(probes, 'Keep #40 and #41.', lambda _: '#40, #41')['hits'] == 2


def test_only_final_answer_counts_and_unfinished_reasoning_has_no_hit():
    probes = build_probes('Keep #40.')
    assert score(probes, 'Keep #40.', lambda _: '<think>It is #40</think>unknown')['hits'] == 0
    import pytest
    with pytest.raises(ValueError, match="no completed final answer"):
        score(probes, 'Keep #40.', lambda _: '<think>It is #40')
    assert score(probes, 'Keep #40.', lambda _: '<think>reason</think>#40')['hits'] == 1
    assert score(probes, 'Keep #40.', lambda _: '#40</think>unknown')['hits'] == 0


def test_no_probes_is_explicitly_not_applicable_and_does_not_call_model():
    def unexpected(_):
        raise AssertionError("No model call expected")
    probes = build_probes("Languages ES/DE/FR")
    assert probes == []
    report = score(probes, "", unexpected)
    assert report['status'] == 'not_applicable'
    assert report['total'] == 0
    assert report['score'] is None
    assert score(build_probes("#40"), "", lambda _: "unknown")['status'] == 'scored'


def test_exact_case_sensitive_values_and_numeric_boundaries():
    from shared.qa_fidelity import Probe, matches
    for kind, expected, answer in [
        ('path', 'shared/Config.yml', 'shared/config.yml'),
        ('url', 'https://example.com/A', 'https://example.com/a'),
        ('id', 'ProjectAlpha', 'projectalpha'),
        ('number', '3', '-3'), ('number', '3', '0.3'),
        ('number', '3', '3,000'), ('number', '3', '+3'),
    ]:
        assert not matches(Probe(kind, 'List values', expected), answer)


def test_empty_or_reasoning_only_command_output_is_invalid():
    import pytest
    for answer in ['', '   ', '<think>#40</think>']:
        with pytest.raises(ValueError):
            score(build_probes('#40'), '', lambda _: answer)



def test_numeric_probe_survives_overlapping_issue_number():
    probes = build_probes('Budget 42; issue #142')
    assert any(p.kind == 'number' and p.expected == '42' for p in probes)


def test_scoring_rejects_longer_tokens():
    for source, answer in [('#40', '#400'), ('42', '142'), ('abc1234', 'abc12345'),
                           ('2026-10-30', '2026-10-300'),
                           ('https://example.com/a', 'https://example.com/ab')]:
        result = score(build_probes(source), answer, lambda prompt: answer)
        assert result['hits'] == 0


def test_reasoning_does_not_supply_answers():
    probes = build_probes('#40')
    for answer in ('<think>#40</think> unknown', '#40</think> unknown'):
        assert score(probes, '', lambda prompt: answer)['hits'] == 0
    assert score(probes, '', lambda prompt: '<think>#400</think>#40')['hits'] == 1


def test_custom_id_not_leaked_in_question():
    probes = build_probes('', ids=('unseen-value',))
    assert 'unseen-value' not in make_prompt('', probes[0].question)


def test_sentence_final_number_is_scored():
    assert score(build_probes('42'), '', lambda prompt: '42.')['hits'] == 1

