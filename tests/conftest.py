"""Test fixtures for anything that touches the database (AL-107).

Until now no test needed a database: `test_health.py` fakes the engine with
inline stub classes, which is enough for a liveness probe and not enough for a
query. This is the first real one.

Deliberately sqlite in memory rather than a Postgres service in CI: the CI
workflow has no database, and adding one to run a handful of read tests is a
large step for a small gain. The divergences that matter are known — `sa.Enum`
becomes VARCHAR+CHECK, `Uuid` becomes CHAR(32), `JSON` becomes TEXT — and none
of them bite **as long as `metadata_json` is never filtered in SQL**. Read it in
Python; that rule is what keeps these tests representative.

**Uno de ellos sí mordió (2026-08-13).** `sa.Enum` degradado a VARCHAR aceptó los
nombres de los miembros (`"BATTERY"`), que es lo que SQLAlchemy persiste por
omisión, mientras el tipo real de Postgres tenía los valores en minúscula: el
endpoint de inventario respondió 500 en p340 con la suite entera en verde. La
corrección vive en `models._enum_values` y la comprobación en
`test_enum_labels.py`, que mira las etiquetas declaradas en vez de una consulta —
porque una consulta contra sqlite nunca habría visto la diferencia.

La lección no es "no usar sqlite", es que la lista de divergencias de arriba hay
que tratarla como una lista de cosas a fijar con una prueba, no como una lista de
cosas inofensivas. Correr la suite contra Postgres las cubriría todas de una vez y
sigue siendo la mejora pendiente.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aerolink import main
from aerolink.config import get_settings
from aerolink.db import Base, get_db
from aerolink.models import Device, DeviceKind, Workspace

WORKSPACE_SLUG = "jej"
SERVICE_TOKEN = "test-token-not-a-real-secret"


@pytest.fixture
def engine():
    # StaticPool is mandatory: without it every connection gets its own empty
    # in-memory database and the fixture silently tests nothing.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def workspace(db_session) -> Workspace:
    workspace = Workspace(name="JEJ", slug=WORKSPACE_SLUG)
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture
def configured_token(monkeypatch):
    """Point the settings at the test token.

    `get_settings` is `lru_cache`d and the cache is process-global, so it is
    cleared both **before and after**: forgetting the teardown clear is how
    unrelated tests start depending on ordering.
    """
    monkeypatch.setenv("SERVICE_TOKEN", SERVICE_TOKEN)
    monkeypatch.setenv("SERVICE_TOKEN_WORKSPACE", WORKSPACE_SLUG)
    get_settings.cache_clear()
    yield SERVICE_TOKEN
    get_settings.cache_clear()


@pytest.fixture
def client(db_session):
    """A client whose requests use the test session.

    `main.app` is one shared global across every test module, so the override is
    removed in teardown -- otherwise test ordering starts to matter.
    """
    main.app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(configured_token) -> dict[str, str]:
    return {"Authorization": f"Token {configured_token}"}


@pytest.fixture
def make_device(db_session, workspace):
    """Factory for devices in the caller's workspace.

    A fixture rather than a plain helper because `tests/` is not a package, so
    test modules cannot import from this file.

    Serials are invented: AGENTS.md forbids real ones in git.
    """

    def _make(
        *,
        serial: str,
        kind: DeviceKind = DeviceKind.BATTERY,
        model: str | None = "TB65",
        status: str = "active",
        metadata: dict | None = None,
        in_workspace: Workspace | None = None,
    ) -> Device:
        device = Device(
            id=uuid.uuid4(),
            workspace_id=(in_workspace or workspace).id,
            kind=kind,
            serial_number=serial,
            model=model,
            status=status,
            metadata_json=metadata or {},
        )
        db_session.add(device)
        db_session.commit()
        return device

    return _make
