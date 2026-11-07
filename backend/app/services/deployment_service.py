"""Deployment lifecycle: publish -> validate -> promote between environments -> observe."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationAppError,
)
from app.repositories.assets import PromptRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.monitoring import MetricsRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.deployment import ENVIRONMENTS, DeploymentCreate, PromoteRequest, PublishRequest
from app.schemas.llm import GenerateRequest
from app.services.evaluation import EVALUATORS, EvalContext
from app.services.llm_service import LLMService
from app.services.model_catalog import validate_generation
from app.services.template import extract_variables, render

log = logging.getLogger(__name__)
CREATED_BY = "local-user"  # the management API has no user accounts yet
_SNAPSHOT = ["system_instruction", "template", "provider", "model", "temperature",
             "max_output_tokens"]


def _now() -> datetime:
    return datetime.now(UTC)


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": passed, "detail": detail}


def deployment_status(dep: dict) -> str:
    return "active" if any(v is not None for v in dep["environments"].values()) else "inactive"


class DeploymentService:
    def __init__(self, deployments: DeploymentRepository, prompts: PromptRepository,
                 projects: ProjectRepository, metrics: MetricsRepository):
        self._deps = deployments
        self._prompts = prompts
        self._projects = projects
        self._metrics = metrics

    # ----- deployments
    def _view(self, dep: dict) -> dict:
        return {**dep, "status": deployment_status(dep)}

    def create(self, data: DeploymentCreate) -> dict:
        self._projects.get(data.project_id)
        return self._view(self._deps.create(data.project_id, data.name, data.description))

    def get(self, deployment_id: str) -> dict:
        return self._view(self._deps.get(deployment_id))

    def list(self, project_id: str | None) -> list[dict]:
        return [self._view(d) for d in self._deps.list(project_id)]

    def list_versions(self, deployment_id: str) -> list[dict]:
        self._deps.get(deployment_id)
        return self._deps.list_versions(deployment_id)

    def events(self, deployment_id: str) -> list[dict]:
        self._deps.get(deployment_id)
        return self._deps.list_events(deployment_id)

    # ----- validation
    def _run_checks(self, llm: LLMService, dep: dict, ver: dict) -> list[dict]:
        """Configuration checks first (no network), then a live probe of the real model."""
        cfg, checks = ver["config"], []
        try:
            validate_generation(cfg["provider"], cfg["model"], cfg["temperature"],
                                cfg["max_output_tokens"])
            checks.append(_check("model_configuration", True, "provider, model and limits are valid"))
        except ValidationAppError as exc:
            return [_check("model_configuration", False, exc.message)]

        variables = ver["variables"]
        samples = ver["validation_spec"]["sample_inputs"] or [
            {v: f"sample {v}" for v in variables}
        ]
        for i, sample in enumerate(samples, start=1):
            missing = [v for v in variables if v not in sample]
            extra = [k for k in sample if k not in variables]
            if missing or extra:
                detail = []
                if missing:
                    detail.append(f"missing {', '.join(missing)}")
                if extra:
                    detail.append(f"unknown {', '.join(map(str, extra))}")
                checks.append(_check("sample_inputs", False, f"sample {i}: " + "; ".join(detail)))
                return checks
        checks.append(_check("sample_inputs", True, f"{len(samples)} sample input(s) match the template"))

        spec = ver["validation_spec"]
        outputs: list[str] = []
        for sample in samples:
            try:
                req = GenerateRequest(
                    prompt=render(cfg["template"], {k: str(v) for k, v in sample.items()}),
                    system_instruction=cfg["system_instruction"], provider=cfg["provider"],
                    model=cfg["model"], temperature=cfg["temperature"],
                    max_output_tokens=cfg["max_output_tokens"], project_id=dep["project_id"],
                )
                resp = llm.generate(req, extra={
                    "deployment_id": dep["id"], "deployment_version": ver["version"],
                    "environment": "validation", "prompt_id": ver["prompt_id"],
                    "prompt_version": ver["prompt_version"], "purpose": "deployment_validation",
                })
                outputs.append(resp.text)
            except ValidationError:
                checks.append(_check("model_call", False, "rendered prompt is invalid or too long"))
                return checks
            except AppError as exc:
                checks.append(_check("model_call", False, f"model call failed ({exc.category})"))
                return checks
        checks.append(_check("model_call", True, f"{len(outputs)} live call(s) succeeded"))
        checks.append(_check("non_empty_output", all(o.strip() for o in outputs),
                             "every output had text" if all(o.strip() for o in outputs)
                             else "the model returned empty output"))
        if spec["expect_json"]:
            ok = all(EVALUATORS["json_valid"].evaluate(EvalContext(o, {}, None, {})).passed
                     for o in outputs)
            checks.append(_check("json_output", ok, "all outputs are valid JSON" if ok
                                 else "an output was not valid JSON"))
        if spec["max_output_chars"]:
            limit = spec["max_output_chars"]
            ok = all(len(o) <= limit for o in outputs)
            checks.append(_check("max_output_chars", ok, f"outputs within {limit} characters" if ok
                                 else f"an output exceeded {limit} characters"))
        return checks

    @staticmethod
    def _health(checks: list[dict]) -> dict:
        failed = [c["name"] for c in checks if not c["passed"]]
        return {"status": "unhealthy" if failed else "healthy", "checked_at": _now(),
                "detail": ("failed: " + ", ".join(failed)) if failed else "all checks passed"}

    # ----- publish
    def publish(self, deployment_id: str, data: PublishRequest, llm: LLMService) -> dict:
        dep = self._deps.get(deployment_id)
        prompt = self._prompts.get(data.prompt_id)
        if prompt["project_id"] != dep["project_id"]:
            raise ValidationAppError("The prompt must belong to the same project as the deployment.")
        pv = self._prompts.get_version(prompt["id"], data.prompt_version or prompt["latest_version"])
        llm.resolve_provider(pv["provider"])  # no credentials -> clear error, nothing is saved

        number = self._deps.next_version(deployment_id)
        ver = self._deps.insert_version({
            "deployment_id": deployment_id, "project_id": dep["project_id"], "version": number,
            "prompt_id": prompt["id"], "prompt_name": prompt["name"], "prompt_version": pv["version"],
            "config": {k: pv[k] for k in _SNAPSHOT}, "variables": extract_variables(pv["template"]),
            "validation_spec": data.validation.model_dump(), "validation_report": None,
            "status": "validating", "health": {"status": "unknown", "checked_at": None,
                                                 "detail": "not checked yet"},
            "change_description": data.change_description, "created_by": CREATED_BY,
        })
        try:
            checks = self._run_checks(llm, dep, ver)
        except Exception:  # noqa: BLE001 - never leave a version stuck in "validating"
            log.exception("deployment validation crashed")
            checks = [_check("validation", False, "validation could not be completed")]
        passed = all(c["passed"] for c in checks)
        return self._deps.update_version(deployment_id, number, {
            "status": "ready" if passed else "failed",
            "validation_report": {"passed": passed, "checks": checks, "ran_at": _now()},
            "health": self._health(checks),
        })

    def health_check(self, deployment_id: str, version: int, llm: LLMService) -> dict:
        dep = self._deps.get(deployment_id)
        ver = self._deps.get_version(deployment_id, version)
        llm.resolve_provider(ver["config"]["provider"])
        checks = self._run_checks(llm, dep, ver)
        return self._deps.update_version(deployment_id, version, {
            "health": {**self._health(checks), "checks": checks}})

    # ----- environments
    def promote(self, deployment_id: str, data: PromoteRequest) -> dict:
        dep = self._deps.get(deployment_id)
        ver = self._deps.get_version(deployment_id, data.version)
        if ver["status"] != "ready":
            raise ConflictError("Only versions whose validation passed can be promoted.")
        if data.environment == "production" and ver["health"]["status"] == "unhealthy":
            raise ConflictError("This version's latest health check failed, so it cannot go to production.")
        previous = dep["environments"].get(data.environment)
        updated = self._deps.set_environment(deployment_id, data.environment, data.version)
        kind = "rollback" if previous is not None and data.version < previous else "promote"
        self._deps.add_event({"deployment_id": deployment_id, "type": kind,
                              "environment": data.environment, "from_version": previous,
                              "to_version": data.version, "by": CREATED_BY})
        return self._view(updated)

    def unpublish(self, deployment_id: str, environment: str) -> dict:
        if environment not in ENVIRONMENTS:
            raise ValidationAppError(f"environment must be one of {', '.join(ENVIRONMENTS)}")
        dep = self._deps.get(deployment_id)
        previous = dep["environments"].get(environment)
        if previous is None:
            raise NotFoundError("Nothing is live in that environment.")
        updated = self._deps.set_environment(deployment_id, environment, None)
        self._deps.add_event({"deployment_id": deployment_id, "type": "unpublish",
                              "environment": environment, "from_version": previous,
                              "to_version": None, "by": CREATED_BY})
        return self._view(updated)

    # ----- usage
    def usage(self, deployment_id: str, start: datetime, end: datetime) -> dict:
        self._deps.get(deployment_id)
        match = {"deployment_id": deployment_id, "environment": {"$ne": "validation"},
                 "created_at": {"$gte": start, "$lt": end}}
        counts = self._metrics.counts(match)
        if counts["total"] == 0:
            return {"empty": True, "total": 0, "window": {"start": start, "end": end}}
        sums = self._metrics.sums(match)

        def rows(fields):
            return [{**r["_id"], "requests": r["requests"], "failed": r["failed"],
                     "avg_latency_ms": None if r["avg_latency_ms"] is None
                     else round(r["avg_latency_ms"], 1),
                     "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]}
                    for r in self._metrics.group_by(match, fields)]

        return {
            "empty": False, "window": {"start": start, "end": end}, "total": counts["total"],
            "failed": counts["failed"], "error_rate": round(counts["failed"] / counts["total"], 4),
            "avg_latency_ms": None if sums["avg_latency_ms"] is None
            else round(sums["avg_latency_ms"], 1),
            "p95_latency_ms": self._metrics.percentile(match, "latency_ms", 95),
            "input_tokens": sums["input_tokens"], "output_tokens": sums["output_tokens"],
            "by_environment": rows({"environment": "environment"}),
            "by_version": rows({"version": "deployment_version"}),
            "by_api_key": rows({"api_key_id": "api_key_id"}),
            "note": "Validation probes are excluded. Tokens are provider-reported.",
        }

