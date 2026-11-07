"""Central execution pipeline: every model call goes through here.

Order of work: resolve provider -> validate parameters -> time the call -> build telemetry ->
persist it. A failed provider call and a failed telemetry write are handled separately.
The caller's API key is held only in memory for this call; it is never logged or stored.
"""
import logging
import time
import uuid
from datetime import UTC, datetime

from app.core.errors import NotFoundError, ProviderError
from app.core.redaction import redact
from app.repositories.project_repository import ProjectRepository
from app.repositories.request_repository import RequestRepository
from app.schemas.llm import GenerateRequest, GenerateResponse, Usage
from app.services.model_catalog import default_model, validate_generation
from app.services.providers.base import GenerationParams, LLMProvider
from app.services.providers.registry import ProviderRegistry

log = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        registry: ProviderRegistry,
        api_key: str | None,
        requests: RequestRepository,
        projects: ProjectRepository,
        store_prompt_text: bool = False,
        redaction_enabled: bool = True,
    ):
        self._registry = registry
        self._api_key = api_key
        self._requests = requests
        self._projects = projects
        self._store_text = store_prompt_text
        self._redact = redaction_enabled

    def resolve_provider(self, name: str | None) -> LLMProvider:
        return self._registry.get(name, self._api_key)

    def generate(self, req: GenerateRequest, extra: dict | None = None) -> GenerateResponse:
        provider = self.resolve_provider(req.provider)
        if req.project_id and not self._projects.exists(req.project_id):
            raise NotFoundError("Project not found")

        model = req.model or provider.default_model or default_model(provider.name)
        validate_generation(provider.name, model, req.temperature, req.max_output_tokens)
        params = GenerationParams(
            prompt=req.prompt,
            model=model,
            system_instruction=req.system_instruction,
            temperature=req.temperature,
            max_output_tokens=req.max_output_tokens,
        )

        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        result = None
        failure: ProviderError | None = None
        try:
            result = provider.generate(params)
        except ProviderError as exc:
            failure = exc
        latency_ms = round((time.perf_counter() - started) * 1000, 1)

        record = {
            "request_id": request_id,
            "created_at": datetime.now(UTC),
            "project_id": req.project_id,
            "provider": provider.name,
            "model": model,
            "status": "success" if failure is None else "error",
            "error_category": failure.category if failure else None,
            "latency_ms": latency_ms,
            "input_tokens": result.input_tokens if result else None,
            "output_tokens": result.output_tokens if result else None,
            "total_tokens": result.total_tokens if result else None,
            "prompt_chars": len(req.prompt),
            "response_chars": len(result.text) if result else None,
            "temperature": req.temperature,
            "max_output_tokens": req.max_output_tokens,
            # Fields reserved for later phases are recorded honestly as "not applicable yet".
            "retry_count": 0,  # automatic retries are not implemented
            "deployment_id": None,
            "prompt_id": None,
            "prompt_version": None,
            "evaluations": [],
        }
        if extra:
            record.update(extra)
        if self._store_text:
            record["prompt_text"] = redact(req.prompt, self._redact)
            record["response_text"] = redact(result.text, self._redact) if result else None

        telemetry_ok = self._save_telemetry(record)

        if failure is not None:
            failure.request_id = request_id  # lets callers quote an ID without seeing internals
            raise failure

        return GenerateResponse(
            request_id=request_id,
            text=result.text,
            provider=provider.name,
            model=model,
            latency_ms=latency_ms,
            usage=Usage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
            ),
            telemetry_recorded=telemetry_ok,
        )

    def _save_telemetry(self, record: dict) -> bool:
        """A telemetry failure must never turn a good answer into an error."""
        try:
            self._requests.insert(record)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error(
                "telemetry write failed",
                extra={
                    "ctx": {
                        "request_id": record["request_id"],
                        "error_type": type(exc).__name__,
                    }
                },
            )
            return False

    def attach_evaluations(self, request_id: str, evaluations: list[dict]) -> None:
        """Link evaluation scores to the trace. Best effort: never breaks the experiment."""
        try:
            self._requests.set_evaluations(request_id, evaluations)
        except Exception as exc:  # noqa: BLE001
            log.error("attaching evaluations failed", extra={"ctx": {"error_type": type(exc).__name__}})
