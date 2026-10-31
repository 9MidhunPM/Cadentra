from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, localcontext

import pytest

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.money import money
from app.core.security import (
    hash_password,
    hash_token,
    normalize_email,
    validate_password,
    verify_password,
)


def test_money_rounds_half_up_and_rejects_float_nonfinite():
    assert money("1.005") == Decimal("1.01")
    assert money("-1.005") == Decimal("-1.01")
    for value in [1.005, "NaN", "Infinity", "nonsense"]:
        with pytest.raises(ValueError):
            money(value)


def test_password_boundary_and_hash():
    for value in ["Abcdefg!", "abcdefgh!", "ABCDEFGH!", "Abcdefghi", "Abcdefgh "]:
        with pytest.raises(DomainError):
            validate_password(value)
    validate_password("Abcdefgh!")  # Digits are not an extra requirement.
    encoded = hash_password("Abcdefgh!")
    assert encoded != "Abcdefgh!"
    assert verify_password("Abcdefgh!", encoded)
    assert not verify_password("Incorrect!", encoded)
    assert not verify_password("Abcdefgh!", "not-a-hash")
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"
    assert hash_token("secret") != "secret"


def test_clock_uses_business_zone(monkeypatch):
    class FixedClock(Clock):
        def now(self):
            return datetime(2026, 10, 31, 20, 0, tzinfo=UTC)

    assert str(FixedClock().today()) == "2026-11-01"


def test_settings_reject_sqlite_and_insecure_production():
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///test.db")
    with pytest.raises(ValueError):
        Settings(app_env="production", session_cookie_secure=False)


def test_money_is_independent_of_callers_decimal_context():
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        assert money("4680.005") == Decimal("4680.01")
