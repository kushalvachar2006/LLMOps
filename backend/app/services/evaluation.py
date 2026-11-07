"""Pluggable evaluation framework.

Evaluators are small classes registered in EVALUATORS. Each one declares whether its result is
an OBJECTIVE computation or a MODEL JUDGMENT, so the UI can keep the two clearly apart.
None of these metrics proves factual correctness: they measure agreement with a reference,
format validity or simple rules, and nothing more.
"""
import difflib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from app.core.errors import ProviderError, ValidationAppError

OBJECTIVE = "objective"
MODEL_JUDGMENT = "model_judgment"


@dataclass
class EvalContext:
    output: str
    row: dict
    reference: str | None
    params: dict
    judge: Callable[[str], str] | None = None


@dataclass
class EvalResult:
    score: float | None
    passed: bool | None
    detail: str


def _norm(text: str, case_sensitive: bool, collapse_ws: bool) -> str:
    text = text.strip()
    if collapse_ws:
        text = " ".join(text.split())
    return text if case_sensitive else text.lower()


class Evaluator:
    type = ""
    kind = OBJECTIVE
    needs_reference = False
    description = ""
    limitations = ""
    param_docs: dict[str, str] = {}

    def validate_params(self, params: dict) -> None:  # noqa: B027 - optional hook
        pass

    def evaluate(self, ctx: EvalContext) -> EvalResult:
        raise NotImplementedError


class ExactMatch(Evaluator):
    type = "exact_match"
    needs_reference = True
    description = "1 if the output equals the reference answer after light normalisation."
    limitations = "Only suits short, closed answers. Correct answers worded differently fail."
    param_docs = {"case_sensitive": "default false", "normalize_whitespace": "default true"}

    def evaluate(self, ctx):
        if ctx.reference is None:
            return EvalResult(None, None, "No reference value in this row.")
        cs = bool(ctx.params.get("case_sensitive", False))
        ws = bool(ctx.params.get("normalize_whitespace", True))
        ok = _norm(ctx.output, cs, ws) == _norm(ctx.reference, cs, ws)
        return EvalResult(1.0 if ok else 0.0, ok, "match" if ok else "different from reference")


class TextSimilarity(Evaluator):
    type = "text_similarity"
    needs_reference = True
    description = "Character-level similarity (0-1) to the reference, plus token overlap F1."
    limitations = (
        "Measures how alike two texts look, NOT whether the output is true. "
        "Similar wording can still be wrong, and a correct paraphrase can score low."
    )
    param_docs = {"threshold": "pass mark between 0 and 1, default 0.8"}

    def validate_params(self, params):
        t = params.get("threshold", 0.8)
        if not isinstance(t, (int, float)) or not 0 <= t <= 1:
            raise ValidationAppError("text_similarity threshold must be between 0 and 1.")

    def evaluate(self, ctx):
        if ctx.reference is None:
            return EvalResult(None, None, "No reference value in this row.")
        a, b = _norm(ctx.output, False, True), _norm(ctx.reference, False, True)
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        ta, tb = Counter(a.split()), Counter(b.split())
        overlap = sum((ta & tb).values())
        f1 = 0.0 if not overlap else 2 * overlap / (sum(ta.values()) + sum(tb.values()))
        threshold = ctx.params.get("threshold", 0.8)
        return EvalResult(
            round(ratio, 4), ratio >= threshold, f"char similarity {ratio:.2f}, token F1 {f1:.2f}"
        )


class JsonValid(Evaluator):
    type = "json_valid"
    description = "1 if the output is valid JSON (and matches the JSON Schema, if one is given)."
    limitations = "Checks structure only. Valid JSON can still contain wrong values."
    param_docs = {"schema": "optional JSON Schema object"}

    def validate_params(self, params):
        schema = params.get("schema")
        if schema is None:
            return
        if not isinstance(schema, dict):
            raise ValidationAppError("json_valid schema must be a JSON object.")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ValidationAppError(f"Invalid JSON Schema: {exc.message[:150]}") from None

    def evaluate(self, ctx):
        text = ctx.output.strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        try:
            data = json.loads(text)
        except ValueError:
            return EvalResult(0.0, False, "not valid JSON")
        schema = ctx.params.get("schema")
        if schema:
            errors = sorted(Draft202012Validator(schema).iter_errors(data), key=str)
            if errors:
                return EvalResult(0.0, False, f"schema violation: {errors[0].message[:150]}")
        return EvalResult(1.0, True, "valid JSON" + (" matching schema" if schema else ""))


class ContainsKeywords(Evaluator):
    type = "contains_keywords"
    description = "Checks that required words or phrases appear in the output."
    limitations = "Plain substring matching; it cannot judge meaning or context."
    param_docs = {"keywords": "list of strings", "mode": "'all' (default) or 'any'",
                  "case_sensitive": "default false"}

    def validate_params(self, params):
        kw = params.get("keywords")
        if not isinstance(kw, list) or not 1 <= len(kw) <= 20 or not all(
            isinstance(k, str) and 0 < len(k) <= 100 for k in kw
        ):
            raise ValidationAppError("contains_keywords needs 1-20 non-empty keyword strings.")
        if params.get("mode", "all") not in ("all", "any"):
            raise ValidationAppError("contains_keywords mode must be 'all' or 'any'.")

    def evaluate(self, ctx):
        cs = bool(ctx.params.get("case_sensitive", False))
        hay = ctx.output if cs else ctx.output.lower()
        kws = ctx.params["keywords"]
        found = [k for k in kws if (k if cs else k.lower()) in hay]
        mode = ctx.params.get("mode", "all")
        passed = len(found) == len(kws) if mode == "all" else bool(found)
        return EvalResult(round(len(found) / len(kws), 4), passed, f"found {len(found)}/{len(kws)}")


class MaxLength(Evaluator):
    type = "max_length"
    description = "Passes if the output is at most N characters."
    limitations = "Counts characters only."
    param_docs = {"max_chars": "integer >= 1"}

    def validate_params(self, params):
        n = params.get("max_chars")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValidationAppError("max_length needs an integer max_chars >= 1.")

    def evaluate(self, ctx):
        n, limit = len(ctx.output), ctx.params["max_chars"]
        return EvalResult(1.0 if n <= limit else 0.0, n <= limit, f"{n} chars (limit {limit})")


class LlmJudge(Evaluator):
    type = "llm_judge"
    kind = MODEL_JUDGMENT
    description = "Another model call scores the output 1-5 against your rubric (optional, costs tokens)."
    limitations = (
        "This is a MODEL OPINION, not a measurement. Judges can be biased, inconsistent between "
        "runs, favour longer answers, and miss factual errors. Treat scores as a signal to review, "
        "never as proof of correctness or of absence of hallucination."
    )
    param_docs = {"rubric": "what a good answer looks like (required)",
                  "pass_score": "pass mark 1-5, default 4"}

    def validate_params(self, params):
        r = params.get("rubric")
        if not isinstance(r, str) or not 5 <= len(r.strip()) <= 2000:
            raise ValidationAppError("llm_judge needs a rubric of 5-2000 characters.")
        p = params.get("pass_score", 4)
        if not isinstance(p, int) or isinstance(p, bool) or not 1 <= p <= 5:
            raise ValidationAppError("llm_judge pass_score must be an integer 1-5.")

    def evaluate(self, ctx):
        if ctx.judge is None:
            return EvalResult(None, None, "No judge model available.")
        prompt = (
            "You are grading an AI answer. Use ONLY the rubric below.\n"
            f"Rubric: {ctx.params['rubric']}\n"
            f"Question/input data: {json.dumps(ctx.row, ensure_ascii=False)[:2000]}\n"
            f"Answer to grade: {ctx.output[:4000]}\n"
            'Reply with ONLY JSON: {"score": <integer 1-5>, "reason": "<one sentence>"}'
        )
        try:
            raw = ctx.judge(prompt)
        except ProviderError as exc:
            return EvalResult(None, None, f"judge call failed ({exc.category})")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            data = json.loads(match.group(0)) if match else {}
            score = int(data["score"])
            if not 1 <= score <= 5:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return EvalResult(None, None, "judge reply could not be read")
        pass_score = ctx.params.get("pass_score", 4)
        return EvalResult(float(score), score >= pass_score,
                          f"judge: {str(data.get('reason', ''))[:150]}")


EVALUATORS: dict[str, Evaluator] = {
    e.type: e
    for e in (ExactMatch(), TextSimilarity(), JsonValid(), ContainsKeywords(), MaxLength(), LlmJudge())
}


def describe_all() -> list[dict]:
    return [
        {"type": e.type, "kind": e.kind, "needs_reference": e.needs_reference,
         "description": e.description, "limitations": e.limitations, "params": e.param_docs}
        for e in EVALUATORS.values()
    ]
