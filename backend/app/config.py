"""Centralized configuration loaded from environment / .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env sitting next to the backend root (backend/.env)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # Optional regex to also allow origins (e.g. Vercel preview URLs):
    #   CORS_ORIGIN_REGEX=https://.*\.vercel\.app
    CORS_ORIGIN_REGEX: str = os.getenv("CORS_ORIGIN_REGEX", "")

    UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "./uploads")
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "./outputs")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))

    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "12"))

    def ensure_dirs(self) -> None:
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
