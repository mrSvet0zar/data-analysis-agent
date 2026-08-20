"""Integration tests for the PostgreSQL job-store backend.

Skipped unless ``TEST_DATABASE_URL`` points at a reachable Postgres, so the
default suite stays fast and dependency-free. CI provides one via a service
container; locally you can run:

    docker run --rm -d --name pg-test -e POSTGRES_PASSWORD=pw -p 5433:5432 postgres:16-alpine
    TEST_DATABASE_URL=postgresql://postgres:pw@localhost:5433/postgres \\
        pytest tests/test_store_postgres.py
"""

import os

import pytest

from app.config import settings
from app.store import JobStore

PG_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="TEST_DATABASE_URL not set; skipping Postgres integration tests"
)


async def _truncate(store: JobStore) -> None:
    await store._db.execute("DELETE FROM jobs WHERE 1=1")


@pytest.fixture
async def pg_store(monkeypatch):
    monkeypatch.setattr(settings, "database_url", PG_URL)
    s = JobStore()
    await s.init()
    # Start from a clean table so reruns are deterministic.
    await _truncate(s)
    yield s
    # A test may legitimately close the store (e.g. the reconnect test), so only
    # clean up if it is still connected.
    if s.connected:
        await _truncate(s)
        await s.close()


async def test_selects_postgres_backend(pg_store):
    assert pg_store.backend == "postgres"


async def test_roundtrip_persists_every_field(pg_store, tmp_path):
    upload = tmp_path / "job.csv"
    upload.write_text("a,b\n1,2\n", encoding="utf-8")
    live = await pg_store.create("pg1", "job.csv", "req", str(upload))

    # Running jobs report live state.
    snap = await pg_store.get("pg1")
    assert snap["status"] == "running"

    # Steps arrive through the live job (that's what `on_step` does in production),
    # and finalize persists those.
    live.add_step({"type": "tool_use", "tool": "read_csv"})

    result = {
        "status": "completed",
        "result": "done",
        "error": None,
        "charts": [{"chart_type": "heatmap", "title": "t", "plotly_json": {"data": []}}],
        "report": "# Report",
        "usage": {"input_tokens": 11, "output_tokens": 7, "cost_usd": 0.002, "iterations": 3},
        "steps": [],
    }
    await pg_store.finalize("pg1", result, str(upload))

    got = await pg_store.get("pg1")
    assert got["status"] == "completed"
    assert got["result"] == "done"
    assert got["charts"][0]["chart_type"] == "heatmap"
    assert got["report"] == "# Report"
    assert got["usage"]["cost_usd"] == 0.002
    assert got["steps"][0]["tool"] == "read_csv"
    assert not upload.exists(), "upload should be deleted after finalize"


async def test_survives_reconnect(pg_store, tmp_path):
    """The whole point of Postgres: data outlives the process."""
    upload = tmp_path / "d.csv"
    upload.write_text("a\n1\n", encoding="utf-8")
    await pg_store.create("pg-durable", "d.csv", "req", str(upload))
    await pg_store.finalize(
        "pg-durable",
        {
            "status": "completed",
            "result": "kept",
            "charts": [],
            "report": None,
            "usage": {},
            "steps": [],
        },
        str(upload),
    )
    await pg_store.close()

    # A brand-new store instance (fresh "process") still sees the job.
    revived = JobStore()
    await revived.init()
    try:
        got = await revived.get("pg-durable")
        assert got is not None, "job should survive a reconnect"
        assert got["result"] == "kept"
    finally:
        await _truncate(revived)
        await revived.close()


async def test_get_unknown_returns_none(pg_store):
    assert await pg_store.get("does-not-exist") is None


async def test_sweep_expired(pg_store, tmp_path, monkeypatch):
    upload = tmp_path / "old.csv"
    upload.write_text("a\n1\n", encoding="utf-8")
    await pg_store.create("pg-old", "old.csv", "req", str(upload))

    monkeypatch.setattr(settings, "job_ttl_seconds", -1)
    assert await pg_store.sweep_expired() == 1
    assert await pg_store.get("pg-old") is None
