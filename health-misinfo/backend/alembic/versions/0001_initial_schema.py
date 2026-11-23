"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-23 15:47:19.123840
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("reviewer_code", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'reviewer', 'researcher')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reviewer_code"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.create_index("ix_audit_actor", ["actor_id"], unique=False)
        batch_op.create_index("ix_audit_created", ["created_at"], unique=False)
        batch_op.create_index("ix_audit_entity", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "source_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("languages", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("paper_url", sa.Text(), nullable=True),
        sa.Column("access_method", sa.Text(), nullable=True),
        sa.Column("verified_revision", sa.String(length=64), nullable=True),
        sa.Column("license_name", sa.String(length=255), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("license_evidence", sa.Text(), nullable=True),
        sa.Column("license_status", sa.String(length=32), nullable=False),
        sa.Column("commercial_use_allowed", sa.Boolean(), nullable=True),
        sa.Column("redistribution_allowed", sa.Text(), nullable=True),
        sa.Column("attribution_required", sa.Boolean(), nullable=True),
        sa.Column("text_available", sa.Boolean(), nullable=False),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("training_use_status", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("details", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("registry_version", sa.String(length=32), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("license_status IN ('verified', 'unclear_needs_review', 'unknown', 'not_a_dataset')", name="ck_source_license_status"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("source_registry", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_source_registry_key"), ["key"], unique=True)

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("label_mapping_version", sa.String(length=64), nullable=True),
        sa.Column("label_mapping_sha256", sa.String(length=64), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("params", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("stats", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('import', 'split', 'curated')", name="ck_datasets_kind"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["source_registry.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_datasets_name_version"),
    )
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.create_index("ix_datasets_language", ["language"], unique=False)

    op.create_table(
        "dataset_samples",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("text_available", sa.Boolean(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("match_key_hash", sa.String(length=64), nullable=True),
        sa.Column("original_label", sa.String(length=255), nullable=True),
        sa.Column("original_labels", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("mapped_label", sa.SmallInteger(), nullable=True),
        sa.Column("mapping_status", sa.String(length=40), nullable=False),
        sa.Column("health_topic", sa.String(length=64), nullable=True),
        sa.Column("source_category", sa.String(length=128), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence_urls", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("claim_date", sa.String(length=40), nullable=True),
        sa.Column("group_id", sa.String(length=64), nullable=True),
        sa.Column("duplicate_of_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("near_duplicate_score", sa.Float(), nullable=True),
        sa.Column("eligibility", sa.String(length=16), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=128), nullable=True),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("final_label", sa.SmallInteger(), nullable=True),
        sa.Column("final_label_source", sa.String(length=32), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("extra", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("final_label IS NULL OR final_label IN (0, 1, 2)", name="ck_samples_final_label"),
        sa.CheckConstraint("mapped_label IS NULL OR mapped_label IN (0, 1, 2)", name="ck_samples_mapped_label"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["dataset_samples.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "row_number", name="uq_samples_dataset_row"),
    )
    with op.batch_alter_table("dataset_samples", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_dataset_samples_dataset_id"), ["dataset_id"], unique=False)
        batch_op.create_index("ix_samples_group", ["group_id"], unique=False)
        batch_op.create_index("ix_samples_lang_elig", ["language", "eligibility"], unique=False)
        batch_op.create_index("ix_samples_match_key", ["match_key_hash"], unique=False)
        batch_op.create_index("ix_samples_review_status", ["review_status"], unique=False)

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_tag", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("base_model", sa.String(length=255), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("data_sha256", sa.String(length=64), nullable=True),
        sa.Column("hyperparameters", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("output_dir", sa.Text(), nullable=True),
        sa.Column("val_metrics", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("test_metrics", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("environment", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("git_commit", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="ck_training_status"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_tag"),
    )
    op.create_table(
        "annotations",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("sample_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("annotator_id", sa.Integer(), nullable=True),
        sa.Column("annotator_kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.SmallInteger(), nullable=True),
        sa.Column("health_topic", sa.String(length=64), nullable=True),
        sa.Column("evidence_urls", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("guideline_version", sa.String(length=32), nullable=True),
        sa.Column("mapping_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("annotator_kind IN ('source_mapping', 'human')", name="ck_annotations_kind"),
        sa.CheckConstraint("label IS NULL OR label IN (0, 1, 2)", name="ck_annotations_label"),
        sa.ForeignKeyConstraint(["annotator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sample_id"], ["dataset_samples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("annotations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_annotations_sample_id"), ["sample_id"], unique=False)

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_tag", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("base_model", sa.String(length=255), nullable=False),
        sa.Column("checkpoint_path", sa.Text(), nullable=False),
        sa.Column("checkpoint_sha256", sa.String(length=64), nullable=True),
        sa.Column("training_run_id", sa.Integer(), nullable=True),
        sa.Column("trained_on_dataset_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_calibrated", sa.Boolean(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("abstention_threshold", sa.Float(), nullable=True),
        sa.Column("val_metrics", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("test_metrics", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("calibration", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("model_card_path", sa.Text(), nullable=True),
        sa.Column("registered_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('registered', 'active', 'retired')", name="ck_model_status"),
        sa.ForeignKeyConstraint(["registered_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trained_on_dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["training_run_id"], ["training_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_tag"),
    )
    with op.batch_alter_table("model_versions", schema=None) as batch_op:
        batch_op.create_index("ix_model_versions_lang_status", ["language", "status"], unique=False)

    op.create_table(
        "split_assignments",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("split_dataset_id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("split", sa.String(length=16), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_split_value"),
        sa.ForeignKeyConstraint(["sample_id"], ["dataset_samples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["split_dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("split_dataset_id", "sample_id", name="uq_split_sample"),
    )
    with op.batch_alter_table("split_assignments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_split_assignments_sample_id"), ["sample_id"], unique=False)
        batch_op.create_index("ix_split_dataset_split", ["split_dataset_id", "split"], unique=False)

    op.create_table(
        "analyses",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("text_length", sa.Integer(), nullable=False),
        sa.Column("redactions", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("language_detected", sa.String(length=16), nullable=False),
        sa.Column("language_confidence", sa.Float(), nullable=False),
        sa.Column("language_used", sa.String(length=8), nullable=True),
        sa.Column("requested_model", sa.String(length=16), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("predicted_label", sa.SmallInteger(), nullable=True),
        sa.Column("raw_scores", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("calibrated_probabilities", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("is_calibrated", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("abstained", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("similar_claims", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("health_topic", sa.String(length=64), nullable=True),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("review_requested", sa.Boolean(), nullable=False),
        sa.Column("final_label", sa.SmallInteger(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("final_label IS NULL OR final_label IN (0, 1, 2)", name="ck_analyses_final"),
        sa.CheckConstraint("predicted_label IS NULL OR predicted_label IN (0, 1, 2)", name="ck_analyses_label"),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("analyses", schema=None) as batch_op:
        batch_op.create_index("ix_analyses_created", ["created_at"], unique=False)
        batch_op.create_index("ix_analyses_review_status", ["review_status"], unique=False)
        batch_op.create_index("ix_analyses_status", ["status"], unique=False)
        batch_op.create_index("ix_analyses_user_created", ["user_id", "created_at"], unique=False)

    op.create_table(
        "expert_reviews",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("analysis_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("sample_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.SmallInteger(), nullable=False),
        sa.Column("agrees_with_model", sa.Boolean(), nullable=True),
        sa.Column("evidence_urls", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_adjudication", sa.Boolean(), nullable=False),
        sa.Column("guideline_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(target_type = 'analysis' AND analysis_id IS NOT NULL AND sample_id IS NULL) OR (target_type = 'sample' AND sample_id IS NOT NULL AND analysis_id IS NULL)",
            name="ck_reviews_target",
        ),
        sa.CheckConstraint("target_type IN ('analysis', 'sample')", name="ck_reviews_target_type"),
        sa.CheckConstraint("label IN (0, 1, 2)", name="ck_reviews_label"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sample_id"], ["dataset_samples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("expert_reviews", schema=None) as batch_op:
        batch_op.create_index("ix_reviews_analysis", ["analysis_id"], unique=False)
        batch_op.create_index("ix_reviews_reviewer", ["reviewer_id"], unique=False)
        batch_op.create_index("ix_reviews_sample", ["sample_id"], unique=False)


def downgrade() -> None:

    with op.batch_alter_table("expert_reviews", schema=None) as batch_op:
        batch_op.drop_index("ix_reviews_sample")
        batch_op.drop_index("ix_reviews_reviewer")
        batch_op.drop_index("ix_reviews_analysis")

    op.drop_table("expert_reviews")
    with op.batch_alter_table("analyses", schema=None) as batch_op:
        batch_op.drop_index("ix_analyses_user_created")
        batch_op.drop_index("ix_analyses_status")
        batch_op.drop_index("ix_analyses_review_status")
        batch_op.drop_index("ix_analyses_created")

    op.drop_table("analyses")
    with op.batch_alter_table("split_assignments", schema=None) as batch_op:
        batch_op.drop_index("ix_split_dataset_split")
        batch_op.drop_index(batch_op.f("ix_split_assignments_sample_id"))

    op.drop_table("split_assignments")
    with op.batch_alter_table("model_versions", schema=None) as batch_op:
        batch_op.drop_index("ix_model_versions_lang_status")

    op.drop_table("model_versions")
    with op.batch_alter_table("annotations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_annotations_sample_id"))

    op.drop_table("annotations")
    op.drop_table("training_runs")
    with op.batch_alter_table("dataset_samples", schema=None) as batch_op:
        batch_op.drop_index("ix_samples_review_status")
        batch_op.drop_index("ix_samples_match_key")
        batch_op.drop_index("ix_samples_lang_elig")
        batch_op.drop_index("ix_samples_group")
        batch_op.drop_index(batch_op.f("ix_dataset_samples_dataset_id"))

    op.drop_table("dataset_samples")
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_index("ix_datasets_language")

    op.drop_table("datasets")
    with op.batch_alter_table("source_registry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_source_registry_key"))

    op.drop_table("source_registry")
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_entity")
        batch_op.drop_index("ix_audit_created")
        batch_op.drop_index("ix_audit_actor")

    op.drop_table("audit_logs")
    op.drop_table("app_settings")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")
