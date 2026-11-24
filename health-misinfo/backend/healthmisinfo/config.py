"""Application settings, read from environment variables (prefix ``HMD_``) or ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../health-misinfo


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HMD_", env_file=".env", extra="ignore")

    environment: str = Field("development", description="development | test | production")
    database_url: str = Field(
        f"sqlite:///{PROJECT_ROOT / 'backend' / 'healthmisinfo_dev.db'}",
        description="SQLAlchemy URL. Use postgresql+psycopg://... in production.",
    )
    secret_key: str = Field("", description="JWT signing key. REQUIRED outside development/test.")
    access_token_minutes: int = 8 * 60
    cookie_name: str = "hmd_session"
    cookie_secure: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Input limits
    min_text_chars: int = 10
    max_text_chars: int = 2000
    max_upload_mb: int = 50

    # Rate limiting (requests per window, per client)
    rate_limit_analyze: int = 30
    rate_limit_login: int = 10
    rate_limit_window_seconds: int = 60

    # Paths
    registry_dir: Path = PROJECT_ROOT / "data" / "registry"
    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"
    pdf_font_path: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

    # Privacy
    store_analysis_text: bool = True
    audit_ip_salt: str = Field("", description="Salt for hashing client IPs in audit logs.")

    # Public mode: anonymous visitors may view the dashboard, analyze claims, browse datasets,
    # analytics and public reports. Reviews, imports and administration always require sign-in.
    public_mode: bool = False

    # Review workflow
    reviews_required: int = 2

    # Dataset target (a target, not an assumed quantity)
    target_samples_per_language: int = 3000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def effective_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.environment in {"development", "test"}:
            # Deterministic, clearly-insecure dev key; refused in production.
            return "dev-only-insecure-key-change-me-0123456789abcdef"
        raise RuntimeError("HMD_SECRET_KEY must be set in production")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production:
        if not s.secret_key or len(s.secret_key) < 32:
            raise RuntimeError("HMD_SECRET_KEY must be at least 32 characters in production")
        if "*" in s.cors_origins:
            raise RuntimeError("Wildcard CORS origin is not allowed in production")
    return s
