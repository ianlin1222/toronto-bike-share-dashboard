from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

pytestmark = pytest.mark.integration


def test_migrations_downgrade_and_upgrade_on_disposable_database(database_engine: Engine) -> None:
    url = database_engine.url.render_as_string(hide_password=False)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    previous = os.environ.get("BIKESHARE_DATABASE_URL")
    os.environ["BIKESHARE_DATABASE_URL"] = url
    try:
        database_engine.dispose()
        command.downgrade(config, "base")
        assert "stations" not in inspect(database_engine).get_table_names()
        database_engine.dispose()
        command.upgrade(config, "head")
        assert "stations" in inspect(database_engine).get_table_names()
    finally:
        if previous is None:
            os.environ.pop("BIKESHARE_DATABASE_URL", None)
        else:
            os.environ["BIKESHARE_DATABASE_URL"] = previous
