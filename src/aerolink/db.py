from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from aerolink.config import get_settings


class Base(DeclarativeBase):
    """Base class for AeroLink's durable domain models."""


# `connect_timeout` is not a tuning detail, it is what makes the probes honest:
# without it a database whose host does not resolve takes the operating system's
# full DNS/TCP timeout -- measured at ~130s -- and during that time `/ready`
# hangs instead of answering 503 and `/metrics` hangs instead of reporting
# `aerolink_ingestion_metrics_available 0`. A probe that hangs is worse than one
# that fails: the scraper times out with no signal about why.
engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
