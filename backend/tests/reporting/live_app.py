"""Test-only HTTP app with a fixed business date, never a public clock override."""

import os
from datetime import date

from fixture_database import checked_url, read_manifest, scoped_url

from app.core import clock

# Resolve the private manifest before importing app DB/settings singletons.
manifest = os.environ.get("CADENTRA_LIVE_CREDENTIALS")
if manifest and os.environ.get("CADENTRA_T30_SCHEMA") == "1":
    from pathlib import Path

    data = read_manifest(Path(manifest))
    if data.get("state") != "ready":
        raise RuntimeError("T30 fixture is not committed and ready")
    os.environ["DATABASE_URL"] = scoped_url(data).render_as_string(hide_password=False)
    checked_url(schema=data["schema"])
else:
    checked_url()


class FixedClock(clock.Clock):
    def today(self):
        return date(2026, 11, 2)


clock._clock = FixedClock()

from app.main import create_app  # noqa: E402

app = create_app()
