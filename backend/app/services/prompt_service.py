"""Prompt assets with immutable, numbered versions."""
from __future__ import annotations

import difflib

from app.core.errors import ValidationAppError
from app.repositories.assets import ExperimentRepository, PromptRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.prompt import PromptCreate, PromptVersionCreate, VersionFields
from app.services.model_catalog import providers, validate_generation
from app.services.template import extract_variables

CREATED_BY = "local-user"  # no accounts until Phase 4
_COMPARED = ["system_instruction", "template", "provider", "model", "temperature",
             "max_output_tokens"]


class PromptService:
    def __init__(self, prompts: PromptRepository, projects: ProjectRepository,
                 experiments: ExperimentRepository):
        self._prompts = prompts
        self._projects = projects
        self._experiments = experiments

    @staticmethod
    def _check(fields: VersionFields) -> None:
        if fields.provider not in providers():
            raise ValidationAppError(f"Unknown provider '{fields.provider}'.")
        validate_generation(
            fields.provider, fields.model, fields.temperature, fields.max_output_tokens
        )

    def _write_version(self, prompt: dict, f: VersionFields | dict, change: str | None) -> dict:
        data = f if isinstance(f, dict) else f.model_dump(exclude={"change_description"})
        number = self._prompts.next_version_number(prompt["id"])
        doc = {
            "prompt_id": prompt["id"], "project_id": prompt["project_id"], "version": number,
            **{k: data[k] for k in _COMPARED},
            "change_description": change, "created_by": CREATED_BY,
        }
        return self._decorate(self._prompts.insert_version(doc))

    @staticmethod
    def _decorate(version: dict) -> dict:
        return {**version, "variables": extract_variables(version["template"])}

    def create_prompt(self, data: PromptCreate) -> dict:
        self._projects.get(data.project_id)  # 404 if the project does not exist
        self._check(data)
        prompt = self._prompts.create(data.project_id, data.name, data.description)
        version = self._write_version(prompt, data, data.change_description or "Initial version")
        return {"prompt": self._prompts.get(prompt["id"]), "version": version}

    def add_version(self, prompt_id: str, data: PromptVersionCreate) -> dict:
        prompt = self._prompts.get(prompt_id)
        self._check(data)
        return self._write_version(prompt, data, data.change_description)

    def restore(self, prompt_id: str, version: int) -> dict:
        """Restoring never rewrites history: it appends a NEW version copied from the old one."""
        prompt = self._prompts.get(prompt_id)
        old = self._prompts.get_version(prompt_id, version)
        return self._write_version(prompt, old, f"Restored from version {version}")

    def get(self, prompt_id: str) -> dict:
        prompt = self._prompts.get(prompt_id)
        latest = None
        if prompt["latest_version"]:
            latest = self._decorate(self._prompts.get_version(prompt_id, prompt["latest_version"]))
        return {"prompt": prompt, "latest": latest}

    def list(self, project_id: str | None, skip: int, limit: int) -> dict:
        items, total = self._prompts.list(project_id, skip, limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def _with_evals(self, prompt_id: str, version: dict) -> dict:
        """Evaluation results are looked up from experiments, so versions stay immutable."""
        exps = self._experiments.for_prompt_version(prompt_id, version["version"])
        version["evaluation_results"] = [
            {"experiment_id": e["id"], "name": e["name"], "status": e["status"],
             "created_at": e["created_at"], "metrics": e.get("summary", {}).get("metrics", {})}
            for e in exps
        ]
        return version

    def list_versions(self, prompt_id: str) -> list[dict]:
        self._prompts.get(prompt_id)
        return [
            self._with_evals(prompt_id, self._decorate(v))
            for v in self._prompts.list_versions(prompt_id)
        ]

    def get_version(self, prompt_id: str, version: int) -> dict:
        self._prompts.get(prompt_id)
        return self._with_evals(
            prompt_id, self._decorate(self._prompts.get_version(prompt_id, version))
        )

    def compare(self, prompt_id: str, a: int, b: int) -> dict:
        self._prompts.get(prompt_id)
        va = self._decorate(self._prompts.get_version(prompt_id, a))
        vb = self._decorate(self._prompts.get_version(prompt_id, b))
        changes = {f: {"a": va[f], "b": vb[f], "changed": va[f] != vb[f]} for f in _COMPARED}
        diffs = {}
        for f in ("system_instruction", "template"):
            diffs[f] = list(difflib.unified_diff(
                (va[f] or "").splitlines(), (vb[f] or "").splitlines(),
                fromfile=f"v{a}", tofile=f"v{b}", lineterm="",
            ))
        return {"a": va, "b": vb, "changes": changes, "diffs": diffs}
