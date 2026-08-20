"""Application configuration via Pydantic Settings.

Validates the environment at startup (fail-fast) instead of discovering a
missing/invalid value on the first request. Import ``settings`` anywhere.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Anthropic ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")
    # Per-1M-token USD prices used to estimate cost (override for other models).
    price_input_per_mtok: float = Field(default=3.0, alias="PRICE_INPUT_PER_MTOK")
    price_output_per_mtok: float = Field(default=15.0, alias="PRICE_OUTPUT_PER_MTOK")

    # --- Server ---
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS"
    )
    cors_origin_regex: str = Field(default="", alias="CORS_ORIGIN_REGEX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Auth / limits ---
    # If set, callers must send `Authorization: Bearer <token>` (or X-API-Key).
    # Empty = open (local dev).
    api_auth_token: str = Field(default="", alias="API_AUTH_TOKEN")
    rate_limit: str = Field(default="20/minute", alias="RATE_LIMIT")
    max_concurrent_jobs: int = Field(default=4, alias="MAX_CONCURRENT_JOBS")

    # --- Files ---
    upload_dir: Path = Field(default=BASE_DIR / "uploads", alias="UPLOAD_DIR")
    output_dir: Path = Field(default=BASE_DIR / "outputs", alias="OUTPUT_DIR")
    db_path: Path = Field(default=BASE_DIR / "jobs.db", alias="DB_PATH")
    # If set, jobs are stored in PostgreSQL instead of SQLite. Railway's Postgres
    # plugin injects DATABASE_URL automatically. Needed for multi-replica deploys;
    # for a single instance, pointing DB_PATH at a mounted volume is enough.
    database_url: str = Field(default="", alias="DATABASE_URL")
    max_file_size: int = Field(default=50 * 1024 * 1024, alias="MAX_FILE_SIZE")
    max_rows: int = Field(default=1_000_000, alias="MAX_ROWS")
    # Rows above this are randomly sampled before analysis to bound memory/latency.
    sample_over_rows: int = Field(default=200_000, alias="SAMPLE_OVER_ROWS")

    # --- Agent ---
    max_iterations: int = Field(default=12, alias="MAX_ITERATIONS")
    job_timeout_seconds: int = Field(default=180, alias="JOB_TIMEOUT_SECONDS")
    anthropic_max_retries: int = Field(default=4, alias="ANTHROPIC_MAX_RETRIES")
    job_ttl_seconds: int = Field(default=24 * 3600, alias="JOB_TTL_SECONDS")

    @field_validator("upload_dir", "output_dir", "db_path", mode="before")
    @classmethod
    def _resolve_path(cls, v: str | Path) -> Path:
        p = Path(v)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_auth_token)

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def cost_usd(self, input_tokens: float, output_tokens: float) -> float:
        return round(
            input_tokens / 1e6 * self.price_input_per_mtok
            + output_tokens / 1e6 * self.price_output_per_mtok,
            6,
        )


settings = Settings()
