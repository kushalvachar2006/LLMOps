"""The public inference path: authenticate -> rate limit -> validate -> run -> track.

Anything returned to API callers is deliberately generic. Provider details, prompts, model
settings and other projects' data never appear in a response.
"""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import (
    ForbiddenError,
    MissingApiKeyError,
    NotFoundError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    RateLimitedError,
    ServiceUnavailableError,
    UnauthorizedError,
    UpstreamError,
    ValidationAppError,
)
from app.core.security import hash_secret, parse_token, verify_secret
from app.repositories.deployments import ApiKeyRepository, DeploymentRepository, RateLimitRepository
from app.schemas.deployment import ENVIRONMENTS, InvokeRequest
from app.schemas.llm import GenerateRequest
from app.services.llm_service import LLMService
from app.services.template import render

log = logging.getLogger(__name__)
_BAD_KEY = "Invalid or missing API key."
_DUMMY_HASH = hash_secret("x" * 43, "dummy")


def _safe_provider_error(exc: ProviderError) -> UpstreamError | ServiceUnavailableError:
    rid = getattr(exc, "request_id", None)
    if isinstance(exc, ProviderTimeoutError):
        return UpstreamError("The model service timed out. Please retry.", rid, 504, "upstream_timeout")
    if isinstance(exc, (ProviderRateLimitError, ProviderAuthError)):
        err = ServiceUnavailableError("The service is temporarily unavailable. Please retry shortly.")
        err.request_id = rid
        return err
    return UpstreamError("The model service could not process this request.", rid)


class InvokeService:
    def __init__(self, keys: ApiKeyRepository, limits: RateLimitRepository,
                 deployments: DeploymentRepository, llm: LLMService, settings: Settings,
                 clock=time.time):
        self._keys = keys
        self._limits = limits
        self._deps = deployments
        self._llm = llm
        self._settings = settings
        self._clock = clock

    # ----- 1. who is calling?
    def authenticate(self, token: str | None) -> dict:
        parsed = parse_token(token)
        row = self._keys.get_for_auth(parsed[0]) if parsed else None
        stored = row["hash"] if row else _DUMMY_HASH
        secret = parsed[1] if parsed else "x" * 43
        ok = verify_secret(secret, self._settings.pepper if row else "dummy", stored)
        if not (parsed and row and ok) or row.get("revoked_at") is not None:
            raise UnauthorizedError(_BAD_KEY)  # same answer for unknown, wrong and revoked keys
        return row

    # ----- 2. are they within their limit?
    def _rate_limit(self, key: dict) -> None:
        now = self._clock()
        window = int(now // 60)
        expires = datetime.fromtimestamp((window + 2) * 60, UTC)
        count = self._limits.hit(key["key_id"], window, expires)
        limit = key.get("rate_limit_per_minute") or self._settings.default_rate_limit_per_minute
        if count > limit:
            raise RateLimitedError("Rate limit exceeded. Please slow down.",
                                   max(1, math.ceil((window + 1) * 60 - now)))

    @staticmethod
    def _parse(raw: bytes) -> InvokeRequest:
        try:
            return InvokeRequest.model_validate(json.loads(raw or b"{}"))
        except ValidationError as exc:
            fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
            raise ValidationAppError(
                "Invalid request. Check these field(s): " + (", ".join(fields) or "body") + "."
            ) from None
        except ValueError:
            raise ValidationAppError("The request body must be valid JSON.") from None

    # ----- 3. run
    def invoke(self, token: str | None, deployment_id: str, raw_body: bytes) -> dict:
        key = self.authenticate(token)
        self._rate_limit(key)
        body = self._parse(raw_body)
        if body.environment not in ENVIRONMENTS:
            raise ValidationAppError(f"environment must be one of {', '.join(ENVIRONMENTS)}.")

        try:
            dep = self._deps.get(deployment_id)
        except NotFoundError:
            dep = None
        # A key from another project gets the same answer as a missing deployment.
        if dep is None or dep["project_id"] != key["project_id"]:
            raise NotFoundError("Deployment not found.")
        if body.environment not in key["environments"]:
            raise ForbiddenError("This API key is not allowed to use that environment.")
        number = dep["environments"].get(body.environment)
        if number is None:
            raise NotFoundError("No version is live in this environment.")
        ver = self._deps.get_version(dep["id"], number)

        variables = ver["variables"]
        missing = [v for v in variables if v not in body.inputs]
        extra = [k for k in body.inputs if k not in variables]
        if missing:
            raise ValidationAppError(f"Missing input(s): {', '.join(missing)}.")
        if extra:
            raise ValidationAppError(f"Unknown input(s): {', '.join(extra)}.")
        limit = self._settings.max_input_chars
        values = {k: str(v) for k, v in body.inputs.items()}
        if any(len(v) > limit for v in values.values()):
            raise ValidationAppError(f"Each input is limited to {limit:,} characters.")

        cfg = ver["config"]
        try:
            req = GenerateRequest(
                prompt=render(cfg["template"], values), system_instruction=cfg["system_instruction"],
                provider=cfg["provider"], model=cfg["model"], temperature=cfg["temperature"],
                max_output_tokens=cfg["max_output_tokens"], project_id=dep["project_id"],
            )
        except ValidationError:
            raise ValidationAppError("The inputs make the prompt too long.") from None

        self._touch(key)
        try:
            resp = self._llm.generate(req, extra={
                "deployment_id": dep["id"], "deployment_version": number,
                "environment": body.environment, "api_key_id": key["id"],
                "prompt_id": ver["prompt_id"], "prompt_version": ver["prompt_version"],
            })
        except ProviderError as exc:
            raise _safe_provider_error(exc) from None
        except (MissingApiKeyError, ValidationAppError) as exc:
            # A server-side configuration problem: log it, tell the caller nothing specific.
            log.error("deployment misconfigured", extra={"ctx": {
                "deployment_id": dep["id"], "category": exc.category}})
            raise ServiceUnavailableError(
                "The service is temporarily unavailable. Please retry shortly.") from None
        return {
            "request_id": resp.request_id, "deployment_id": dep["id"], "version": number,
            "environment": body.environment, "output": resp.text,
            "usage": resp.usage.model_dump(), "latency_ms": resp.latency_ms,
        }

    def _touch(self, key: dict) -> None:
        try:
            self._keys.touch(key["id"])
        except Exception as exc:  # noqa: BLE001 - usage bookkeeping must not block a request
            log.error("api key usage update failed", extra={"ctx": {"error_type": type(exc).__name__}})


