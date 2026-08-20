"""Tests for the SQLite-backed job store."""

import tempfile
from pathlib import Path

import pytest

from app.config import settings
from app.store import JobStore


@pytest.fixture
async def fresh_store(monkeypatch):
    db = Path(tempfile.mkdtemp()) / "jobs.db"
    monkeypatch.setattr(settings, "db_path", db)
    s = JobStore()
    await s.init()
    yield s
    await s.close()


async def test_create_get_finalize_roundtrip(fresh_store, tmp_path):
    upload = tmp_path / "job.csv"
    upload.write_text("a,b\n1,2\n", encoding="utf-8")

    live = await fresh_store.create("job1", "job.csv", "req", str(upload))
    assert live is not None

    # While running, get() returns the live snapshot.
    snap = await fresh_store.get("job1")
    assert snap["status"] == "running"

    result = {
        "status": "completed",
        "result": "done",
        "error": None,
        "charts": [{"chart_type": "histogram", "title": "t", "plotly_json": {"data": []}}],
        "report": "# Report",
        "usage": {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001, "iterations": 2},
        "steps": [{"type": "tool_use", "tool": "read_csv"}],
    }
    await fresh_store.finalize("job1", result, str(upload))

    # After finalize: persisted record, and the upload file is cleaned up.
    got = await fresh_store.get("job1")
    assert got["status"] == "completed"
    assert got["result"] == "done"
    assert len(got["charts"]) == 1
    assert got["report"] == "# Report"
    assert got["usage"]["cost_usd"] == 0.001
    assert not upload.exists(), "upload should be deleted after finalize"


async def test_get_unknown_returns_none(fresh_store):
    assert await fresh_store.get("nope") is None


async def test_sweep_expired_removes_old_jobs(fresh_store, tmp_path, monkeypatch):
    upload = tmp_path / "old.csv"
    upload.write_text("a\n1\n", encoding="utf-8")
    await fresh_store.create("old", "old.csv", "req", str(upload))

    monkeypatch.setattr(settings, "job_ttl_seconds", -1)  # everything is "expired"
    removed = await fresh_store.sweep_expired()
    assert removed == 1
    assert await fresh_store.get("old") is None
