# FlakeGuard

CI reliability intelligence for GitHub Actions. M0 provides the local development foundation: a FastAPI service, a SvelteKit frontend, and PostgreSQL. Test result ingestion and reliability analysis are not implemented yet.

## Requirements

- Python 3.12+
- Node.js 20+
- npm
- Docker Compose

## Start locally

1. Create the local environment file and start PostgreSQL:

   ```sh
   cp .env.example .env
   docker compose up -d db
   ```

2. Install and start the backend:

   ```sh
   cd backend
   python -m venv .venv
   . .venv/bin/activate
   pip install -e '.[dev]'
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

   The API is at <http://localhost:8000>. Liveness is at `/health`; readiness is at `/health/ready` and checks the database.

3. In another terminal, install and start the frontend:

   ```sh
   cd frontend
   npm install
   npm run dev
   ```

   The frontend is at <http://localhost:5173>.

## Configuration

Copy `.env.example` to `.env`. The backend reads `DATABASE_URL` and `APP_ENV` from the environment. `DATABASE_URL` defaults to the local Compose database if unset. Never commit `.env` or place credentials in source control. For a non-local database, use a PostgreSQL SQLAlchemy URL such as `postgresql+psycopg://user:password@host:5432/flakeguard`.

## Checks

```sh
cd backend
pip install -e '.[dev]'
ruff check .
pytest
alembic upgrade head
```

```sh
cd frontend
npm ci
npm run check
npm test -- --run
```

CI runs backend lint/tests and checks that Alembic can upgrade against an ephemeral PostgreSQL service. It also runs frontend type/accessibility checks and tests.

## Domain schema

M1 Phase 1 adds organizations, projects, workflow attempts, stable project-scoped test identities, and test results. Test results are idempotent per workflow attempt and identity, and composite foreign keys prevent cross-project result links. Raw JUnit XML, failure messages, and stack traces are not stored; only signatures derived from sanitized normalized failure data may be retained. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for entity relationships, constraints, and retention details.

## Open decisions before ingestion

- Organization provisioning and authentication/authorization model.
- GitHub Action credential issuance and revocation.
- Stable test identity normalization across pytest and Jest.
- Run identity and duplicate/retry semantics.
- Retention periods for results and derived reports.
- Hosting, backups, and database operations for production.
