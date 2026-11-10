# FlakeGuard architecture

## M1 Phase 1 data model

The backend remains a single FastAPI application using synchronous SQLAlchemy 2 sessions and PostgreSQL. Persistence functions accept a caller-owned `Session`; they flush or execute statements but never commit. The caller decides transaction boundaries.

### Entities and ownership

- An **Organization** owns projects and is the tenant boundary.
- A **Project** belongs to one organization and represents one repository. Repository owner and name are normalized to lowercase by the repository function and checked in PostgreSQL. A unique constraint allows one project per organization and repository.
- A **WorkflowRun** belongs to one project. Its external identity is `(project_id, external_run_id, run_attempt)`. Each GitHub rerun has a new attempt row. `commit_sha` is revision metadata and is not part of run identity.
- A **TestIdentity** belongs to one project and represents a stable logical test. Its identity key is `(project_id, framework, canonical_fingerprint)`. Failure content is never used as identity.
- A **TestResult** links one workflow attempt to one test identity. It includes `project_id` and composite foreign keys so PostgreSQL rejects a result that combines a run and identity from different projects. Its idempotency key is `(workflow_run_id, test_identity_id)`.

Descendants inherit tenant ownership through their project foreign key; only Project stores `organization_id`. Queries that enforce organization visibility must join through Project. Database authorization policies and user authentication are outside this phase.

### Constraints and indexes

PostgreSQL constraints enforce unique organization slugs, repository identity per organization, workflow attempt identity, test fingerprints, and result identity. Check constraints validate frameworks, workflow status/conclusion, result outcome, timestamps, positive attempts, nonnegative durations, lowercase repository coordinates, and SHA-256 signature format.

Indexes support projects by organization (the repository unique index begins with `organization_id`), workflow runs by project and start time, test identities by project (their unique index begins with `project_id`), and result history by test identity and workflow run. Results also have a project index for tenant-scoped queries.

Foreign keys use `RESTRICT`; deleting a parent cannot silently delete historical records. Deletion policy and retention jobs are not implemented yet.

### Workflow lifecycle

`WorkflowRun.status` represents execution state (`queued`, `in_progress`, `completed`, `waiting`, `requested`, or `pending`). `conclusion` is separately nullable and may be populated only after status becomes `completed`. A run attempt is distinct from a workflow run's commit SHA and from other attempts.

### Test identity and results

Framework is constrained to `pytest` or `jest`. Canonical fingerprints are project-scoped and framework-scoped. The ingestion layer that defines canonicalization is not part of this phase. Test results are unique within an attempt and can be persisted concurrently using PostgreSQL `ON CONFLICT` handling.

## Privacy and retention

Raw JUnit XML, failure messages, and stack traces are not stored. `failure_signature` stores only a 64-character SHA-256 digest derived from already-normalized and sanitized failure information. The hashing helper does not normalize exception text: a future parser must remove secrets, volatile paths, and other sensitive details before hashing. Signatures can still reveal equality and should be treated as customer data. No automated retention or deletion policy exists yet; retention periods require a product decision before ingestion is enabled.
