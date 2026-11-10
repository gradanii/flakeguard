"""Create the initial tenant-scoped domain schema.

Revision ID: 0002_domain_schema
Revises: 0001_m0_baseline
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_domain_schema"
down_revision: str | None = "0001_m0_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_nonempty"),
        sa.CheckConstraint(
            "length(slug) > 0 AND slug = lower(slug)", name="ck_organizations_slug_lower"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("repository_owner", sa.String(length=100), nullable=False),
        sa.Column("repository_name", sa.String(length=100), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_nonempty"),
        sa.CheckConstraint(
            "length(trim(default_branch)) > 0", name="ck_projects_default_branch_nonempty"
        ),
        sa.CheckConstraint(
            "length(repository_owner) > 0 AND repository_owner = lower(repository_owner) "
            "AND repository_owner = trim(repository_owner)",
            name="ck_projects_repository_owner_lower",
        ),
        sa.CheckConstraint(
            "length(repository_name) > 0 AND repository_name = lower(repository_name) "
            "AND repository_name = trim(repository_name)",
            name="ck_projects_repository_name_lower",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_projects_organization_id_organizations", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint(
            "organization_id", "repository_owner", "repository_name", name="uq_projects_repository"
        ),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_run_id", sa.String(length=128), nullable=False),
        sa.Column("run_attempt", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("conclusion", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("run_attempt > 0", name="ck_workflow_runs_attempt_positive"),
        sa.CheckConstraint(
            "length(external_run_id) > 0", name="ck_workflow_runs_external_id_nonempty"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'in_progress', 'completed', 'waiting', 'requested', 'pending')",
            name="ck_workflow_runs_status",
        ),
        sa.CheckConstraint(
            "conclusion IS NULL OR conclusion IN "
            "('success', 'failure', 'cancelled', 'skipped', 'timed_out', "
            "'action_required', 'neutral', 'stale', 'startup_failure')",
            name="ck_workflow_runs_conclusion",
        ),
        sa.CheckConstraint(
            "conclusion IS NULL OR status = 'completed'",
            name="ck_workflow_runs_conclusion_after_completion",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at",
            name="ck_workflow_runs_time_order",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_workflow_runs_project_id_projects", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
        sa.UniqueConstraint("id", "project_id", name="uq_workflow_runs_id_project"),
        sa.UniqueConstraint(
            "project_id", "external_run_id", "run_attempt", name="uq_workflow_runs_external_attempt"
        ),
    )
    op.create_index("ix_workflow_runs_project_started_at", "workflow_runs", ["project_id", "started_at"])
    op.create_table(
        "test_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("framework", sa.String(length=16), nullable=False),
        sa.Column("canonical_fingerprint", sa.String(length=512), nullable=False),
        sa.Column("original_identifier", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("class_name", sa.Text(), nullable=True),
        sa.Column("test_name", sa.Text(), nullable=False),
        sa.Column("parameter_identifier", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("framework IN ('pytest', 'jest')", name="ck_test_identities_framework"),
        sa.CheckConstraint(
            "length(canonical_fingerprint) > 0", name="ck_test_identities_fingerprint_nonempty"
        ),
        sa.CheckConstraint("length(test_name) > 0", name="ck_test_identities_test_name_nonempty"),
        sa.CheckConstraint("last_seen_at >= first_seen_at", name="ck_test_identities_seen_order"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_test_identities_project_id_projects", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_identities"),
        sa.UniqueConstraint("id", "project_id", name="uq_test_identities_id_project"),
        sa.UniqueConstraint(
            "project_id", "framework", "canonical_fingerprint", name="uq_test_identities_fingerprint"
        ),
    )
    op.create_table(
        "test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("failure_signature", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed', 'skipped', 'error')", name="ck_test_results_outcome"
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_test_results_duration_nonnegative"),
        sa.CheckConstraint(
            "failure_signature IS NULL OR failure_signature ~ '^[0-9a-f]{64}$'",
            name="ck_test_results_failure_signature_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_test_results_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id", "project_id"],
            ["workflow_runs.id", "workflow_runs.project_id"],
            name="fk_test_results_workflow_run_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["test_identity_id", "project_id"],
            ["test_identities.id", "test_identities.project_id"],
            name="fk_test_results_identity_project",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_results"),
        sa.UniqueConstraint("workflow_run_id", "test_identity_id", name="uq_test_results_run_identity"),
    )
    op.create_index("ix_test_results_identity_run", "test_results", ["test_identity_id", "workflow_run_id"])
    op.create_index("ix_test_results_project_id", "test_results", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_test_results_project_id", table_name="test_results")
    op.drop_index("ix_test_results_identity_run", table_name="test_results")
    op.drop_table("test_results")
    op.drop_table("test_identities")
    op.drop_index("ix_workflow_runs_project_started_at", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_table("projects")
    op.drop_table("organizations")
