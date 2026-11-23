"""Pydantic request/response models (also drive the OpenAPI documentation)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from healthmisinfo.labels import LABEL_NAMES

Lang = Literal["ar", "en"]


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    reviewer_code: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    role: Literal["admin", "reviewer", "researcher"] = "researcher"


class UserUpdate(BaseModel):
    role: Literal["admin", "reviewer", "researcher"] | None = None
    is_active: bool | None = None
    display_name: str | None = Field(default=None, max_length=120)


class AnalyzeIn(BaseModel):
    text: str = Field(description="Health claim to analyse (Arabic or English).", max_length=20000)
    model: Literal["auto", "ar", "en"] = Field("auto", description="auto = choose by detected language")
    explain: bool = True


class LanguageInfo(BaseModel):
    detected: str
    confidence: float
    used: str | None
    details: dict


class PredictionOut(BaseModel):
    label: int
    label_name: str
    display_label: str
    raw_scores: dict[str, float] = Field(description="Uncalibrated softmax scores. NOT a confidence.")
    calibrated_probabilities: dict[str, float] | None = None
    confidence: float | None = Field(None, description="Max calibrated probability; null if the model is uncalibrated.")
    is_calibrated: bool
    abstained: bool
    abstention_threshold: float | None


class AnalysisOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    model_state: str | None = None
    language: LanguageInfo
    warnings: list[str] = []
    model: dict | None = None
    prediction: PredictionOut | None = None
    explanation: dict = {}
    similar_claims: list[dict] = []
    verification_resources: list[dict] = []
    health_topic: str | None = None
    review_status: str
    final_label: int | None = None
    final_label_name: str | None = None
    text: str | None = None
    redactions: dict = {}
    disclaimer: dict[str, str]
    reviews: list[dict] | None = None


class AnalysisSummary(BaseModel):
    id: int
    created_at: datetime
    status: str
    language_detected: str
    language_used: str | None
    predicted_label_name: str | None
    confidence: float | None
    is_calibrated: bool
    abstained: bool
    review_status: str
    final_label_name: str | None
    model_version: str | None
    text_preview: str | None


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class ReviewIn(BaseModel):
    target_type: Literal["analysis", "sample"]
    target_id: int = Field(gt=0)
    label: Literal["SUPPORTED", "MISLEADING", "NEEDS_REVIEW"]
    evidence_urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)
    is_adjudication: bool = False
    guideline_version: str = Field("guidelines-v1", max_length=32)

    @field_validator("evidence_urls")
    @classmethod
    def _https_only(cls, v):
        for u in v:
            if u.scheme not in ("http", "https"):
                raise ValueError("evidence URLs must be http(s)")
        return v


class ReviewOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    reviewer_code: str
    label_name: str
    agrees_with_model: bool | None
    evidence_urls: list[str]
    notes: str | None
    is_adjudication: bool
    created_at: datetime
    target_review_status: str | None = None
    target_final_label_name: str | None = None


class SourceUpdate(BaseModel):
    license_status: Literal["verified", "unclear_needs_review", "unknown", "not_a_dataset"]
    license_evidence: str = Field(min_length=10, max_length=4000, description="What was checked and where.")


class SplitIn(BaseModel):
    language: Lang
    version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    dataset_ids: list[int] | None = None
    seed: int = 42
    require_human_review: bool = False
    near_dup_threshold: float = Field(0.85, ge=0.5, le=1.0)
    label_scheme: Literal["three_class", "binary"] = "three_class"


class QueueReviewIn(BaseModel):
    count: int = Field(50, ge=1, le=2000)
    seed: int = 42
    only_eligible: bool = True


class SettingsUpdate(BaseModel):
    reviews_required: int | None = Field(None, ge=1, le=5)
    store_analysis_text: bool | None = None
    auto_queue_abstained: bool | None = None
    auto_queue_needs_review: bool | None = None


def label_name(v: int | None) -> str | None:
    return None if v is None else LABEL_NAMES[v]
