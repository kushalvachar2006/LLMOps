"""Index definitions, created idempotently at startup."""
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure

PROJECTS = "projects"
REQUESTS = "requests"


def ensure_indexes(db: Database) -> None:
    db[PROJECTS].create_index([("id", ASCENDING)], unique=True, name="uniq_project_id")
    db[PROJECTS].create_index([("name_lower", ASCENDING)], unique=True, name="uniq_project_name")
    db[PROJECTS].create_index([("created_at", DESCENDING)], name="projects_created_at")
    db[REQUESTS].create_index([("request_id", ASCENDING)], unique=True, name="uniq_request_id")
    db[REQUESTS].create_index([("created_at", DESCENDING)], name="requests_created_at")
    db[REQUESTS].create_index(
        [("project_id", ASCENDING), ("created_at", DESCENDING)], name="requests_project_time"
    )


def ensure_workspace_indexes(db: Database) -> None:
    """Indexes for Phase 2 collections (prompts, datasets, experiments)."""
    A, D = ASCENDING, DESCENDING
    db["prompts"].create_index([("id", A)], unique=True, name="uniq_prompt_id")
    db["prompts"].create_index(
        [("project_id", A), ("name_lower", A)], unique=True, name="uniq_prompt_name"
    )
    db["prompt_versions"].create_index([("id", A)], unique=True, name="uniq_pv_id")
    db["prompt_versions"].create_index(
        [("prompt_id", A), ("version", A)], unique=True, name="uniq_prompt_version"
    )
    db["datasets"].create_index([("id", A)], unique=True, name="uniq_dataset_id")
    db["datasets"].create_index(
        [("project_id", A), ("name_lower", A)], unique=True, name="uniq_dataset_name"
    )
    db["dataset_versions"].create_index([("id", A)], unique=True, name="uniq_dv_id")
    db["dataset_versions"].create_index(
        [("dataset_id", A), ("version", A)], unique=True, name="uniq_dataset_version"
    )
    db["dataset_rows"].create_index(
        [("dataset_version_id", A), ("index", A)], unique=True, name="uniq_dataset_row"
    )
    db["experiments"].create_index([("id", A)], unique=True, name="uniq_experiment_id")
    db["experiments"].create_index([("project_id", A), ("created_at", D)], name="exp_project_time")
    db["experiments"].create_index([("prompt_id", A), ("prompt_version", A)], name="exp_prompt")
    db["experiment_results"].create_index(
        [("experiment_id", A), ("row_index", A)], unique=True, name="uniq_exp_row"
    )


def _ttl_index(db: Database, collection: str, retention_days: int) -> None:
    """Create or adjust a TTL index so MongoDB deletes old records itself."""
    name = f"{collection}_ttl"
    seconds = retention_days * 86400
    col = db[collection]
    existing = {i["name"]: i for i in col.list_indexes()}
    if retention_days <= 0:
        if name in existing:
            col.drop_index(name)
        return
    if name in existing and existing[name].get("expireAfterSeconds") == seconds:
        return
    if name in existing:
        col.drop_index(name)
    col.create_index([("created_at", ASCENDING)], expireAfterSeconds=seconds, name=name)


def ensure_monitoring_indexes(db: Database, retention_days: int = 0) -> None:
    """Indexes for Phase 3: fast filtered aggregations, pricing, feedback, retention."""
    A, D = ASCENDING, DESCENDING
    db[REQUESTS].create_index(
        [("provider", A), ("model", A), ("created_at", D)], name="requests_model_time"
    )
    db[REQUESTS].create_index(
        [("prompt_id", A), ("prompt_version", A), ("created_at", D)], name="requests_prompt_time"
    )
    db["feedback"].create_index([("request_id", A)], unique=True, name="uniq_feedback_request")
    db["feedback"].create_index([("project_id", A), ("created_at", D)], name="feedback_project_time")
    db["pricing"].create_index(
        [("provider", A), ("model", A), ("effective_from", A)], unique=True, name="uniq_pricing"
    )
    db["monitoring_settings"].create_index([("scope", A)], unique=True, name="uniq_settings_scope")
    try:
        _ttl_index(db, REQUESTS, retention_days)
        _ttl_index(db, "feedback", retention_days)
    except OperationFailure:
        raise


def ensure_deployment_indexes(db: Database) -> None:
    A, D = ASCENDING, DESCENDING
    db["deployments"].create_index([("id", A)], unique=True, name="uniq_deployment_id")
    db["deployments"].create_index(
        [("project_id", A), ("name_lower", A)], unique=True, name="uniq_deployment_name"
    )
    db["deployment_versions"].create_index(
        [("deployment_id", A), ("version", A)], unique=True, name="uniq_deployment_version"
    )
    db["deployment_events"].create_index([("deployment_id", A), ("at", D)], name="events_by_deployment")
    db["api_keys"].create_index([("id", A)], unique=True, name="uniq_apikey_id")
    db["api_keys"].create_index([("key_id", A)], unique=True, name="uniq_apikey_keyid")
    db["api_keys"].create_index([("project_id", A), ("created_at", D)], name="apikeys_project")
    db["rate_limits"].create_index([("key", A)], unique=True, name="uniq_rate_key")
    # MongoDB removes expired counters on its own (checked about once a minute).
    db["rate_limits"].create_index([("expires_at", A)], expireAfterSeconds=0, name="rate_ttl")
    db[REQUESTS].create_index([("deployment_id", A), ("created_at", D)], name="requests_deployment")
