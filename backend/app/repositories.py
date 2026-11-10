from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Organization, Project, TestIdentity, TestResult, WorkflowRun


def create_organization(session: Session, *, name: str, slug: str) -> Organization:
    organization = Organization(name=name.strip(), slug=slug.strip().lower())
    session.add(organization)
    session.flush()
    return organization


def create_project(
    session: Session,
    *,
    organization_id: UUID,
    name: str,
    repository_owner: str,
    repository_name: str,
    default_branch: str,
) -> Project:
    project = Project(
        organization_id=organization_id,
        name=name.strip(),
        repository_owner=repository_owner.strip().lower(),
        repository_name=repository_name.strip().lower(),
        default_branch=default_branch.strip(),
    )
    session.add(project)
    session.flush()
    return project


def get_projects_for_organization(session: Session, organization_id: UUID) -> list[Project]:
    statement = select(Project).where(Project.organization_id == organization_id).order_by(Project.name)
    return list(session.scalars(statement))


def get_or_create_workflow_run(
    session: Session,
    *,
    project_id: UUID,
    external_run_id: str,
    run_attempt: int,
    commit_sha: str,
    branch: str,
    workflow_name: str,
    status: str,
    conclusion: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> WorkflowRun:
    values: dict[str, Any] = {
        "project_id": project_id,
        "external_run_id": external_run_id,
        "run_attempt": run_attempt,
        "commit_sha": commit_sha,
        "branch": branch,
        "workflow_name": workflow_name,
        "status": status,
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    insert_statement = (
        insert(WorkflowRun)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[
                WorkflowRun.project_id,
                WorkflowRun.external_run_id,
                WorkflowRun.run_attempt,
            ]
        )
        .returning(WorkflowRun)
    )
    workflow_run = session.scalars(insert_statement).one_or_none()
    if workflow_run is not None:
        return workflow_run

    return session.scalars(
        select(WorkflowRun).where(
            WorkflowRun.project_id == project_id,
            WorkflowRun.external_run_id == external_run_id,
            WorkflowRun.run_attempt == run_attempt,
        )
    ).one()


def get_or_create_test_identity(
    session: Session,
    *,
    project_id: UUID,
    framework: str,
    canonical_fingerprint: str,
    original_identifier: str,
    test_name: str,
    first_seen_at: datetime,
    last_seen_at: datetime,
    file_path: str | None = None,
    class_name: str | None = None,
    parameter_identifier: str | None = None,
) -> TestIdentity:
    insert_statement = insert(TestIdentity).values(
        project_id=project_id,
        framework=framework.lower(),
        canonical_fingerprint=canonical_fingerprint,
        original_identifier=original_identifier,
        test_name=test_name,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        file_path=file_path,
        class_name=class_name,
        parameter_identifier=parameter_identifier,
    )
    insert_statement = (
        insert_statement
        .on_conflict_do_update(
            index_elements=[
                TestIdentity.project_id,
                TestIdentity.framework,
                TestIdentity.canonical_fingerprint,
            ],
            set_={
                "first_seen_at": func.least(
                    TestIdentity.first_seen_at, insert_statement.excluded.first_seen_at
                ),
                "last_seen_at": func.greatest(
                    TestIdentity.last_seen_at, insert_statement.excluded.last_seen_at
                ),
                "updated_at": func.now(),
            },
        )
        .returning(TestIdentity)
        .execution_options(populate_existing=True)
    )
    return session.scalars(insert_statement).one()


def persist_test_results(
    session: Session,
    results: Iterable[Mapping[str, Any]],
) -> int:
    """Insert result rows once; return how many rows this call inserted.

    Duplicate keys within this batch are collapsed before issuing SQL. PostgreSQL's
    ON CONFLICT handles duplicates arriving concurrently from other transactions.
    The caller owns the transaction and must commit or roll it back.
    """
    unique_results: dict[tuple[UUID, UUID], dict[str, Any]] = {}
    for result in results:
        values = dict(result)
        values.setdefault("id", uuid4())
        values.setdefault("duration_ms", None)
        values.setdefault("failure_signature", None)
        key = (values["workflow_run_id"], values["test_identity_id"])
        unique_results.setdefault(key, values)

    if not unique_results:
        return 0

    statement = (
        insert(TestResult)
        .values(list(unique_results.values()))
        .on_conflict_do_nothing(
            index_elements=[TestResult.workflow_run_id, TestResult.test_identity_id]
        )
        .returning(TestResult.id)
    )
    return len(session.scalars(statement).all())


def get_historical_results(
    session: Session,
    test_identity_id: UUID,
    *,
    limit: int | None = None,
) -> list[TestResult]:
    statement = (
        select(TestResult)
        .join(WorkflowRun, TestResult.workflow_run_id == WorkflowRun.id)
        .where(TestResult.test_identity_id == test_identity_id)
        .order_by(
            WorkflowRun.started_at.desc().nulls_last(),
            WorkflowRun.created_at.desc(),
            TestResult.id,
        )
    )
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        statement = statement.limit(limit)
    return list(session.scalars(statement))
