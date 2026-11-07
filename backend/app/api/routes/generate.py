from fastapi import APIRouter, Depends, Request

from app.api.deps import build_llm_service, get_api_key
from app.schemas.llm import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/api", tags=["llm"])


# A plain `def` route runs in FastAPI's threadpool, so the blocking SDK call
# does not freeze the event loop.
@router.post("/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest, request: Request, api_key: str | None = Depends(get_api_key)):
    return build_llm_service(request, api_key).generate(body)
