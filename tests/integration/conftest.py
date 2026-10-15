from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def database_engine() -> Iterator[Engine]:
    configured = os.getenv("BIKESHARE_TEST_ADMIN_URL")
    if not configured:
        pytest.skip("BIKESHARE_TEST_ADMIN_URL is not set; PostgreSQL integration test skipped")
    admin_url = make_url(configured)
    database_name = f"bikeshare_test_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created_roles: list[str] = []
    with admin_engine.connect() as connection:
        for role_name in ("bikeshare_ingest", "bikeshare_api", "bikeshare_reporter"):
            if connection.scalar(text('SELECT 1 FROM pg_roles WHERE rolname=:name'), {'name': role_name}):
                continue
            created_roles.append(role_name)
            connection.execute(
                text(
                    f"""
                    DO $role$
                    BEGIN
                      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role_name}') THEN
                        CREATE ROLE {role_name} LOGIN PASSWORD 'integration-test-only';
                      END IF;
                    END
                    $role$
                    """
                )
            )
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    test_url = admin_url.set(database=database_name)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False))
    # env.py uses the setting, so provide it only for the migration call.
    old_url = os.environ.get("BIKESHARE_DATABASE_URL")
    os.environ["BIKESHARE_DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    try:
        command.upgrade(config, "head")
        engine = create_engine(test_url)
        yield engine
        engine.dispose()
    finally:
        if old_url is None:
            os.environ.pop("BIKESHARE_DATABASE_URL", None)
        else:
            os.environ["BIKESHARE_DATABASE_URL"] = old_url
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE "{database_name}"'))
            for role_name in created_roles:
                connection.execute(text(f"DROP ROLE IF EXISTS {role_name}"))
        admin_engine.dispose()
