"""Rollback-only sessions against an explicitly named disposable PostgreSQL database."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def db_connection():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail(
            "TEST_DATABASE_URL must identify an explicitly disposable PostgreSQL *_test database"
        )
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def db_session(db_connection):
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as db:
        yield db


@pytest.fixture
def client(db_connection, monkeypatch):
    from app.core import auth
    from app.core.config import get_settings
    from app.db import session as database
    from app.main import create_app

    def factory():
        return Session(
            bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    monkeypatch.setattr(database, "SessionFactory", factory)
    application = create_app()

    def dependency():
        with factory() as db:
            yield db

    application.dependency_overrides[database.get_session] = dependency

    def auth_dependency():
        # Auth reads share the outer connection without nesting over business savepoints.
        with Session(
            bind=db_connection, join_transaction_mode="rollback_only", expire_on_commit=False
        ) as db:
            yield db

    application.dependency_overrides[auth.get_auth_session] = auth_dependency
    with TestClient(application, headers={"Origin": get_settings().allowed_origins[0]}) as client:
        yield client
