from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "x-request-id"
REQUEST_ID_PATTERN = re.compile(r"^req-[0-9a-f]{8}$")


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def resolve_correlation_id(incoming: str | None) -> str:
    # Chỉ tin header đúng format req-<8-hex>; giá trị lạ (có thể chứa PII hoặc
    # ký tự phá log) bị thay bằng ID mới thay vì ghi nguyên văn.
    if incoming and REQUEST_ID_PATTERN.fullmatch(incoming.strip().lower()):
        return incoming.strip().lower()
    return new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa context của request trước để không rò correlation_id/user context.
        clear_contextvars()

        correlation_id = resolve_correlation_id(request.headers.get(REQUEST_ID_HEADER))
        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = correlation_id
        response.headers["x-response-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
        return response
