"""Bounded SMTP outbox dispatch with caller-owned transactions.

SENT means accepted by SMTP, not externally delivered. A crash or lost SMTP
acknowledgement before database commit can duplicate an email on retry; this
transport boundary is at-least-once and never creates invoices or payments.
"""

import smtplib
import ssl
from contextlib import contextmanager
from datetime import timedelta
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.core.config import get_settings
from app.models import EmailOutbox


class InvalidPayload(ValueError):
    """Persisted email content is incomplete or unsuitable for this template."""


class SMTPNotConfigured(smtplib.SMTPException):
    """Public site can boot before private delivery credentials are supplied."""


def validate_smtp_ready(settings) -> None:
    if settings.smtp_host.casefold() == "smtp.resend.com" or settings.app_env == "production":
        if (
            settings.smtp_host.casefold() != "smtp.resend.com"
            or not settings.smtp_password.strip()
            or not settings.smtp_from.strip()
        ):
            raise SMTPNotConfigured("SMTP provider credentials or sender are not configured")


def build_message(record: EmailOutbox) -> EmailMessage:
    settings = get_settings()
    validate_smtp_ready(settings)
    message = EmailMessage()
    try:
        outbox_id = UUID(str(record.id))
        message["Message-ID"] = f"<{outbox_id}@cadentra-outbox.invalid>"
        message["Date"] = format_datetime(record.created_at)
        # Resend retains idempotency keys for 24 hours, not an exactly-once guarantee.
        message["Resend-Idempotency-Key"] = f"cadentra-outbox/{outbox_id}"
        message["From"] = settings.smtp_from
        message["To"] = Address(addr_spec=record.recipient)
        message["Subject"] = record.subject
        if not record.subject.strip():
            raise InvalidPayload("Missing subject")
        if not isinstance(record.payload, dict):
            raise InvalidPayload("Missing payload")
        if record.kind == "RESET":
            url = record.payload.get("reset_url")
            if not isinstance(url, str):
                raise InvalidPayload("Missing reset URL")
            parsed, origin = urlsplit(url), urlsplit(settings.app_origin)
            tokens = parse_qs(parsed.query).get("token", [])
            if (
                (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc)
                or parsed.path != "/reset-password"
                or len(tokens) != 1
                or not tokens[0]
                or len(tokens[0]) > 256
            ):
                raise InvalidPayload("Invalid reset URL")
            message.set_content(
                f"Reset your Cadentra password using this single-use link:\n\n{url}\n\n"
                "If you did not request this, ignore this email."
            )
        elif record.kind == "INVOICE":
            text, html = record.payload.get("text"), record.payload.get("html")
            if not (
                (isinstance(text, str) and text.strip()) or (isinstance(html, str) and html.strip())
            ):
                raise InvalidPayload("Missing invoice content")
            message.set_content(
                text
                if isinstance(text, str) and text.strip()
                else "Your invoice is included in the HTML version of this email."
            )
            if isinstance(html, str) and html.strip():
                message.add_alternative(html, subtype="html")
                message.set_boundary(f"cadentra-outbox-{outbox_id.hex}")
        else:
            raise InvalidPayload("Unsupported email kind")
    except (ValueError, TypeError) as error:
        raise InvalidPayload("Invalid email content") from error
    return message


@contextmanager
def smtp_connection(settings):
    """One verified STARTTLS/auth path shared by sending and no-mail preflight."""
    validate_smtp_ready(settings)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as connection:
        connection.ehlo()
        if settings.smtp_starttls:
            connection.starttls(context=ssl.create_default_context())
            connection.ehlo()
        if settings.smtp_user:
            connection.login(settings.smtp_user, settings.smtp_password)
        yield connection


def send_message(message: EmailMessage) -> None:
    """Patch this transport boundary in tests; production uses configured SMTP."""
    with smtp_connection(get_settings()) as connection:
        refused = connection.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def dispatch_pending(db: Session, limit: int | None = None) -> dict[str, int]:
    """Dispatch locked due rows; caller commits successes/failures atomically."""
    batch_size = get_settings().worker_batch_size if limit is None else limit
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= 1000
    ):
        raise ValueError("Outbox batch limit must be between 1 and 1000")
    now = get_clock().now()
    records = db.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.status.in_(("PENDING", "FAILED")), EmailOutbox.next_attempt_at <= now)
        .order_by(EmailOutbox.next_attempt_at, EmailOutbox.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    result = {"processed": 0, "accepted_by_smtp": 0, "failed": 0}
    for record in records:
        record.attempts += 1
        record.status = "SENDING"
        try:
            message = build_message(record)
            send_message(message)
        except (InvalidPayload, smtplib.SMTPException, OSError) as error:
            record.status = "FAILED"
            # Never persist a transport exception message: it may echo tokens or credentials.
            record.last_error = type(error).__name__
            record.next_attempt_at = get_clock().now() + timedelta(
                seconds=min(3600, 30 * (2 ** min(record.attempts - 1, 7)))
            )
            result["failed"] += 1
        else:
            record.status = "SENT"
            record.last_error = None
            result["accepted_by_smtp"] += 1
        result["processed"] += 1
    db.flush()
    return result


def main(argv: list[str] | None = None) -> int:
    """Explicit one-batch dispatcher; print counts without message/token content."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Dispatch one bounded pending SMTP outbox batch")
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    if args.limit is not None and not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    from app.db.session import SessionFactory

    with SessionFactory.begin() as db:
        result = dispatch_pending(db, args.limit)
    counts = {key: result[key] for key in ("processed", "accepted_by_smtp", "failed")}
    print(json.dumps(counts, sort_keys=True))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
