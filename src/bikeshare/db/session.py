from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from bikeshare.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"options": "-c timezone=UTC"},
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=900,
    )
