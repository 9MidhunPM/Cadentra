import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.core.client_ip import resolve_client_ip
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_session

logger = logging.getLogger(__name__)
EXPECTED_SCHEMA_REVISION = "0003"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        from app.modules.identity.dev_tools import reconcile_configuration
        reconcile_configuration()
        yield

    app = FastAPI(title="Cadentra API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_identifier(request: Request, call_next):
        from app.modules.identity.dev_audit import prepare_attempt, record_outcome

        request.state.request_id = str(uuid4())
        attempt = None
        try:
            request.state.client_ip = resolve_client_ip(request, get_settings())
            attempt = prepare_attempt(request)
            response = await call_next(request)
        except DomainError as error:
            response = error_response(request, error.code, error.message, error.status_code)
            record_outcome(attempt, error.status_code)
        except Exception as error:
            record_outcome(attempt, 500, type(error).__name__)
            raise
        else:
            record_outcome(attempt, response.status_code)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def error_response(request, code, message, status, fields=None):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "fields": fields or {},
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return error_response(request, exc.code, exc.message, exc.status_code, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Do not reflect submitted input, especially passwords/tokens, into errors.
        fields = {".".join(map(str, item["loc"])): item["msg"] for item in exc.errors()}
        return error_response(
            request, "VALIDATION_ERROR", "Check the submitted fields.", 422, fields
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(
            request,
            "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
            str(exc.detail),
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error(
            "Unhandled request failure %s request_id=%s",
            type(exc).__name__,
            getattr(request.state, "request_id", "unknown"),
        )
        return error_response(request, "INTERNAL_ERROR", "The request could not be completed.", 500)

    @app.api_route("/api/v1/health", methods=["GET", "HEAD"])
    def health(db: Annotated[Session, Depends(get_session)]):
        try:
            db.execute(text("SELECT 1"))
            revisions = db.scalars(text("SELECT version_num FROM alembic_version")).all()
            if revisions != [EXPECTED_SCHEMA_REVISION]:
                raise DomainError("NOT_READY", "Database migration is required.", 503)
        except SQLAlchemyError as exc:
            raise DomainError(
                "NOT_READY", "Database is unavailable or requires migration.", 503
            ) from exc
        return {"data": {"status": "ready", "migration": EXPECTED_SCHEMA_REVISION}}

    from app.modules.billing.router import router as billing_router
    from app.modules.catalog.router import router as catalog_router
    from app.modules.identity.dev_tools import router as dev_tools_router
    from app.modules.identity.router import router as identity_router
    from app.modules.reporting.router import router as reporting_router
    from app.modules.subscriptions.router import router as subscriptions_router

    for router in (
        identity_router,
        dev_tools_router,
        catalog_router,
        subscriptions_router,
        billing_router,
        reporting_router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
