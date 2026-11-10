from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_nonempty"),
        CheckConstraint("length(slug) > 0 AND slug = lower(slug)", name="ck_organizations_slug_lower"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    projects: Mapped[list[Project]] = relationship(
        back_populates="organization", passive_deletes="all"
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "repository_owner", "repository_name", name="uq_projects_repository"
        ),
        CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_nonempty"),
        CheckConstraint(
            "length(trim(default_branch)) > 0", name="ck_projects_default_branch_nonempty"
        ),
        CheckConstraint(
            "length(repository_owner) > 0 AND repository_owner = lower(repository_owner) "
            "AND repository_owner = trim(repository_owner)",
            name="ck_projects_repository_owner_lower",
        ),
        CheckConstraint(
            "length(repository_name) > 0 AND repository_name = lower(repository_name) "
            "AND repository_name = trim(repository_name)",
            name="ck_projects_repository_name_lower",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    repository_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repository_name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    workflow_runs: Mapped[list[WorkflowRun]] = relationship(
        back_populates="project", passive_deletes="all"
    )
    test_identities: Mapped[list[TestIdentity]] = relationship(
        back_populates="project", passive_deletes="all"
    )
    test_results: Mapped[list[TestResult]] = relationship(
        back_populates="project", foreign_keys="TestResult.project_id", passive_deletes="all"
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "external_run_id", "run_attempt", name="uq_workflow_runs_external_attempt"
        ),
        UniqueConstraint("id", "project_id", name="uq_workflow_runs_id_project"),
        CheckConstraint("run_attempt > 0", name="ck_workflow_runs_attempt_positive"),
        CheckConstraint("length(external_run_id) > 0", name="ck_workflow_runs_external_id_nonempty"),
        CheckConstraint(
            "status IN ('queued', 'in_progress', 'completed', 'waiting', 'requested', 'pending')",
            name="ck_workflow_runs_status",
        ),
        CheckConstraint(
            "conclusion IS NULL OR conclusion IN "
            "('success', 'failure', 'cancelled', 'skipped', 'timed_out', "
            "'action_required', 'neutral', 'stale', 'startup_failure')",
            name="ck_workflow_runs_conclusion",
        ),
        CheckConstraint(
            "conclusion IS NULL OR status = 'completed'", name="ck_workflow_runs_conclusion_after_completion"
        ),
        CheckConstraint(
            "started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at",
            name="ck_workflow_runs_time_order",
        ),
        Index("ix_workflow_runs_project_started_at", "project_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    external_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_attempt: Mapped[int] = mapped_column(nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    conclusion: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="workflow_runs")
    test_results: Mapped[list[TestResult]] = relationship(
        back_populates="workflow_run", foreign_keys="TestResult.workflow_run_id", passive_deletes="all"
    )


class TestIdentity(TimestampMixin, Base):
    __tablename__ = "test_identities"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "framework", "canonical_fingerprint", name="uq_test_identities_fingerprint"
        ),
        UniqueConstraint("id", "project_id", name="uq_test_identities_id_project"),
        CheckConstraint("framework IN ('pytest', 'jest')", name="ck_test_identities_framework"),
        CheckConstraint(
            "length(canonical_fingerprint) > 0", name="ck_test_identities_fingerprint_nonempty"
        ),
        CheckConstraint("length(test_name) > 0", name="ck_test_identities_test_name_nonempty"),
        CheckConstraint("last_seen_at >= first_seen_at", name="ck_test_identities_seen_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    framework: Mapped[str] = mapped_column(String(16), nullable=False)
    canonical_fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)
    original_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    class_name: Mapped[str | None] = mapped_column(Text)
    test_name: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_identifier: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Project] = relationship(back_populates="test_identities")
    test_results: Mapped[list[TestResult]] = relationship(
        back_populates="test_identity", foreign_keys="TestResult.test_identity_id", passive_deletes="all"
    )


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "test_identity_id", name="uq_test_results_run_identity"),
        ForeignKeyConstraint(
            ["workflow_run_id", "project_id"],
            ["workflow_runs.id", "workflow_runs.project_id"],
            ondelete="RESTRICT",
            name="fk_test_results_workflow_run_project",
        ),
        ForeignKeyConstraint(
            ["test_identity_id", "project_id"],
            ["test_identities.id", "test_identities.project_id"],
            ondelete="RESTRICT",
            name="fk_test_results_identity_project",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="RESTRICT", name="fk_test_results_project"
        ),
        CheckConstraint(
            "outcome IN ('passed', 'failed', 'skipped', 'error')", name="ck_test_results_outcome"
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_test_results_duration_nonnegative"),
        CheckConstraint(
            "failure_signature IS NULL OR failure_signature ~ '^[0-9a-f]{64}$'",
            name="ck_test_results_failure_signature_sha256",
        ),
        Index("ix_test_results_identity_run", "test_identity_id", "workflow_run_id"),
        Index("ix_test_results_project_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(nullable=False)
    test_identity_id: Mapped[UUID] = mapped_column(nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    failure_signature: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[Project] = relationship(
        back_populates="test_results", foreign_keys=[project_id], overlaps="test_results"
    )
    workflow_run: Mapped[WorkflowRun] = relationship(
        back_populates="test_results", foreign_keys=[workflow_run_id], overlaps="project,test_results"
    )
    test_identity: Mapped[TestIdentity] = relationship(
        back_populates="test_results", foreign_keys=[test_identity_id], overlaps="project,test_results"
    )
