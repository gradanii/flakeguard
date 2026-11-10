import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or get_settings().database_url
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            server_version = int(connection.scalar(text("SHOW server_version_num")))
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL integration tests require a reachable PostgreSQL 16: {exc}")

    if not 160000 <= server_version < 170000:
        engine.dispose()
        pytest.fail(f"PostgreSQL 16 is required; server_version_num was {server_version}")

    missing_tables = {"organizations", "projects", "workflow_runs", "test_identities", "test_results"} - set(
        inspect(engine).get_table_names()
    )
    if missing_tables:
        engine.dispose()
        pytest.fail(
            "Domain schema is missing tables "
            f"{sorted(missing_tables)}; run `alembic upgrade head` before pytest."
        )

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(postgres_engine):
    connection = postgres_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
