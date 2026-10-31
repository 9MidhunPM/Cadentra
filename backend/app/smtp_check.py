"""Private configuration/preflight check. Never sends an email or prints settings."""

import argparse

from app.core.config import get_settings
from app.core.outbox import smtp_connection, validate_smtp_ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connect", action="store_true", help="Also verify TLS/auth; send no emails"
    )
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        if settings.smtp_host.casefold() != "smtp.resend.com":
            print("FAIL SMTP preflight: Resend is not configured")
            return 1
        validate_smtp_ready(settings)
    except Exception:
        # Validation/provider exceptions can contain credentials; never interpolate them.
        print("FAIL SMTP preflight: invalid configuration")
        return 1
    if args.connect:
        try:
            with smtp_connection(settings):
                pass
        except Exception:
            print("FAIL SMTP preflight: TLS/authentication check failed")
            return 1
        print("PASS SMTP preflight: TLS/authentication accepted; no email sent")
    else:
        print("PASS SMTP preflight: configuration valid; connection and delivery not tested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
