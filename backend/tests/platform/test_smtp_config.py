"""Resend validation, safe preflight and stable provider retry identity."""

import smtplib
import ssl
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import smtp_check
from app.core import outbox
from app.core.config import Settings


def resend_settings(**changes):
    values = dict(
        _env_file=None,
        smtp_host="smtp.resend.com",
        smtp_port=587,
        smtp_user="resend",
        smtp_password="synthetic-private-key-never-display",
        smtp_from="Cadentra <billing@cadentra-demo.com>",
        smtp_starttls=True,
        app_env="production",
        app_origin="https://cadentra-demo.com",
        allowed_origins=("https://cadentra-demo.com",),
        session_cookie_secure=True,
        trusted_web_proxy_ips=("172.31.250.2",),
    )
    return Settings(**(values | changes))


def test_resend_defaults_validate_and_dev_capture_stays_valid():
    assert resend_settings().smtp_port == 587
    assert Settings(_env_file=None).smtp_host == "localhost"
    # Existing production proxy-only tests may retain localhost defaults.
    assert (
        resend_settings(smtp_host="localhost", smtp_starttls=False, smtp_password="").app_env
        == "production"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"smtp_starttls": False},
        {"smtp_port": 465},
        {"smtp_user": "wrong"},
        {"smtp_password": "REPLACE_THIS"},
        {"smtp_from": "bad\r\nBcc: unwanted@example.com"},
        {"smtp_from": "a@example.com,b@example.com"},
        {"smtp_from": "noreply@example.invalid"},
        {"smtp_from": "invalid"},
        {"app_origin": "https://cadentra-demo.com/"},
        {"app_origin": "https://cadentra-demo.com?token=synthetic-secret"},
        {"app_origin": "https://user:synthetic-secret@cadentra-demo.com"},
        {"app_origin": "https://bad host"},
        {"allowed_origins": ("https://elsewhere.com",)},
        {"allowed_origins": ("https://cadentra-demo.com", "https://bad host")},
    ],
)
def test_resend_rejects_insecure_or_ambiguous_config(changes):
    with pytest.raises(ValidationError) as error:
        resend_settings(**changes)
    assert "synthetic-private-key-never-display" not in str(error.value)
    assert "synthetic-secret" not in str(error.value)


def test_numeric_parse_failure_hides_entire_synthetic_input():
    with pytest.raises(ValidationError) as error:
        resend_settings(smtp_port="synthetic-port-secret")
    assert "synthetic-port-secret" not in str(error.value)


def test_retry_message_identity_and_mime_bytes_are_stable(monkeypatch):
    monkeypatch.setattr(outbox, "get_settings", resend_settings)
    record = SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 10, 31, tzinfo=UTC),
        recipient="customer@example.com",
        subject="Fictional invoice",
        kind="INVOICE",
        payload={"text": "Invoice INR4970.16", "html": "<p>INR4970.16</p>"},
    )
    first, second = outbox.build_message(record), outbox.build_message(record)
    assert first.as_bytes() == second.as_bytes()
    assert first["Resend-Idempotency-Key"] == f"cadentra-outbox/{record.id}"
    assert first["Message-ID"] == f"<{record.id}@cadentra-outbox.invalid>"
    record.id = uuid4()
    assert outbox.build_message(record)["Resend-Idempotency-Key"] != first["Resend-Idempotency-Key"]


def test_tls_failure_prevents_auth_and_send(monkeypatch):
    events = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, *, context):
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            raise smtplib.SMTPNotSupportedError("synthetic-private-provider-error")

        def login(self, *args):
            events.append("auth")

        def send_message(self, *args):
            events.append("send")

    monkeypatch.setattr(outbox, "get_settings", resend_settings)
    monkeypatch.setattr(outbox.smtplib, "SMTP", SMTP)
    with pytest.raises(smtplib.SMTPNotSupportedError):
        outbox.send_message(outbox.EmailMessage())
    assert events == ["ehlo"]


def test_validation_preflight_never_connects_or_prints_values(monkeypatch, capsys):
    monkeypatch.setattr(smtp_check, "get_settings", resend_settings)
    monkeypatch.setattr(
        smtp_check, "smtp_connection", lambda _: pytest.fail("validation must not connect")
    )
    assert smtp_check.main([]) == 0
    output = capsys.readouterr().out
    assert "PASS" in output and "delivery not tested" in output
    assert "synthetic-private" not in output and "cadentra-demo.com" not in output


def test_connection_preflight_never_sends(monkeypatch, capsys):
    calls = []

    @contextmanager
    def connection(settings):
        calls.append("tls-auth-only")
        yield object()

    monkeypatch.setattr(smtp_check, "get_settings", resend_settings)
    monkeypatch.setattr(smtp_check, "smtp_connection", connection)
    assert smtp_check.main(["--connect"]) == 0
    assert calls == ["tls-auth-only"]
    assert "no email sent" in capsys.readouterr().out


@pytest.mark.parametrize("stage", ["settings", "connect"])
def test_preflight_failure_redacts_exception(stage, monkeypatch, capsys):
    def failure(*args):
        raise ValueError("synthetic-private-provider-key")

    monkeypatch.setattr(
        smtp_check, "get_settings", failure if stage == "settings" else resend_settings
    )
    monkeypatch.setattr(smtp_check, "smtp_connection", failure)
    assert smtp_check.main(["--connect"]) == 1
    output = capsys.readouterr().out
    assert "FAIL" in output and "synthetic-private-provider-key" not in output


def test_production_manifest_has_no_mailpit_but_retains_volume_and_native_mapping():
    root = Path(__file__).resolve().parents[3]
    text = (root / "compose.dokploy.yaml").read_text()
    assert "SMTP_HOST: ${COMPOSE_SMTP_HOST:-smtp.resend.com}" in text
    assert "SMTP_PORT: ${SMTP_PORT:-587}" in text
    assert "SMTP_USER: ${SMTP_USER:-resend}" in text
    assert "SMTP_STARTTLS: ${SMTP_STARTTLS:-true}" in text
    assert "SMTP_PASSWORD: ${SMTP_PASSWORD:-}" in text and "SMTP_FROM: ${SMTP_FROM:-}" in text
    assert "  mailpit:" not in text and "  mailcapture:" in text


@pytest.mark.parametrize(
    "missing", [{"smtp_password": ""}, {"smtp_from": ""}, {"smtp_password": "", "smtp_from": ""}]
)
def test_missing_resend_credentials_allow_boot_but_block_connection_and_cli(
    missing, monkeypatch, capsys
):
    settings = resend_settings(**missing)
    monkeypatch.setattr(smtp_check, "get_settings", lambda: settings)
    monkeypatch.setattr(
        outbox.smtplib,
        "SMTP",
        lambda *args, **kwargs: pytest.fail("Unconfigured SMTP must never connect"),
    )
    with pytest.raises(outbox.SMTPNotConfigured):
        with outbox.smtp_connection(settings):
            pytest.fail("Missing config must not yield a connection")
    assert smtp_check.main([]) == 1
    assert smtp_check.main(["--connect"]) == 1
    assert "FAIL" in capsys.readouterr().out
