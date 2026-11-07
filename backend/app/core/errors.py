"""Clear error categories shared by services and API handlers."""


class AppError(Exception):
    status_code = 500
    category = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    category = "not_found"


class ConflictError(AppError):
    status_code = 409
    category = "conflict"


class DatabaseUnavailableError(AppError):
    status_code = 503
    category = "database_unavailable"


class ProviderError(AppError):
    """Base class for LLM provider failures. Messages must never contain secrets."""

    status_code = 502
    category = "provider_error"


class ProviderRateLimitError(ProviderError):
    status_code = 429
    category = "rate_limited"


class ProviderTimeoutError(ProviderError):
    status_code = 504
    category = "provider_timeout"


class ProviderAuthError(ProviderError):
    status_code = 502
    category = "provider_auth"


class ProviderBadRequestError(ProviderError):
    status_code = 400
    category = "provider_bad_request"


class ValidationAppError(AppError):
    status_code = 422
    category = "validation_error"


class MissingApiKeyError(AppError):
    status_code = 400
    category = "missing_api_key"


class PayloadTooLargeError(AppError):
    status_code = 413
    category = "payload_too_large"


class UnauthorizedError(AppError):
    status_code = 401
    category = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    category = "forbidden"


class RateLimitedError(AppError):
    status_code = 429
    category = "rate_limited"

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class ServiceUnavailableError(AppError):
    status_code = 503
    category = "service_unavailable"


class UpstreamError(AppError):
    """Safe, generic failure shown to API callers. `request_id` lets support find the trace."""

    status_code = 502
    category = "upstream_error"

    def __init__(self, message: str, request_id: str | None = None, status_code: int = 502,
                 category: str = "upstream_error"):
        super().__init__(message)
        self.request_id = request_id
        self.status_code = status_code
        self.category = category
