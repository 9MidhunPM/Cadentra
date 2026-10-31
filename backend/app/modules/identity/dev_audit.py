"""Durable pre-dispatch attempts and append-only write outcomes for role tests.

The business transaction never depends on a post-commit audit acknowledgement.
An attempt without an outcome remains pending/unknown for operator inspection.
"""
import logging
from uuid import uuid4

from sqlalchemy import select

from app.core.auth import require_actor
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_token
from app.db import session as database
from app.models import AuditEvent, SessionRecord

logger = logging.getLogger(__name__)
RECOVERY_PATHS = frozenset({
    "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/signup",
    "/api/v1/auth/password-reset/request", "/api/v1/auth/password-reset/confirm",
})


def store_event(context, action, details, event_id):
    with database.SessionFactory() as db, db.begin():
        db.add(AuditEvent(id=event_id, actor_user_id=context["operator_id"],
            entity_type="DEV_ACCESS_GRANT", entity_id=context["grant_id"],
            action=action, redacted_details=details))


def prepare_attempt(request):
    if (request.method in {"GET", "HEAD", "OPTIONS"}
        or request.url.path in RECOVERY_PATHS
        or request.url.path.startswith("/api/v1/dev-tools/")):
        return None
    token = request.cookies.get(get_settings().session_cookie_name, "")
    if not token:
        return None
    with database.SessionFactory() as db:
        linked = db.scalar(select(SessionRecord.dev_grant_id).where(
            SessionRecord.token_hash == hash_token(token)))
        if linked is None:
            return None
        # Validates current authority, Origin and the normal business CSRF before
        # the attempt is stored or the business route may execute.
        require_actor(request, db)
    context = dict(request.state.dev_audit)
    context.update(attempt_id=uuid4(), request_id=request.state.request_id,
                   method=request.method, path=request.url.path)
    details = {"target_user_id": str(context["target_id"]),
               "request_id": context["request_id"], "method": context["method"],
               "path": context["path"], "state": "PENDING"}
    try:
        store_event(context, "DEV_BUSINESS_WRITE_ATTEMPT", details, context["attempt_id"])
    except Exception as error:
        # This isolated storage boundary runs BEFORE any business mutation.
        logger.warning("Developer audit attempt unavailable %s", type(error).__name__)
        raise DomainError("DEV_AUDIT_UNAVAILABLE", "Role testing audit is unavailable. Try again later.", 503) from error
    return context


def record_outcome(context, status, error_type=None):
    if context is None:
        return
    details = {"attempt_id": str(context["attempt_id"]),
               "target_user_id": str(context["target_id"]),
               "request_id": context["request_id"], "http_status": status}
    if error_type:
        details["error_type"] = error_type
    try:
        store_event(context, "DEV_BUSINESS_WRITE_OUTCOME", details, uuid4())
    except Exception as error:
        # The durable attempt remains PENDING/unknown. Never turn an already
        # committed business success into a failure or invent an outcome record.
        logger.warning("Developer audit outcome unavailable %s", type(error).__name__)
