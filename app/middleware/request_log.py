import time
import uuid

from fastapi import Request

from app.core.logger import access_logger, error_logger
from app.core.request_context import request_id_ctx


async def request_log_middleware(
    request: Request,
    call_next,
):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

    # 保存到ContextVar
    token = request_id_ctx.set(request_id)

    start_time = time.perf_counter()

    client_ip = request.client.host if request.client else "unknown"

    try:
        response = await call_next(request)

        elapsed = time.perf_counter() - start_time

        access_logger.info(
            f"{client_ip} "
            f"{request.method} "
            f"{request.url.path} "
            f"query={request.query_params} "
            f"status={response.status_code} "
            f"cost={elapsed:.3f}s"
        )

        response.headers["X-Request-Id"] = request_id

        return response

    except Exception:

        elapsed = time.perf_counter() - start_time

        error_logger.exception(
            f"{request.method} "
            f"{request.url.path} "
            f"cost={elapsed:.3f}s"
        )

        raise

    finally:
        # 防止上下文泄漏
        request_id_ctx.reset(token)
