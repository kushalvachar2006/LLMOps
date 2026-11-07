from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import build_invoke_service
from app.core.errors import PayloadTooLargeError

router = APIRouter(prefix="/v1", tags=["inference"])


async def read_limited_body(request: Request, limit: int) -> bytes:
    """Stop reading as soon as the limit is passed, so a huge body can't fill memory."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise PayloadTooLargeError(f"Request body is limited to {limit:,} bytes.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise PayloadTooLargeError(f"Request body is limited to {limit:,} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


def extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key")


@router.post("/deployments/{deployment_id}/invoke")
async def invoke(deployment_id: str, request: Request):
    """Call a live deployment.  Header:  Authorization: Bearer <api key>
    Body: {"inputs": {"field": "value"}, "environment": "production"}"""
    raw = await read_limited_body(request, request.app.state.settings.max_request_bytes)
    svc = build_invoke_service(request)
    result = await run_in_threadpool(svc.invoke, extract_token(request), deployment_id, raw)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
