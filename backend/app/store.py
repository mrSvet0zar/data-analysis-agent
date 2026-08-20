"""Job persistence + live pub/sub.

Two layers:
- A **database** (SQLite by default, PostgreSQL when ``DATABASE_URL`` is set —
  see ``app.db``) durably stores every job, so results survive a restart and
  memory doesn't grow without bound.
- **LiveJob** holds the in-flight state for a running job and pushes steps to
  subscribed WebSockets through per-subscriber queues (real push, not polling).

A background sweep deletes jobs (and their uploaded files) past their TTL, and a
semaphore caps how many agent runs hit the Anthropic API concurrently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.data_loader import evict
from app.db import Database, make_database
from app.logging_config import get_logger, log_event

logger = get_logger("store")


class LiveJob:
    """In-memory state for a running job; fans steps out to WS subscribers."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.steps: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.done = asyncio.Event()
        self.final: dict | None = None

    def add_step(self, step: dict) -> None:
        self.steps.append(step)
        for q in list(self.subscribers):
            q.put_nowait(("step", step))

    def finish(self, final: dict) -> None:
        self.final = final
        self.done.set()
        for q in list(self.subscribers):
            q.put_nowait(("complete", final))

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay steps already emitted so a late subscriber sees the full timeline.
        for step in self.steps:
            q.put_nowait(("step", step))
        if self.final is not None:
            q.put_nowait(("complete", self.final))
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)


class JobStore:
    def __init__(self) -> None:
        self._live: dict[str, LiveJob] = {}
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._db: Database | None = None

    @property
    def backend(self) -> str | None:
        """Which storage backend is active ('sqlite' / 'postgres'), if connected."""
        return self._db.backend if self._db else None

    @property
    def connected(self) -> bool:
        return self._db is not None

    async def init(self) -> None:
        db = make_database()
        await db.connect()
        self._db = db
        log_event(logger, logging.INFO, "store_ready", backend=db.backend)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # --- creation & lifecycle ---
    async def create(
        self, job_id: str, filename: str, request_text: str, file_path: str
    ) -> LiveJob:
        now = time.time()
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO jobs (job_id, status, filename, request_text, file_path, "
            "created_at, updated_at) VALUES (?, 'running', ?, ?, ?, ?, ?)",
            (job_id, filename, request_text, file_path, now, now),
        )
        live = LiveJob(job_id)
        self._live[job_id] = live
        return live

    def live(self, job_id: str) -> LiveJob | None:
        return self._live.get(job_id)

    async def finalize(self, job_id: str, result: dict, file_path: str) -> None:
        """Persist the finished job and notify subscribers."""
        now = time.time()
        assert self._db is not None
        live = self._live.get(job_id)
        steps = live.steps if live else result.get("steps", [])
        await self._db.execute(
            "UPDATE jobs SET status=?, result=?, error=?, charts=?, report=?, "
            "steps=?, usage=?, updated_at=? WHERE job_id=?",
            (
                result.get("status", "completed"),
                result.get("result"),
                result.get("error"),
                json.dumps(result.get("charts", [])),
                result.get("report"),
                json.dumps(steps),
                json.dumps(result.get("usage", {})),
                now,
                job_id,
            ),
        )

        payload = {
            "status": result.get("status", "completed"),
            "result": result.get("result"),
            "charts": result.get("charts", []),
            "report": result.get("report"),
            "usage": result.get("usage", {}),
            "error": result.get("error"),
        }
        if live:
            live.finish(payload)

        # The uploaded CSV is no longer needed once analysis is done.
        try:
            Path(file_path).unlink(missing_ok=True)
            evict(file_path)
        except OSError:
            pass

    async def get(self, job_id: str) -> dict | None:
        """Return a job snapshot: live state if running, else the DB record."""
        live = self._live.get(job_id)
        if live and not live.done.is_set():
            return {
                "job_id": job_id,
                "status": "running",
                "steps": live.steps,
                "charts": [],
                "report": None,
                "result": None,
                "error": None,
                "usage": {},
            }
        assert self._db is not None
        row = await self._db.fetchone("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        if not row:
            return None
        return _row_to_dict(row)

    # --- maintenance ---
    async def sweep_expired(self) -> int:
        """Delete jobs past their TTL and remove any lingering upload files."""
        cutoff = time.time() - settings.job_ttl_seconds
        assert self._db is not None
        rows = await self._db.fetchall(
            "SELECT job_id, file_path FROM jobs WHERE created_at < ?", (cutoff,)
        )
        for row in rows:
            fp = row["file_path"]
            if fp:
                try:
                    Path(fp).unlink(missing_ok=True)
                    evict(fp)
                except OSError:
                    pass
            self._live.pop(row["job_id"], None)
        await self._db.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
        if rows:
            log_event(logger, logging.INFO, "swept_expired_jobs", count=len(rows))
        return len(rows)

    async def sweep_loop(self, interval_seconds: int = 3600) -> None:
        while True:
            try:
                await self.sweep_expired()
            except Exception as e:  # noqa: BLE001 — never let the sweeper die
                log_event(logger, logging.ERROR, "sweep_error", error=str(e))
            await asyncio.sleep(interval_seconds)


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "filename": row["filename"],
        "request_text": row["request_text"],
        "result": row["result"],
        "error": row["error"],
        "charts": json.loads(row["charts"]) if row["charts"] else [],
        "report": row["report"],
        "steps": json.loads(row["steps"]) if row["steps"] else [],
        "usage": json.loads(row["usage"]) if row["usage"] else {},
    }


store = JobStore()
