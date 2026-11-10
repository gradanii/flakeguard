from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.failure_signature import failure_signature_from_normalized
from app.models import (
    Organization,
    Project,
    WorkflowRun,
)
from app.models import (
    TestIdentity as DomainTestIdentity,
)
from app.models import (
    TestResult as DomainTestResult,
)
from app.repositories import (
    create_organization,
    create_project,
    get_historical_results,
    get_or_create_test_identity,
    get_or_create_workflow_run,
    get_projects_for_organization,
    persist_test_results,
)


def make_project(session: Session) -> Project:
    organization = create_organization(session, name="Example Org", slug=f"example-{uuid4().hex}")
    return create_project(
        session,
        organization_id=organization.id,
        name="Example Project",
        repository_owner="ExampleOwner",
        repository_name="ExampleRepo",
        default_branch="main",
    )


def make_workflow_run(
    session: Session, project_id, *, attempt: int = 1, started_at: datetime | None = None
) -> WorkflowRun:
    return get_or_create_workflow_run(
        session,
        project_id=project_id,
        external_run_id="9001",
        run_attempt=attempt,
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        status="in_progress",
        started_at=started_at,
    )


def make_identity(
    session: Session, project_id, *, fingerprint: str = "fingerprint-1"
) -> DomainTestIdentity:
    now = datetime.now(UTC)
    return get_or_create_test_identity(
        session,
        project_id=project_id,
        framework="pytest",
        canonical_fingerprint=fingerprint,
        original_identifier="tests/test_example.py::test_example",
        file_path="tests/test_example.py",
        test_name="test_example",
        first_seen_at=now,
        last_seen_at=now,
    )


def test_model_creation_and_repository_normalization(db_session: Session) -> None:
    project = make_project(db_session)
    db_session.flush()

    assert project.organization.name == "Example Org"
    assert project.repository_owner == "exampleowner"
    assert project.repository_name == "examplerepo"
    assert project.created_at.tzinfo is not None
    assert project.updated_at.tzinfo is not None


def test_foreign_key_integrity_and_database_case_protection(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        create_project(
            db_session,
            organization_id=uuid4(),
            name="Orphan",
            repository_owner="owner",
            repository_name="repo",
            default_branch="main",
        )

    db_session.rollback()
    organization = create_organization(db_session, name="Org", slug=f"org-{uuid4().hex}")
    db_session.add(
        Project(
            organization_id=organization.id,
            name="Mixed case direct insert",
            repository_owner="NotNormalized",
            repository_name="repo",
            default_branch="main",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_project_repository_is_unique_within_organization(db_session: Session) -> None:
    project = make_project(db_session)
    with pytest.raises(IntegrityError):
        create_project(
            db_session,
            organization_id=project.organization_id,
            name="Second project for same repo",
            repository_owner="EXAMPLEOWNER",
            repository_name="EXAMPLEREPO",
            default_branch="main",
        )


def test_workflow_rerun_attempts_are_distinct_and_identity_is_unique(db_session: Session) -> None:
    project = make_project(db_session)
    first_attempt = make_workflow_run(db_session, project.id, attempt=1)
    rerun = make_workflow_run(db_session, project.id, attempt=2)
    duplicate = make_workflow_run(db_session, project.id, attempt=1)

    assert first_attempt.id != rerun.id
    assert duplicate.id == first_attempt.id

    db_session.add(
        WorkflowRun(
            project_id=project.id,
            external_run_id="9001",
            run_attempt=1,
            commit_sha="b" * 40,
            branch="main",
            workflow_name="Different payload",
            status="queued",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_workflow_conclusion_is_separate_and_gated_by_completion(db_session: Session) -> None:
    project = make_project(db_session)
    run = make_workflow_run(db_session, project.id)
    assert run.conclusion is None

    run.conclusion = "success"
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_test_identity_uniqueness_and_seen_range_updates(db_session: Session) -> None:
    project = make_project(db_session)
    first_seen = datetime.now(UTC) - timedelta(days=1)
    last_seen = datetime.now(UTC)
    identity = get_or_create_test_identity(
        db_session,
        project_id=project.id,
        framework="PYTEST",
        canonical_fingerprint="same-test",
        original_identifier="tests/a.py::test_a",
        test_name="test_a",
        first_seen_at=first_seen,
        last_seen_at=first_seen,
    )
    duplicate = get_or_create_test_identity(
        db_session,
        project_id=project.id,
        framework="pytest",
        canonical_fingerprint="same-test",
        original_identifier="tests/a.py::test_a",
        test_name="test_a",
        first_seen_at=first_seen,
        last_seen_at=last_seen,
    )

    assert duplicate.id == identity.id
    assert duplicate.last_seen_at == last_seen

    db_session.add(
        DomainTestIdentity(
            project_id=project.id,
            framework="pytest",
            canonical_fingerprint="same-test",
            original_identifier="other identifier",
            test_name="test_a",
            first_seen_at=first_seen,
            last_seen_at=last_seen,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_result_idempotency_and_historical_retrieval(db_session: Session) -> None:
    project = make_project(db_session)
    identity = make_identity(db_session, project.id)
    earlier = datetime.now(UTC) - timedelta(hours=1)
    run_1 = make_workflow_run(db_session, project.id, attempt=1, started_at=earlier)
    run_2 = get_or_create_workflow_run(
        db_session,
        project_id=project.id,
        external_run_id="9002",
        run_attempt=1,
        commit_sha="b" * 40,
        branch="main",
        workflow_name="CI",
        status="completed",
        conclusion="failure",
        started_at=datetime.now(UTC),
    )
    rows = [
        {
            "project_id": project.id,
            "workflow_run_id": run_1.id,
            "test_identity_id": identity.id,
            "outcome": "passed",
            "duration_ms": 15.125,
        },
        {
            "project_id": project.id,
            "workflow_run_id": run_2.id,
            "test_identity_id": identity.id,
            "outcome": "failed",
            "failure_signature": failure_signature_from_normalized("AssertionError|expected!=actual"),
        },
    ]

    assert persist_test_results(db_session, rows) == 2
    assert persist_test_results(db_session, rows) == 0
    history = get_historical_results(db_session, identity.id)
    assert [item.workflow_run_id for item in history] == [run_2.id, run_1.id]
    assert get_historical_results(db_session, identity.id, limit=1) == history[:1]


def test_result_foreign_keys_reject_cross_project_pairs(db_session: Session) -> None:
    project_a = make_project(db_session)
    project_b = create_project(
        db_session,
        organization_id=project_a.organization_id,
        name="Another project",
        repository_owner="other-owner",
        repository_name="other-repo",
        default_branch="main",
    )
    run = make_workflow_run(db_session, project_a.id)
    identity = make_identity(db_session, project_b.id)
    db_session.add(
        DomainTestResult(
            project_id=project_a.id,
            workflow_run_id=run.id,
            test_identity_id=identity.id,
            outcome="passed",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_projects_are_isolated_by_organization(db_session: Session) -> None:
    project = make_project(db_session)
    other_organization = create_organization(db_session, name="Other", slug=f"other-{uuid4().hex}")
    other_project = create_project(
        db_session,
        organization_id=other_organization.id,
        name="Other project",
        repository_owner="owner",
        repository_name="repo",
        default_branch="main",
    )

    assert get_projects_for_organization(db_session, project.organization_id) == [project]
    assert get_projects_for_organization(db_session, other_organization.id) == [other_project]


def test_failure_signature_hashes_normalized_input_only() -> None:
    assert failure_signature_from_normalized("AssertionError|expected!=actual") == (
        failure_signature_from_normalized("AssertionError|expected!=actual")
    )
    with pytest.raises(ValueError):
        failure_signature_from_normalized("  ")


def test_concurrent_get_or_create_and_result_writes_are_safe(postgres_engine) -> None:
    organization_id = uuid4()
    project_id = uuid4()
    slug = f"concurrent-{uuid4().hex}"
    started_at = datetime.now(UTC)

    with Session(postgres_engine) as setup:
        organization = Organization(id=organization_id, name="Concurrent", slug=slug)
        project = Project(
            id=project_id,
            organization=organization,
            name="Concurrent project",
            repository_owner="concurrent-owner",
            repository_name=uuid4().hex,
            default_branch="main",
        )
        setup.add(project)
        setup.commit()

    barrier = Barrier(4)

    def get_or_create(_: int):
        with Session(postgres_engine) as session:
            barrier.wait()
            run = get_or_create_workflow_run(
                session,
                project_id=project_id,
                external_run_id="concurrent-run",
                run_attempt=1,
                commit_sha="c" * 40,
                branch="main",
                workflow_name="CI",
                status="in_progress",
            )
            identity = get_or_create_test_identity(
                session,
                project_id=project_id,
                framework="jest",
                canonical_fingerprint="concurrent-test",
                original_identifier="tests/a.test.js test a",
                test_name="test a",
                first_seen_at=started_at,
                last_seen_at=started_at,
            )
            session.commit()
            return run.id, identity.id

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            identities = list(executor.map(get_or_create, range(4)))
        assert len({run_id for run_id, _ in identities}) == 1
        assert len({identity_id for _, identity_id in identities}) == 1
        resolved_run_id, resolved_identity_id = identities[0]
        result_barrier = Barrier(4)

        def persist_once(_: int) -> int:
            with Session(postgres_engine) as session:
                result_barrier.wait()
                inserted = persist_test_results(
                    session,
                    [
                        {
                            "project_id": project_id,
                            "workflow_run_id": resolved_run_id,
                            "test_identity_id": resolved_identity_id,
                            "outcome": "passed",
                        }
                    ],
                )
                session.commit()
                return inserted

        with ThreadPoolExecutor(max_workers=4) as executor:
            inserted_counts = list(executor.map(persist_once, range(4)))
        assert sum(inserted_counts) == 1
    finally:
        with Session(postgres_engine) as cleanup:
            cleanup.execute(delete(DomainTestResult).where(DomainTestResult.project_id == project_id))
            cleanup.execute(delete(DomainTestIdentity).where(DomainTestIdentity.project_id == project_id))
            cleanup.execute(delete(WorkflowRun).where(WorkflowRun.project_id == project_id))
            cleanup.execute(delete(Project).where(Project.id == project_id))
            cleanup.execute(delete(Organization).where(Organization.id == organization_id))
            cleanup.commit()
