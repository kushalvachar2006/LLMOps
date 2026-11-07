from fastapi import APIRouter, Request

from app.services.model_catalog import PROVIDER_LABELS, models_for

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
def list_models(request: Request) -> dict:
    registry = request.app.state.registry
    out = []
    for pid, label in PROVIDER_LABELS.items():
        if pid == "mock" and not registry.mock_enabled():
            continue
        out.append({
            "id": pid,
            "label": label,
            "server_key_configured": registry.has_server_key(pid),
            "models": [
                {
                    "id": m.id,
                    "label": m.label,
                    "supports_temperature": m.supports_temperature,
                    "temp_max": m.temp_max,
                    "max_output_tokens": m.max_output_tokens,
                    "note": m.note,
                }
                for m in models_for(pid)
            ],
        })
    return {"default_provider": registry.default_provider, "providers": out}
