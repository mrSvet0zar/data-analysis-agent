"""API tests using FastAPI's TestClient (drives startup/shutdown lifespan).

The agent is replaced with a fake so no real Anthropic call is made.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings


class FakeAgent:
    def __init__(self):
        pass

    async def analyze(self, file_path, request_text, on_step=None):
        if on_step:
            await on_step({"type": "tool_use", "tool": "read_csv", "iteration": 0})
            await on_step(
                {
                    "type": "tool_result",
                    "tool": "read_csv",
                    "success": True,
                    "summary": "ok",
                    "iteration": 0,
                }
            )
        return {
            "status": "completed",
            "result": "done",
            "error": None,
            "charts": [],
            "report": "# Report",
            "usage": {"input_tokens": 5, "output_tokens": 3, "cost_usd": 0.0001, "iterations": 1},
            "steps": [],
        }


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_upload_rejects_non_csv(client):
    r = client.post("/api/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_empty(client):
    r = client.post("/api/analyze", files={"file": ("x.csv", b"   ", "text/csv")})
    assert r.status_code == 400


def test_full_flow_with_fake_agent(client, monkeypatch):
    monkeypatch.setattr(main, "DataAnalysisAgent", FakeAgent)
    r = client.post("/api/analyze", files={"file": ("d.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    job = {}
    for _ in range(100):
        job = client.get(f"/api/job/{job_id}").json()
        if job["status"] in ("completed", "error"):
            break
        time.sleep(0.02)
    assert job["status"] == "completed"
    assert job["report"] == "# Report"
    assert job["usage"]["cost_usd"] == 0.0001


def test_auth_enforced_when_token_set(client, monkeypatch):
    monkeypatch.setattr(settings, "api_auth_token", "secret")
    # No token -> 401 (auth dependency runs before the 404).
    assert client.get("/api/job/anything").status_code == 401
    # Correct token -> passes auth, then 404 for the missing job.
    r = client.get("/api/job/anything", headers={"X-API-Key": "secret"})
    assert r.status_code == 404
