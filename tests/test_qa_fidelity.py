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
