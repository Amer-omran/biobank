"""SQLAlchemy ORM models. Schema changes MUST go through an Alembic migration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")
# BigInteger autoincrement does not work on SQLite; use INTEGER there.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


ROLES = ("admin", "reviewer", "researcher")
LABEL_CHECK = "IN (0, 1, 2)"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    reviewer_code: Mapped[str] = mapped_column(String(16), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="researcher")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceRegistry(Base):
    __tablename__ = "source_registry"
    __table_args__ = (
        CheckConstraint(
            "license_status IN ('verified', 'unclear_needs_review', 'unknown', 'not_a_dataset')",
            name="ck_source_license_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    languages: Mapped[list] = mapped_column(JSONType, default=list)
    official_url: Mapped[str | None] = mapped_column(Text)
    paper_url: Mapped[str | None] = mapped_column(Text)
    access_method: Mapped[str | None] = mapped_column(Text)
    verified_revision: Mapped[str | None] = mapped_column(String(64))
    license_name: Mapped[str | None] = mapped_column(String(255))
    license_url: Mapped[str | None] = mapped_column(Text)
    license_evidence: Mapped[str | None] = mapped_column(Text)
    license_status: Mapped[str] = mapped_column(String(32), default="unknown")
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean)
    redistribution_allowed: Mapped[str | None] = mapped_column(Text)
    attribution_required: Mapped[bool | None] = mapped_column(Boolean)
    text_available: Mapped[bool] = mapped_column(Boolean, default=False)
    citation: Mapped[str | None] = mapped_column(Text)
    training_use_status: Mapped[str] = mapped_column(String(64), default="unknown")
    notes: Mapped[list] = mapped_column(JSONType, default=list)
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    registry_version: Mapped[str | None] = mapped_column(String(32))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_datasets_name_version"),
        CheckConstraint("kind IN ('import', 'split', 'curated')", name="ck_datasets_kind"),
        Index("ix_datasets_language", "language"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(16), default="import")
    status: Mapped[str] = mapped_column(String(32), default="imported")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_registry.id", ondelete="SET NULL"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    label_mapping_version: Mapped[str | None] = mapped_column(String(64))
    label_mapping_sha256: Mapped[str | None] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict] = mapped_column(JSONType, default=dict)
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[SourceRegistry | None] = relationship()


class DatasetSample(Base):
    __tablename__ = "dataset_samples"
    __table_args__ = (
        UniqueConstraint("dataset_id", "row_number", name="uq_samples_dataset_row"),
        CheckConstraint(f"mapped_label IS NULL OR mapped_label {LABEL_CHECK}", name="ck_samples_mapped_label"),
        CheckConstraint(f"final_label IS NULL OR final_label {LABEL_CHECK}", name="ck_samples_final_label"),
        Index("ix_samples_match_key", "match_key_hash"),
        Index("ix_samples_group", "group_id"),
        Index("ix_samples_review_status", "review_status"),
        Index("ix_samples_lang_elig", "language", "eligibility"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(8))
    text_available: Mapped[bool] = mapped_column(Boolean, default=True)
    original_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    match_key_hash: Mapped[str | None] = mapped_column(String(64))
    original_label: Mapped[str | None] = mapped_column(String(255))
    original_labels: Mapped[dict] = mapped_column(JSONType, default=dict)
    mapped_label: Mapped[int | None] = mapped_column(SmallInteger)
    mapping_status: Mapped[str] = mapped_column(String(40), default="no_label")
    health_topic: Mapped[str | None] = mapped_column(String(64))
    source_category: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(Text)
    evidence_urls: Mapped[list] = mapped_column(JSONType, default=list)
    claim_date: Mapped[str | None] = mapped_column(String(40))
    group_id: Mapped[str | None] = mapped_column(String(64))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_samples.id", ondelete="SET NULL"))
    near_duplicate_score: Mapped[float | None] = mapped_column(Float)
    eligibility: Mapped[str] = mapped_column(String(16), default="pending")
    exclusion_reason: Mapped[str | None] = mapped_column(String(128))
    review_status: Mapped[str] = mapped_column(String(20), default="unreviewed")
    final_label: Mapped[int | None] = mapped_column(SmallInteger)
    final_label_source: Mapped[str | None] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped[Dataset] = relationship()


class SplitAssignment(Base):
    """Membership of a sample in one versioned train/validation/test split (a kind='split' dataset)."""

    __tablename__ = "split_assignments"
    __table_args__ = (
        UniqueConstraint("split_dataset_id", "sample_id", name="uq_split_sample"),
        CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_split_value"),
        Index("ix_split_dataset_split", "split_dataset_id", "split"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    split_dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    sample_id: Mapped[int] = mapped_column(ForeignKey("dataset_samples.id", ondelete="CASCADE"), index=True)
    split: Mapped[str] = mapped_column(String(16))
    group_id: Mapped[str] = mapped_column(String(64))
    label: Mapped[int] = mapped_column(SmallInteger)


class Annotation(Base):
    """Sample-level labels: automated source-label mappings and human annotations."""

    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint("annotator_kind IN ('source_mapping', 'human')", name="ck_annotations_kind"),
        CheckConstraint(f"label IS NULL OR label {LABEL_CHECK}", name="ck_annotations_label"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("dataset_samples.id", ondelete="CASCADE"), index=True)
    annotator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    annotator_kind: Mapped[str] = mapped_column(String(20))
    label: Mapped[int | None] = mapped_column(SmallInteger)
    health_topic: Mapped[str | None] = mapped_column(String(64))
    evidence_urls: Mapped[list] = mapped_column(JSONType, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    guideline_version: Mapped[str | None] = mapped_column(String(32))
    mapping_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("status IN ('registered', 'active', 'retired')", name="ck_model_status"),
        Index("ix_model_versions_lang_status", "language", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_tag: Mapped[str] = mapped_column(String(120), unique=True)
    language: Mapped[str] = mapped_column(String(8))
    base_model: Mapped[str] = mapped_column(String(255))
    checkpoint_path: Mapped[str] = mapped_column(Text)
    checkpoint_sha256: Mapped[str | None] = mapped_column(String(64))
    training_run_id: Mapped[int | None] = mapped_column(ForeignKey("training_runs.id", ondelete="SET NULL"))
    trained_on_dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="registered")
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature: Mapped[float | None] = mapped_column(Float)
    abstention_threshold: Mapped[float | None] = mapped_column(Float)
    val_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    test_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    calibration: Mapped[dict] = mapped_column(JSONType, default=dict)
    model_card_path: Mapped[str | None] = mapped_column(Text)
    registered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrainingRun(Base):
    __tablename__ = "training_runs"
    __table_args__ = (CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="ck_training_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_tag: Mapped[str] = mapped_column(String(120), unique=True)
    language: Mapped[str] = mapped_column(String(8))
    base_model: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    dataset_version: Mapped[str | None] = mapped_column(String(64))
    data_sha256: Mapped[str | None] = mapped_column(String(64))
    hyperparameters: Mapped[dict] = mapped_column(JSONType, default=dict)
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    output_dir: Mapped[str | None] = mapped_column(Text)
    val_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    test_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    environment: Mapped[dict] = mapped_column(JSONType, default=dict)
    git_commit: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(f"predicted_label IS NULL OR predicted_label {LABEL_CHECK}", name="ck_analyses_label"),
        CheckConstraint(f"final_label IS NULL OR final_label {LABEL_CHECK}", name="ck_analyses_final"),
        Index("ix_analyses_created", "created_at"),
        Index("ix_analyses_user_created", "user_id", "created_at"),
        Index("ix_analyses_review_status", "review_status"),
        Index("ix_analyses_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str | None] = mapped_column(Text)  # PII-redacted; may be NULL if storage disabled
    text_sha256: Mapped[str] = mapped_column(String(64))
    text_length: Mapped[int] = mapped_column(Integer)
    redactions: Mapped[dict] = mapped_column(JSONType, default=dict)
    language_detected: Mapped[str] = mapped_column(String(16))
    language_confidence: Mapped[float] = mapped_column(Float)
    language_used: Mapped[str | None] = mapped_column(String(8))
    requested_model: Mapped[str] = mapped_column(String(16), default="auto")
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32))
    predicted_label: Mapped[int | None] = mapped_column(SmallInteger)
    raw_scores: Mapped[list | None] = mapped_column(JSONType)
    calibrated_probabilities: Mapped[list | None] = mapped_column(JSONType)
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[dict] = mapped_column(JSONType, default=dict)
    similar_claims: Mapped[list] = mapped_column(JSONType, default=list)
    health_topic: Mapped[str | None] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(20), default="not_required")
    review_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    final_label: Mapped[int | None] = mapped_column(SmallInteger)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    model_version: Mapped[ModelVersion | None] = relationship()


class ExpertReview(Base):
    __tablename__ = "expert_reviews"
    __table_args__ = (
        CheckConstraint("target_type IN ('analysis', 'sample')", name="ck_reviews_target_type"),
        CheckConstraint(
            "(target_type = 'analysis' AND analysis_id IS NOT NULL AND sample_id IS NULL) OR "
            "(target_type = 'sample' AND sample_id IS NOT NULL AND analysis_id IS NULL)",
            name="ck_reviews_target",
        ),
        CheckConstraint(f"label {LABEL_CHECK}", name="ck_reviews_label"),
        Index("ix_reviews_analysis", "analysis_id"),
        Index("ix_reviews_sample", "sample_id"),
        Index("ix_reviews_reviewer", "reviewer_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(16))
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    sample_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_samples.id", ondelete="CASCADE"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    label: Mapped[int] = mapped_column(SmallInteger)
    agrees_with_model: Mapped[bool | None] = mapped_column(Boolean)
    evidence_urls: Mapped[list] = mapped_column(JSONType, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    is_adjudication: Mapped[bool] = mapped_column(Boolean, default=False)
    guideline_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reviewer: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
        Index("ix_audit_actor", "actor_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONType)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
