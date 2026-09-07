from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import error_logger
from app.shared.responses import failure_response


def register_exceptions(app: FastAPI):

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        # 记录日志
        error_logger.error(f"""
        METHOD={request.method}
        URL={request.url.path}
        STATUS={exc.status_code}
        MESSAGE={exc.detail}
        """)
        if exc.status_code == 404:
            return JSONResponse(
                failure_response(message=f"API is not found:{request.url.path}")
            )

        return JSONResponse(failure_response(message=exc.detail))

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        # 记录日志
        client_ip = request.client.host if request.client else "unknown"

        error_logger.exception(f"""
        URL={request.url.path}
        METHOD={request.method}
        IP={client_ip}
        QUERY={request.query_params}
        """)
        return JSONResponse(failure_response(message="Internal Server Error"))
