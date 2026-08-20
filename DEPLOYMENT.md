# 🚀 Deployment Guide

Deploy the **backend** to [Railway](https://railway.app) and the **frontend** to
[Vercel](https://vercel.com). Both connect straight to this GitHub repo.

Order matters: deploy the **backend first** so you have its public URL to hand to
the frontend.

---

## 1. Backend → Railway

1. **New Project → Deploy from GitHub repo** → pick `data-analysis-agent`.
2. In the service **Settings → Root Directory**, set it to **`backend`**.
   (The repo is a monorepo; Railway must build from the backend folder.)
   - `backend/railway.json` selects the **Dockerfile builder**, so Railway builds
     the exact same image you can run locally. The container's `CMD` is the single
     source of truth for how the app starts — no start command to set by hand.
3. **Settings → Variables**, add:

   | Variable | Value |
   |----------|-------|
   | `ANTHROPIC_API_KEY` | your real key (`sk-ant-...`) |
   | `ANTHROPIC_MODEL` | `claude-sonnet-5` |
   | `CORS_ORIGINS` | *(fill in after Vercel — your prod URL, e.g. `https://data-analysis-agent.vercel.app`)* |
   | `CORS_ORIGIN_REGEX` | `https://.*\.vercel\.app` *(optional — allows Vercel preview URLs)* |

4. **Settings → Networking → Generate Domain** to get a public URL, e.g.
   `https://data-analysis-agent-production.up.railway.app`.
5. Verify: `https://<your-railway-url>/health` returns `{"status":"ok"}`, and
   `/ready` returns `{"ready":true,...}` (confirms DB + API key are wired up).

Reproduce the exact production image locally:

```bash
cd backend
docker build -t agent-backend .
docker run --rm -e PORT=8000 -e ANTHROPIC_API_KEY=sk-ant-... -p 8000:8000 agent-backend
```

> **`$PORT` gotcha.** Railway exec's a `railway.json` `startCommand` *without a
> shell*, so a literal `--port $PORT` is passed unexpanded and uvicorn fails with
> `Invalid value for '--port': '$PORT'`. Any start command that references `$PORT`
> must go through a shell — the Dockerfile's `CMD` uses
> `sh -c "... --port ${PORT:-8000}"` for exactly this reason.

---

## 1b. Durable job history (optional)

By default the backend stores jobs in **SQLite inside the container**. Railway's
filesystem is ephemeral, so a redeploy or restart wipes job history. Uploaded
CSVs are deleted after each analysis anyway, and results are returned through the
API, so this is fine for a demo — but here is how to make history durable.

**Pick based on how many instances you run:**

| | Use when | How |
|---|---|---|
| **Volume + SQLite** | a **single** instance (the common case) | attach a volume, set `DB_PATH` |
| **PostgreSQL** | **two or more replicas**, or you want managed backups | add the Postgres plugin |

A SQLite file on a volume cannot be shared safely across instances — that is the
line where Postgres becomes necessary, not before.

### Option A — Railway Volume (keeps SQLite)

1. Service → **Data → Add Volume**, mount path `/data`.
2. Add the variable `DB_PATH=/data/jobs.db`.
3. Redeploy. `/ready` should report `"db_backend": "sqlite"`, and job history now
   survives restarts.

No code change: `DB_PATH` was already configurable.

### Option B — Railway PostgreSQL (for multiple replicas)

1. In the project: **New → Database → Add PostgreSQL**.
2. In the **backend** service, reference the injected connection string —
   add the variable `DATABASE_URL` with value `${{Postgres.DATABASE_URL}}`.
3. Redeploy. The app detects `DATABASE_URL`, creates its schema on startup, and
   `/ready` reports `"db_backend": "postgres"`.

Also no code change — `app/db.py` picks the backend from configuration, and both
backends are covered by the test suite (CI runs the Postgres tests against a
service container).

Try either mode locally first:

```bash
# Durable SQLite on a volume
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build

# PostgreSQL
ANTHROPIC_API_KEY=sk-ant-... \
  docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

---

## 2. Frontend → Vercel

1. **Add New → Project** → import `data-analysis-agent` from GitHub.
2. **Root Directory → `frontend`** (Vercel auto-detects Vite from there).
   `frontend/vercel.json` sets the build command (`npm run build`) and output
   (`dist`), so the defaults are already correct.
3. **Environment Variables**, add:

   | Variable | Value |
   |----------|-------|
   | `VITE_API_URL` | your Railway URL, **no trailing slash** (e.g. `https://data-analysis-agent-production.up.railway.app`) |

4. **Deploy**. You'll get a URL like `https://data-analysis-agent.vercel.app`.

---

## 3. Close the loop (CORS)

The frontend calls the backend from the browser, so the backend must allow the
Vercel origin:

1. Copy your final Vercel URL.
2. Back in **Railway → Variables**, set `CORS_ORIGINS` to that URL and redeploy.
3. Open the Vercel site, upload `sample_data/sales.csv`, and confirm the agent
   runs end-to-end (steps stream in, charts + report appear).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `WebSocket connection failed` in prod | Ensure `VITE_API_URL` uses `https://` (the app derives `wss://` from it) and the Railway domain is generated & healthy. |
| CORS error in browser console | `CORS_ORIGINS` on Railway must exactly match the Vercel origin (scheme + host, no trailing slash). |
| Build fails on Railway | Confirm Root Directory is `backend`; reproduce with `docker build -t agent-backend backend/` locally. |
| `Invalid value for '--port': '$PORT'` | A start command referenced `$PORT` without a shell. Let the Dockerfile `CMD` start the app, or wrap the command in `sh -c '...'`. |
| 502 on `/health` | The server must bind `--host 0.0.0.0` and the platform's `$PORT` (the Dockerfile `CMD` already does). |
| `/ready` returns 503 | `ANTHROPIC_API_KEY` is missing on Railway, or the SQLite store failed to initialize — check the deploy logs. |

---

*Both platforms redeploy automatically on every push to the default branch.*
