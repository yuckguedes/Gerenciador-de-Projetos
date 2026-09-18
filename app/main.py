import time
import uuid

import structlog
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies import get_db
from app.api.routes import auth, projects, tasks
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger("app")

app = FastAPI(title="Desafio API")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=getattr(request.state, "user_id", None),
        )
        return response


app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first_error.get("loc", []) if loc != "body")
    message = first_error.get("msg", "Dados inválidos")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": f"{field}: {message}" if field else message,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        content = {"detail": detail}
    else:
        content = {"detail": {"code": "HTTP_ERROR", "message": str(detail)}}

    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", method=request.method, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Erro interno do servidor",
            }
        },
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except SQLAlchemyError:
        database_status = "unreachable"

    if database_status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": database_status},
        )

    return {"status": "ok", "database": database_status}
