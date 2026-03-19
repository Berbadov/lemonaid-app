from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import ROOT_DIR, SETTINGS, ensure_data_dirs
from storage.models import Base


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    ensure_data_dirs()
    sqlite_path = (ROOT_DIR / SETTINGS.sqlite_path).resolve()
    engine = create_engine(
        f"sqlite:///{sqlite_path.as_posix()}",
        future=True,
        echo=False,
    )
    return engine


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def create_all_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
