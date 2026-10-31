"""Pure guard tests: no engine connections or PostgreSQL mutations."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fixture_database import (
    base_url,
    checked_url,
    namespace,
    read_manifest,
    scoped_url,
    verify_namespace,
)

BASE = "postgresql+psycopg://cadentra@127.0.0.1:55431/"


@pytest.fixture
def bound(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", BASE + "cadentra_performance_test")
    run = str(uuid4())
    return {
        "test_only": True,
        "kind": "T30",
        "database": "cadentra_performance_test",
        "run": run,
        "schema": namespace(run),
        "state": "ready",
    }


@pytest.mark.parametrize("database", ["cadentra_experience_test", "cadentra_performance_test"])
def test_only_explicit_databases_allowed(bound, database):
    assert checked_url(BASE + database).database == database


@pytest.mark.parametrize(
    "url",
    [
        BASE + "cadentra_experience",
        BASE + "other_test",
        "postgresql://cadentra@127.0.0.1:55431/cadentra_performance_test",
        "postgresql+psycopg://postgres@127.0.0.1:55431/cadentra_performance_test",
        "postgresql+psycopg://cadentra:secret@127.0.0.1:55431/cadentra_performance_test",
        "postgresql+psycopg://cadentra@localhost:55431/cadentra_performance_test",
        "postgresql+psycopg://cadentra@127.0.0.1:5432/cadentra_performance_test",
        BASE + "cadentra_performance_test?options=-csearch_path%3Dpublic",
        BASE + "cadentra_performance_test?host=other-server",
    ],
)
def test_connection_redirections_rejected(bound, url):
    with pytest.raises(RuntimeError):
        checked_url(url)


def test_production_environment_rejected(bound, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        checked_url()


def test_t30_never_uses_old_experience_database(bound, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", BASE + "cadentra_experience_test")
    with pytest.raises(RuntimeError):
        base_url(bound)


def test_exact_scoped_url_only(bound):
    scoped = scoped_url(bound)
    assert dict(scoped.query) == {"options": f"-csearch_path={bound['schema']}"}
    assert checked_url(scoped, schema=bound["schema"]) == scoped
    with pytest.raises(RuntimeError):
        checked_url(scoped)


@pytest.mark.parametrize(
    "schema", ["public", "t30_other", "t30_" + "0" * 32, "t30_abc;DROP SCHEMA public"]
)
def test_namespace_must_match_full_run_uuid(bound, schema):
    with pytest.raises(RuntimeError):
        scoped_url({**bound, "schema": schema})


def test_private_manifest_binds_run_and_database(bound):
    path = Path("/tmp") / f"cadentra-guard-{uuid4().hex}.json"
    try:
        path.touch(mode=0o600)
        path.write_text(json.dumps(bound))
        assert read_manifest(path) == bound
        path.chmod(0o644)
        with pytest.raises(RuntimeError):
            read_manifest(path)
        path.chmod(0o600)
        path.write_text(json.dumps({**bound, "database": "cadentra_experience_test"}))
        with pytest.raises(RuntimeError):
            read_manifest(path)
        path.write_text(json.dumps({**bound, "schema": "public"}))
        with pytest.raises(RuntimeError):
            read_manifest(path)
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "row",
    [
        None,
        ("cadentra_experience_test", "cadentra", "marker"),
        ("cadentra_performance_test", "postgres", "marker"),
        ("cadentra_performance_test", "cadentra", "wrong-run"),
    ],
)
def test_teardown_proof_rejects_wrong_database_owner_or_marker(bound, row):
    class Connection:
        def execute(self, statement, values):
            assert str(statement).startswith("SELECT ")
            assert values == {"schema": bound["schema"]}
            return self

        def one_or_none(self):
            return row

    with pytest.raises(RuntimeError):
        verify_namespace(Connection(), bound)


def test_teardown_proof_is_read_only_and_exact(bound):
    class Connection:
        def execute(self, statement, values):
            assert str(statement).startswith("SELECT ")
            assert values == {"schema": bound["schema"]}
            return self

        def one_or_none(self):
            return ("cadentra_performance_test", "cadentra", "cadentra:T30:" + bound["run"])

    verify_namespace(Connection(), bound)
