import smtplib
from datetime import timedelta
from uuid import uuid4

import pytest

from app.core import outbox
from app.core.clock import get_clock
from app.models import EmailOutbox

pytestmark = pytest.mark.integration


def queue(db, *, kind="RESET", payload=None):
    row = EmailOutbox(
        kind=kind,
        aggregate_id=uuid4(),
        recipient="customer@example.com",
        subject="Cadentra email",
        dedupe_key=str(uuid4()),
        payload=payload
        if payload is not None
        else {"reset_url": "http://localhost:5171/reset-password?token=single-use-test-token"},
        next_attempt_at=get_clock().now() - timedelta(seconds=1),
    )
    db.add(row)
    db.flush()
    return row


def test_reset_composition_and_smtp_acceptance(db_session, monkeypatch):
    row = queue(db_session)
    messages = []
    monkeypatch.setattr(outbox, "send_message", messages.append)
    result = outbox.dispatch_pending(db_session)
    assert result == {"processed": 1, "accepted_by_smtp": 1, "failed": 0}
    assert row.status == "SENT" and row.attempts == 1
    assert messages[0]["To"] == "customer@example.com"
    assert "single-use-test-token" in messages[0].get_content()
    assert outbox.dispatch_pending(db_session)["processed"] == 0


def test_failure_is_sanitized_and_retries_only_when_due(db_session, monkeypatch):
    row = queue(db_session)

    def fail(message):
        raise smtplib.SMTPAuthenticationError(535, b"secret-token must not be stored")

    monkeypatch.setattr(outbox, "send_message", fail)
    result = outbox.dispatch_pending(db_session)
    assert result["failed"] == 1
    assert row.status == "FAILED" and row.last_error == "SMTPAuthenticationError"
    assert "secret-token" not in row.last_error
    first_next = row.next_attempt_at
    assert first_next >= get_clock().now() + timedelta(seconds=25)
    assert outbox.dispatch_pending(db_session)["processed"] == 0
    row.next_attempt_at = get_clock().now() - timedelta(seconds=1)
    outbox.dispatch_pending(db_session)
    assert row.attempts == 2 and row.next_attempt_at > first_next
    row.next_attempt_at = get_clock().now() - timedelta(seconds=1)
    monkeypatch.setattr(outbox, "send_message", lambda message: None)
    assert outbox.dispatch_pending(db_session)["accepted_by_smtp"] == 1
    assert row.last_error is None and row.status == "SENT"


def test_invalid_payload_never_reaches_smtp(db_session, monkeypatch):
    row = queue(
        db_session, payload={"reset_url": "https://untrusted.example/reset-password?token=x"}
    )
    calls = []
    monkeypatch.setattr(outbox, "send_message", calls.append)
    assert outbox.dispatch_pending(db_session)["failed"] == 1
    assert row.status == "FAILED" and row.last_error == "InvalidPayload" and not calls


def test_invoice_alternative_content_and_bounded_batch(db_session, monkeypatch):
    rows = [
        queue(
            db_session,
            kind="INVOICE",
            payload={"text": "Invoice total INR4970.16", "html": "<p>Invoice total INR4970.16</p>"},
        )
        for _ in range(2)
    ]
    messages = []
    monkeypatch.setattr(outbox, "send_message", messages.append)
    assert outbox.dispatch_pending(db_session, limit=1)["processed"] == 1
    assert sum(row.status == "SENT" for row in rows) == 1
    assert messages[0].is_multipart()
    assert "4970.16" in messages[0].get_body(preferencelist=("html",)).get_content()


def test_transport_has_timeout_tls_auth_and_recipient_refusal(monkeypatch):
    events = []

    class SMTP:
        def __init__(self, host, port, timeout):
            events.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, *, context):
            events.append("tls")

        def login(self, username, password):
            events.append("authenticated")

        def send_message(self, message):
            return {"recipient@example.com": (550, b"refused")}

    settings = outbox.get_settings().model_copy(
        update={"smtp_starttls": True, "smtp_user": "user", "smtp_password": "private"}
    )
    monkeypatch.setattr(outbox, "get_settings", lambda: settings)
    monkeypatch.setattr(outbox.smtplib, "SMTP", SMTP)
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        outbox.send_message(outbox.EmailMessage())
    assert events == [
        (settings.smtp_host, settings.smtp_port, 10),
        "ehlo",
        "tls",
        "ehlo",
        "authenticated",
    ]
