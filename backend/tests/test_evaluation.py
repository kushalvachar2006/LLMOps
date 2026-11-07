import pytest
from app.core.errors import ProviderRateLimitError, ValidationAppError
from app.services.evaluation import EVALUATORS, MODEL_JUDGMENT, OBJECTIVE, EvalContext


def run(kind, output, reference=None, judge=None, **params):
    ev = EVALUATORS[kind]
    ev.validate_params(params)
    return ev.evaluate(EvalContext(output, {"q": "x"}, reference, params, judge))


def test_exact_match_normalises_case_and_whitespace():
    assert run("exact_match", "  paris \n", "Paris").passed is True
    assert run("exact_match", "Lyon", "Paris").score == 0.0
    assert run("exact_match", "paris", "Paris", case_sensitive=True).passed is False
    assert run("exact_match", "a", None).score is None  # missing reference is "not scored"


def test_text_similarity_is_graded_and_documented_as_not_truth():
    hi = run("text_similarity", "The capital is Paris", "The capital is Paris.")
    lo = run("text_similarity", "Bananas are yellow", "The capital is Paris.")
    assert hi.score > 0.9 and hi.passed and lo.score < 0.5 and not lo.passed
    assert "NOT whether the output is true" in EVALUATORS["text_similarity"].limitations
    with pytest.raises(ValidationAppError):
        EVALUATORS["text_similarity"].validate_params({"threshold": 3})


def test_json_valid_with_and_without_schema_and_fences():
    assert run("json_valid", '{"a": 1}').passed is True
    assert run("json_valid", "```json\n{\"a\": 1}\n```").passed is True
    assert run("json_valid", "not json").passed is False
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    assert run("json_valid", '{"name": "x"}', schema=schema).passed is True
    bad = run("json_valid", '{"name": 5}', schema=schema)
    assert bad.passed is False and "schema" in bad.detail
    with pytest.raises(ValidationAppError):
        EVALUATORS["json_valid"].validate_params({"schema": {"type": "nonsense"}})


def test_keywords_modes_and_validation():
    assert run("contains_keywords", "Paris is in France", keywords=["paris", "france"]).passed
    r = run("contains_keywords", "Paris only", keywords=["paris", "france"])
    assert r.passed is False and r.score == 0.5
    assert run("contains_keywords", "Paris only", keywords=["paris", "x"], mode="any").passed
    with pytest.raises(ValidationAppError):
        EVALUATORS["contains_keywords"].validate_params({"keywords": []})


def test_max_length():
    assert run("max_length", "abc", max_chars=3).passed is True
    assert run("max_length", "abcd", max_chars=3).passed is False
    with pytest.raises(ValidationAppError):
        EVALUATORS["max_length"].validate_params({"max_chars": 0})


def test_kinds_are_clearly_separated():
    kinds = {e.type: e.kind for e in EVALUATORS.values()}
    assert kinds["llm_judge"] == MODEL_JUDGMENT
    assert all(k == OBJECTIVE for t, k in kinds.items() if t != "llm_judge")
    assert "not proof" in EVALUATORS["llm_judge"].limitations.lower() or \
           "never as proof" in EVALUATORS["llm_judge"].limitations.lower()


def test_judge_parses_score_and_handles_garbage_and_failures():
    ok = run("llm_judge", "ans", judge=lambda p: 'Sure {"score": 5, "reason": "great"}',
             rubric="Must be correct")
    assert ok.score == 5.0 and ok.passed is True
    low = run("llm_judge", "ans", judge=lambda p: '{"score": 2, "reason": "meh"}', rubric="Must be correct")
    assert low.passed is False
    junk = run("llm_judge", "ans", judge=lambda p: "I refuse", rubric="Must be correct")
    assert junk.score is None and junk.passed is None

    def boom(_):
        raise ProviderRateLimitError("quota")

    failed = run("llm_judge", "ans", judge=boom, rubric="Must be correct")
    assert failed.score is None and "rate_limited" in failed.detail
    with pytest.raises(ValidationAppError):
        EVALUATORS["llm_judge"].validate_params({"rubric": "x"})


def test_evaluators_endpoint_lists_limitations(client):
    body = client.get("/api/evaluators").json()
    assert {e["type"] for e in body} >= {"exact_match", "llm_judge", "json_valid"}
    assert all(e["limitations"] for e in body)
