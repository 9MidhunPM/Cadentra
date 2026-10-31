"""Narrow, test-only database/schema guards shared by explicit browser fixtures."""

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

DATABASES = frozenset({"cadentra_experience_test", "cadentra_performance_test"})
PERFORMANCE_DATABASE = "cadentra_performance_test"


def checked_url(value=None, *, schema=None):
    url = make_url(value if value is not None else os.environ.get("DATABASE_URL", ""))
    if (
        os.environ.get("APP_ENV") != "test"
        or url.drivername != "postgresql+psycopg"
        or url.username != "cadentra"
        or url.password is not None
        or url.host != "127.0.0.1"
        or url.port != 55431
        or url.database not in DATABASES
    ):
        raise RuntimeError("Fixtures require the explicitly assigned local test database and user")
    expected = {} if schema is None else {"options": f"-csearch_path={schema}"}
    if dict(url.query) != expected:
        raise RuntimeError("Unexpected database connection options")
    return url


def namespace(run):
    try:
        parsed = UUID(run)
    except (ValueError, TypeError, AttributeError) as error:
        raise RuntimeError("Fixture run must be a canonical UUID4") from error
    if parsed.version != 4 or str(parsed) != run:
        raise RuntimeError("Fixture run must be a canonical UUID4")
    return "t30_" + parsed.hex


def manifest_path(path):
    if path.parent != Path("/tmp") or path.is_symlink():
        raise RuntimeError("Use a private manifest directly under /tmp")


def read_manifest(path):
    manifest_path(path)
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.getuid()
    ):
        raise RuntimeError("Manifest must be owned by this user with mode0600")
    data = json.loads(path.read_text())
    if (
        data.get("test_only") is not True
        or data.get("kind") != "T30"
        or data.get("database") != PERFORMANCE_DATABASE
        or data.get("schema") != namespace(data.get("run", ""))
    ):
        raise RuntimeError("Not a bound T30 performance fixture manifest")
    return data


def base_url(data=None):
    url = checked_url()
    if url.database != PERFORMANCE_DATABASE or (data and data["database"] != url.database):
        raise RuntimeError("T30 namespaces are permitted only in the performance test database")
    return url


def scoped_url(data):
    url = base_url(data)
    if data["schema"] != namespace(data["run"]):
        raise RuntimeError("Fixture namespace does not match its run UUID")
    return url.update_query_dict({"options": f"-csearch_path={data['schema']}"})


def verify_namespace(connection, data):
    """Read-only proof: exact generated namespace, database, owner and run marker."""
    if data["schema"] != namespace(data["run"]) or not re.fullmatch(
        r"t30_[0-9a-f]{32}", data["schema"]
    ):
        raise RuntimeError("Refusing a non-generated namespace")
    row = connection.execute(
        text(
            "SELECT current_database(), pg_get_userbyid(nspowner), "
            "obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname = :schema"
        ),
        {"schema": data["schema"]},
    ).one_or_none()
    if row is None or tuple(row) != (
        PERFORMANCE_DATABASE,
        "cadentra",
        "cadentra:T30:" + data["run"],
    ):
        raise RuntimeError("Fixture namespace ownership proof failed")


def create_namespace(data):
    scoped = scoped_url(data)
    engine = create_engine(base_url(data))
    try:
        with engine.begin() as db:
            db.execute(CreateSchema(data["schema"]))
            # Both identifiers originate from a validated UUID, never arbitrary SQL.
            db.execute(
                text(f"COMMENT ON SCHEMA \"{data['schema']}\" IS 'cadentra:T30:{data['run']}'")
            )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env=dict(os.environ, DATABASE_URL=scoped.render_as_string(hide_password=False)),
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    finally:
        engine.dispose()


def drop_namespace(data):
    engine = create_engine(base_url(data))
    try:
        with engine.begin() as db:
            verify_namespace(db, data)
            db.execute(DropSchema(data["schema"], cascade=True))
    finally:
        engine.dispose()
