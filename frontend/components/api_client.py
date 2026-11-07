"""Thin HTTP client for the backend. The frontend NEVER talks to Gemini or MongoDB."""
import os

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
# If the backend sets ADMIN_TOKEN, the same value must be provided here.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
CONNECT_TIMEOUT = 3
READ_TIMEOUT = 60  # model calls can take a while


class ApiError(Exception):
    """Friendly message plus the backend's error category."""

    def __init__(self, message: str, category: str = "error", status: int | None = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.status = status


def _call(method: str, path: str, api_key: str | None = None, **kwargs):
    # Secrets travel in headers, never in the URL or body.
    headers = dict(kwargs.pop("headers", None) or {})
    if api_key:
        headers["X-Provider-Api-Key"] = api_key
    if ADMIN_TOKEN:
        headers["X-Admin-Token"] = ADMIN_TOKEN
    if headers:
        kwargs["headers"] = headers
    try:
        resp = requests.request(
            method, f"{API_URL}{path}", timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), **kwargs
        )
    except requests.ConnectionError:
        raise ApiError(
            f"Cannot reach the API at {API_URL}. Is the backend running?", "unreachable"
        ) from None
    except requests.Timeout:
        raise ApiError("The API took too long to respond.", "timeout") from None

    if resp.status_code == 204:
        return None
    try:
        body = resp.json()
    except ValueError:
        raise ApiError(f"Unexpected API response (HTTP {resp.status_code}).") from None
    if resp.status_code >= 400:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise ApiError(
            err.get("message", f"Request failed (HTTP {resp.status_code})."),
            err.get("category", "error"),
            resp.status_code,
        )
    return body


def health() -> dict:
    return _call("GET", "/health")


def list_projects(skip: int = 0, limit: int = 100) -> dict:
    return _call("GET", "/api/projects", params={"skip": skip, "limit": limit})


def create_project(name: str, description: str) -> dict:
    return _call("POST", "/api/projects", json={"name": name, "description": description})


def update_project(project_id: str, **changes) -> dict:
    return _call("PATCH", f"/api/projects/{project_id}", json=changes)


def delete_project(project_id: str) -> None:
    _call("DELETE", f"/api/projects/{project_id}")


def generate(payload: dict, api_key: str | None = None) -> dict:
    return _call("POST", "/api/generate", api_key=api_key, json=payload)


def list_models() -> dict:
    return _call("GET", "/api/models")


def create_prompt(payload: dict) -> dict:
    return _call("POST", "/api/prompts", json=payload)


def list_prompts(project_id: str | None = None) -> dict:
    return _call("GET", "/api/prompts", params={"project_id": project_id, "limit": 100})


def add_prompt_version(prompt_id: str, payload: dict) -> dict:
    return _call("POST", f"/api/prompts/{prompt_id}/versions", json=payload)


def list_prompt_versions(prompt_id: str) -> list:
    return _call("GET", f"/api/prompts/{prompt_id}/versions")


def compare_prompt_versions(prompt_id: str, a: int, b: int) -> dict:
    return _call("GET", f"/api/prompts/{prompt_id}/compare", params={"a": a, "b": b})


def restore_prompt_version(prompt_id: str, version: int) -> dict:
    return _call("POST", f"/api/prompts/{prompt_id}/versions/{version}/restore")


def create_dataset(payload: dict) -> dict:
    return _call("POST", "/api/datasets", json=payload)


def add_dataset_version(dataset_id: str, payload: dict) -> dict:
    return _call("POST", f"/api/datasets/{dataset_id}/versions", json=payload)


def list_datasets(project_id: str | None = None) -> dict:
    return _call("GET", "/api/datasets", params={"project_id": project_id, "limit": 100})


def list_dataset_versions(dataset_id: str) -> list:
    return _call("GET", f"/api/datasets/{dataset_id}/versions")


def dataset_rows(dataset_id: str, version: int, split: str | None = None, limit: int = 20) -> dict:
    params = {"limit": limit, "split": split if split and split != "all" else None}
    return _call("GET", f"/api/datasets/{dataset_id}/versions/{version}/rows", params=params)


def list_evaluators() -> list:
    return _call("GET", "/api/evaluators")


def run_experiment(payload: dict, api_key: str | None = None) -> dict:
    return _call("POST", "/api/experiments", api_key=api_key, json=payload)


def list_experiments(project_id: str | None = None) -> dict:
    return _call("GET", "/api/experiments", params={"project_id": project_id, "limit": 100})


def get_experiment(experiment_id: str) -> dict:
    return _call("GET", f"/api/experiments/{experiment_id}")


def experiment_results(experiment_id: str, limit: int = 100) -> dict:
    return _call("GET", f"/api/experiments/{experiment_id}/results", params={"limit": limit})


def compare_experiments(ids: list[str]) -> dict:
    return _call("GET", "/api/experiments/compare", params={"ids": ",".join(ids)})


def _filters(project_id=None, start=None, end=None, provider=None, model=None) -> dict:
    return {"project_id": project_id, "start": start, "end": end, "provider": provider,
            "model": model}


def monitoring_summary(**f) -> dict:
    return _call("GET", "/api/monitoring/summary", params=_filters(**f))


def monitoring_timeseries(granularity=None, **f) -> dict:
    return _call("GET", "/api/monitoring/timeseries",
                 params={**_filters(**f), "granularity": granularity})


def monitoring_breakdown(**f) -> dict:
    return _call("GET", "/api/monitoring/breakdown", params=_filters(**f))


def monitoring_quality(granularity=None, **f) -> dict:
    return _call("GET", "/api/monitoring/quality",
                 params={**_filters(**f), "granularity": granularity})


def monitoring_alerts(**f) -> dict:
    return _call("GET", "/api/monitoring/alerts", params=_filters(**f))


def get_thresholds() -> dict:
    return _call("GET", "/api/monitoring/thresholds")


def save_thresholds(payload: dict) -> dict:
    return _call("PUT", "/api/monitoring/thresholds", json=payload)


def monitoring_policy() -> dict:
    return _call("GET", "/api/monitoring/policy")


def list_pricing() -> list:
    return _call("GET", "/api/pricing")


def add_pricing(payload: dict) -> dict:
    return _call("POST", "/api/pricing", json=payload)


def delete_pricing(pricing_id: str) -> None:
    _call("DELETE", f"/api/pricing/{pricing_id}")


def add_feedback(payload: dict) -> dict:
    return _call("POST", "/api/feedback", json=payload)


def list_feedback(limit: int = 20, **f) -> list:
    return _call("GET", "/api/feedback", params={**_filters(**f), "limit": limit})


def list_requests(skip: int = 0, limit: int = 50, project_id: str | None = None) -> dict:
    params = {"skip": skip, "limit": limit}
    if project_id:
        params["project_id"] = project_id
    return _call("GET", "/api/requests", params=params)


# ---------------- Phase 4: deployments and API keys ----------------
def list_deployments(project_id: str | None = None) -> list:
    return _call("GET", "/api/deployments", params={"project_id": project_id})


def create_deployment(project_id: str, name: str, description: str) -> dict:
    return _call("POST", "/api/deployments",
                 json={"project_id": project_id, "name": name, "description": description})


def list_deployment_versions(deployment_id: str) -> list:
    return _call("GET", f"/api/deployments/{deployment_id}/versions")


def publish_version(deployment_id: str, payload: dict, api_key: str | None = None) -> dict:
    return _call("POST", f"/api/deployments/{deployment_id}/versions", api_key=api_key, json=payload)


def deployment_health_check(deployment_id: str, version: int, api_key: str | None = None) -> dict:
    return _call("POST", f"/api/deployments/{deployment_id}/versions/{version}/health-check",
                 api_key=api_key)


def promote_version(deployment_id: str, version: int, environment: str) -> dict:
    return _call("POST", f"/api/deployments/{deployment_id}/promote",
                 json={"version": version, "environment": environment})


def unpublish_environment(deployment_id: str, environment: str) -> dict:
    return _call("DELETE", f"/api/deployments/{deployment_id}/environments/{environment}")


def deployment_events(deployment_id: str) -> list:
    return _call("GET", f"/api/deployments/{deployment_id}/events")


def deployment_usage(deployment_id: str) -> dict:
    return _call("GET", f"/api/deployments/{deployment_id}/usage")


def create_api_key(payload: dict) -> dict:
    return _call("POST", "/api/api-keys", json=payload)


def list_api_keys(project_id: str | None = None) -> list:
    return _call("GET", "/api/api-keys", params={"project_id": project_id})


def revoke_api_key(key_row_id: str) -> dict:
    return _call("POST", f"/api/api-keys/{key_row_id}/revoke")


def invoke_deployment(deployment_id: str, inputs: dict, environment: str, token: str) -> dict:
    """Calls the PUBLIC endpoint exactly as an outside application would."""
    try:
        resp = requests.post(
            f"{API_URL}/v1/deployments/{deployment_id}/invoke",
            json={"inputs": inputs, "environment": environment},
            headers={"Authorization": f"Bearer {token}"},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.ConnectionError:
        raise ApiError(f"Cannot reach the API at {API_URL}.", "unreachable") from None
    except requests.Timeout:
        raise ApiError("The API took too long to respond.", "timeout") from None
    try:
        body = resp.json()
    except ValueError:
        raise ApiError(f"Unexpected API response (HTTP {resp.status_code}).") from None
    if resp.status_code >= 400:
        err = body.get("error", {})
        message = err.get("message", f"Request failed (HTTP {resp.status_code}).")
        if resp.headers.get("Retry-After"):
            message += f" Retry after {resp.headers['Retry-After']} seconds."
        raise ApiError(message, err.get("category", "error"), resp.status_code)
    return body
