from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models import Base
from main import app

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

# Default test user — super_admin bypasses all role checks.
# Tests that need a different role override get_current_user locally.
_DEFAULT_USER = CurrentUser(id=1, role="super_admin")


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        SQLALCHEMY_TEST_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    def override_get_current_user() -> CurrentUser:
        return _DEFAULT_USER

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
