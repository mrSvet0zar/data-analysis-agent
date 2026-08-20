"""Pytest fixtures. Env is set BEFORE importing the app so config is isolated."""

import os
import tempfile
from pathlib import Path

# Isolate config from the real .env: dummy key + temp DB, set before any app import.
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-dummy"
os.environ["DB_PATH"] = str(Path(tempfile.gettempdir()) / "agent_test_jobs.db")
os.environ["API_AUTH_TOKEN"] = ""  # open by default in tests

import pytest  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


@pytest.fixture
def sales_csv() -> str:
    return str(SAMPLE_DIR / "sales.csv")


@pytest.fixture
def tmp_csv(tmp_path) -> str:
    p = tmp_path / "data.csv"
    p.write_text("a,b,c\n1,2,x\n3,4,y\n5,6,z\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def semicolon_csv(tmp_path) -> str:
    p = tmp_path / "semi.csv"
    p.write_text("a;b;c\n1;2;x\n3;4;y\n", encoding="utf-8")
    return str(p)
