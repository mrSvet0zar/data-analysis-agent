"""Database adapters: SQLite (default) or PostgreSQL (when DATABASE_URL is set).

Why two backends?

- **SQLite** is perfect for a single instance. On an ephemeral host it loses
  history at every restart, which is fixed by pointing ``DB_PATH`` at a mounted
  volume — no code change needed.
- **PostgreSQL** is what you need once the app runs as **more than one replica**:
  a SQLite file on a volume cannot be shared safely across instances.

Both adapters expose the same tiny async interface, so ``JobStore`` is unaware of
which one it is talking to. SQL is written once with ``?`` placeholders and
rewritten to ``$1, $2, …`` for asyncpg.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.config import settings

# Shared column list; only the physical types differ per backend.
_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    filename     TEXT,
    request_text TEXT,
    file_path    TEXT,
    result       TEXT,
    error        TEXT,
    charts       TEXT,
    report       TEXT,
    steps        TEXT,
    usage        TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at);
"""

_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    filename     TEXT,
    request_text TEXT,
    file_path    TEXT,
    result       TEXT,
    error        TEXT,
    charts       TEXT,
    report       TEXT,
    steps        TEXT,
    usage        TEXT,
    created_at   DOUBLE PRECISION NOT NULL,
    updated_at   DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at);
"""


class Database(Protocol):
    """Minimal async DB interface used by the job store."""

    backend: str

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None: ...
    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict | None: ...
    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict]: ...


class SQLiteDatabase:
    backend = "sqlite"

    def __init__(self, path: str):
        self._path = path
        self._conn: Any = None

    async def connect(self) -> None:
        import aiosqlite

        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SQLITE_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        await self._conn.execute(sql, tuple(params))
        await self._conn.commit()

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        async with self._conn.execute(sql, tuple(params)) as cur:
            row = await cur.fetchone()
        return dict(row) if row is not None else None

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        async with self._conn.execute(sql, tuple(params)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


def _to_pg_placeholders(sql: str) -> str:
    """Rewrite `?` placeholders to asyncpg's `$1, $2, …` form."""
    counter = 0

    def repl(_match: re.Match) -> str:
        nonlocal counter
        counter += 1
        return f"${counter}"

    return re.sub(r"\?", repl, sql)


class PostgresDatabase:
    backend = "postgres"

    def __init__(self, dsn: str):
        # Railway may hand out `postgres://`; asyncpg is happiest with `postgresql://`.
        self._dsn = re.sub(r"^postgres://", "postgresql://", dsn)
        self._pool: Any = None

    async def connect(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            # asyncpg can't run multiple statements in one execute() with args,
            # but plain DDL without args is fine.
            for stmt in filter(None, (s.strip() for s in _POSTGRES_SCHEMA.split(";"))):
                await conn.execute(stmt)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_to_pg_placeholders(sql), *params)

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_to_pg_placeholders(sql), *params)
        return dict(row) if row is not None else None

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_to_pg_placeholders(sql), *params)
        return [dict(r) for r in rows]


def make_database() -> Database:
    """Pick the backend from configuration: Postgres if DATABASE_URL, else SQLite."""
    if settings.database_url:
        return PostgresDatabase(settings.database_url)
    return SQLiteDatabase(str(settings.db_path))
