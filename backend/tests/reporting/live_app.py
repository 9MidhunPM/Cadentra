"""Test-only HTTP app with a fixed business date, never a public clock override."""

import os
from datetime import date

from sqlalchemy.engine import make_url

from app.core import clock

url = make_url(os.environ.get('DATABASE_URL', ''))
if (os.environ.get('APP_ENV') != 'test' or url.host != '127.0.0.1' or url.port != 55431
        or url.database != 'cadentra_experience_test'):
    raise RuntimeError('This app only runs against the assigned disposable test database')


class FixedClock(clock.Clock):
    def today(self):
        return date(2026, 11, 2)


clock._clock = FixedClock()

from app.main import create_app  # noqa: E402

app = create_app()
