# Development

## Requirements

- Python 3.12+
- Node.js 20 and npm
- Docker Compose with PostgreSQL 16

## Backend setup

From the repository root:

```sh
cp .env.example .env
docker compose up -d db
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
```

Set `DATABASE_URL` in the root `.env` when using a different PostgreSQL instance. `TEST_DATABASE_URL` may point integration tests to a dedicated PostgreSQL 16 database; if unset, tests use `DATABASE_URL`. Integration tests require the schema to be migrated first. They check the server major version and do not fall back to SQLite.

Run backend verification from `backend/`:

```sh
ruff check .
alembic upgrade head
pytest
```

For migration rollback verification:

```sh
alembic downgrade 0001_m0_baseline
alembic upgrade head
```

The PostgreSQL integration tests use transaction rollback for isolation. A concurrency integration test commits and removes its own temporary fixture rows.

## Frontend setup

```sh
cd frontend
npm ci
npm run dev
```

## Persistence conventions

- Repository functions accept `sqlalchemy.orm.Session` and never commit. The caller owns commit/rollback.
- `get_or_create_*` functions use PostgreSQL conflict handling against database unique constraints, so concurrent calls converge on the same row.
- `persist_test_results` returns the number of new rows inserted; duplicate rows are ignored safely, including concurrent writers.
- Do not store raw test reports, failure messages, or stack traces. Only a sanitized, normalized failure representation may be hashed into a signature; callers must not pass raw exception text to the signature helper.
