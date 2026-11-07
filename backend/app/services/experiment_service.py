"""Runs a prompt version over a dataset version and records everything needed to reproduce it."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, ProviderAuthError, ValidationAppError
from app.repositories.assets import DatasetRepository, ExperimentRepository, PromptRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.experiment import ExperimentCreate
from app.schemas.llm import GenerateRequest
from app.services.dataset_parser import SPLITS
from app.services.evaluation import EVALUATORS, EvalContext, EvalResult
from app.services.llm_service import LLMService
from app.services.template import extract_variables, render

log = logging.getLogger(__name__)
MAX_CONSECUTIVE_ERRORS = 3
_SNAPSHOT = ["system_instruction", "template", "provider", "model", "temperature",
             "max_output_tokens"]


class ExperimentService:
    def __init__(self, experiments: ExperimentRepository, prompts: PromptRepository,
                 datasets: DatasetRepository, projects: ProjectRepository,
                 llm: LLMService, settings: Settings):
        self._exps = experiments
        self._prompts = prompts
        self._datasets = datasets
        self._projects = projects
        self._llm = llm
        self._settings = settings

    # ---------- validation ----------
    def _evaluator_configs(self, data: ExperimentCreate, fields: set[str]) -> list[dict]:
        configs, used = [], Counter_like()
        for cfg in data.evaluators:
            ev = EVALUATORS.get(cfg.type)
            if ev is None:
                raise ValidationAppError(f"Unknown evaluator '{cfg.type}'.")
            ev.validate_params(cfg.params)
            if ev.needs_reference and (not data.reference_field or data.reference_field not in fields):
                raise ValidationAppError(
                    f"'{cfg.type}' needs a reference_field that exists in the dataset."
                )
            n = used.bump(cfg.type)
            name = cfg.type if n == 1 else f"{cfg.type}_{n}"
            configs.append({"name": name, "type": cfg.type, "params": cfg.params})
        return configs

    # ---------- run ----------
    def run(self, data: ExperimentCreate) -> dict:
        self._projects.get(data.project_id)
        prompt = self._prompts.get(data.prompt_id)
        dataset = self._datasets.get(data.dataset_id)
        if prompt["project_id"] != data.project_id or dataset["project_id"] != data.project_id:
            raise ValidationAppError("The prompt and dataset must belong to the chosen project.")
        pv = self._prompts.get_version(prompt["id"], data.prompt_version or prompt["latest_version"])
        dv = self._datasets.get_version(
            dataset["id"], data.dataset_version or dataset["latest_version"]
        )
        fields = {f["name"] for f in dv["schema"]}
        missing = [v for v in extract_variables(pv["template"]) if v not in fields]
        if missing:
            raise ValidationAppError(
                f"Template uses field(s) not in the dataset: {', '.join(missing)}."
            )
        if data.split not in ("all", "unassigned", *SPLITS):
            raise ValidationAppError("split must be all, train, validation, eval or unassigned.")
        evaluators = self._evaluator_configs(data, fields)
        limit = min(data.max_rows, self._settings.experiment_max_rows)
        rows, available = self._datasets.list_rows(dv["id"], data.split, 0, limit)
        if not rows:
            raise ValidationAppError(f"The '{data.split}' split has no rows.")
        self._llm.resolve_provider(pv["provider"])  # fail fast if there is no API key

        snapshot = {k: pv[k] for k in _SNAPSHOT}
        exp = self._exps.insert({
            "project_id": data.project_id, "name": data.name,
            "prompt_id": prompt["id"], "prompt_version": pv["version"],
            "prompt_version_id": pv["id"], "config": snapshot,
            "dataset_id": dataset["id"], "dataset_version": dv["version"],
            "dataset_version_id": dv["id"], "dataset_sha256": dv["content_sha256"],
            "split": data.split, "rows_available": available, "rows_planned": len(rows),
            "evaluators": evaluators, "reference_field": data.reference_field,
            "status": "running", "started_at": datetime.now(UTC),
        })

        results, consecutive, aborted = [], 0, None
        for row in rows:
            doc = self._run_row(exp, pv, row, evaluators, data.reference_field, data.project_id)
            self._exps.insert_result(doc)
            results.append(doc)
            consecutive = consecutive + 1 if doc["status"] == "error" else 0
            if doc["status"] == "error" and (
                doc["error_category"] == ProviderAuthError.category
                or consecutive >= MAX_CONSECUTIVE_ERRORS
            ):
                aborted = doc["error_category"]
                break

        summary = self._summarize(results, evaluators, len(rows))
        failed = summary["failed"]
        status = ("aborted" if aborted else "completed" if failed == 0
                  else "failed" if summary["succeeded"] == 0 else "partial")
        self._exps.update(exp["id"], {
            "status": status, "summary": summary, "abort_reason": aborted,
            "finished_at": datetime.now(UTC),
        })
        return self._exps.get(exp["id"])

    def _run_row(self, exp, pv, row, evaluators, ref_field, project_id) -> dict:
        data = row["data"]
        doc = {"experiment_id": exp["id"], "row_index": row["index"], "split": row["split"],
               "input": data, "output": None, "status": "error", "error_category": None,
               "error_message": None, "latency_ms": None, "input_tokens": None,
               "output_tokens": None, "total_tokens": None, "request_id": None, "evaluations": []}
        try:
            req = GenerateRequest(
                prompt=render(pv["template"], data), system_instruction=pv["system_instruction"],
                provider=pv["provider"], model=pv["model"], temperature=pv["temperature"],
                max_output_tokens=pv["max_output_tokens"], project_id=project_id,
            )
            extra = {"experiment_id": exp["id"], "prompt_id": pv["prompt_id"],
                     "prompt_version": pv["version"]}
            resp = self._llm.generate(req, extra=extra)
        except ValidationError:
            doc.update(error_category="validation_error",
                       error_message="Rendered prompt is invalid (for example too long).")
            return doc
        except AppError as exc:
            doc.update(error_category=exc.category, error_message=exc.message)
            return doc
        doc.update(
            status="success", output=resp.text, latency_ms=resp.latency_ms,
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            total_tokens=resp.usage.total_tokens, request_id=resp.request_id,
        )
        reference = str(data[ref_field]) if ref_field and data.get(ref_field) is not None else None
        judge = self._judge_fn(pv, exp["id"], project_id)
        for cfg in evaluators:
            ev = EVALUATORS[cfg["type"]]
            try:
                res = ev.evaluate(EvalContext(resp.text, data, reference, cfg["params"], judge))
            except Exception as err:  # noqa: BLE001 - one broken evaluator must not stop the run
                res = EvalResult(None, None, f"evaluator error ({type(err).__name__})")
            doc["evaluations"].append({
                "name": cfg["name"], "type": cfg["type"], "kind": ev.kind,
                "score": res.score, "passed": res.passed, "detail": res.detail,
            })
        # Scores are also written onto the request trace so monitoring can chart quality.
        self._llm.attach_evaluations(resp.request_id, [
            {k: e[k] for k in ("name", "type", "kind", "score", "passed")}
            for e in doc["evaluations"]
        ])
        return doc

    def _judge_fn(self, pv, exp_id, project_id):
        def judge(prompt: str) -> str:
            req = GenerateRequest(
                prompt=prompt, provider=pv["provider"], model=pv["model"], temperature=0.0,
                max_output_tokens=300, project_id=project_id,
            )
            return self._llm.generate(
                req, extra={"experiment_id": exp_id, "purpose": "llm_judge"}
            ).text
        return judge

    @staticmethod
    def _summarize(results: list[dict], evaluators: list[dict], planned: int) -> dict:
        ok = [r for r in results if r["status"] == "success"]
        lat = [r["latency_ms"] for r in ok if r["latency_ms"] is not None]
        metrics = {}
        for cfg in evaluators:
            ev = EVALUATORS[cfg["type"]]
            evals = [e for r in ok for e in r["evaluations"] if e["name"] == cfg["name"]]
            scores = [e["score"] for e in evals if e["score"] is not None]
            judged = [e["passed"] for e in evals if e["passed"] is not None]
            metrics[cfg["name"]] = {
                "type": cfg["type"], "kind": ev.kind, "n_scored": len(scores),
                "n_unscored": len(evals) - len(scores),
                "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
                "pass_rate": round(sum(judged) / len(judged), 4) if judged else None,
            }
        return {
            "rows_planned": planned, "rows_run": len(results), "succeeded": len(ok),
            "failed": len(results) - len(ok),
            "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else None,
            "total_tokens": sum(r["total_tokens"] or 0 for r in ok), "metrics": metrics,
        }

    # ---------- read ----------
    def get(self, exp_id: str) -> dict:
        return self._exps.get(exp_id)

    def list(self, project_id: str | None, skip: int, limit: int) -> dict:
        items, total = self._exps.list(project_id, skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def results(self, exp_id: str, skip: int, limit: int) -> dict:
        self._exps.get(exp_id)
        items, total = self._exps.list_results(exp_id, skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def compare(self, ids: list[str], max_rows: int = 100) -> dict:
        ids = list(dict.fromkeys(ids))
        if not 2 <= len(ids) <= 4:
            raise ValidationAppError("Choose between 2 and 4 experiments to compare.")
        exps = []
        for i in ids:
            try:
                exps.append(self._exps.get(i))
            except NotFoundError:
                raise NotFoundError(f"Experiment {i} not found") from None
        aligned = len({(e["dataset_version_id"], e["split"]) for e in exps}) == 1
        differences = {
            k: [e["config"][k] for e in exps]
            for k in _SNAPSHOT if len({str(e["config"][k]) for e in exps}) > 1
        }
        rows: dict[int, dict] = {}
        if aligned:
            for e in exps:
                items, _ = self._exps.list_results(e["id"], 0, max_rows)
                for r in items:
                    slot = rows.setdefault(r["row_index"], {"row_index": r["row_index"],
                                                            "input": r["input"], "outputs": {}})
                    slot["outputs"][e["id"]] = {
                        "output": r["output"], "status": r["status"],
                        "error_category": r["error_category"], "evaluations": r["evaluations"],
                        "latency_ms": r["latency_ms"],
                    }
        return {
            "experiments": exps, "aligned": aligned, "config_differences": differences,
            "rows": [rows[k] for k in sorted(rows)],
        }


class Counter_like:  # tiny counter so evaluator names stay unique
    def __init__(self):
        self._n: dict[str, int] = {}

    def bump(self, key: str) -> int:
        self._n[key] = self._n.get(key, 0) + 1
        return self._n[key]
