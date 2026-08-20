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

> Note: Railway's filesystem is ephemeral — uploaded CSVs, generated charts, and
> the SQLite job store are temporary. That's fine here (results are returned via
> the API, and uploads are deleted after each analysis anyway). For durable job
> history, attach a volume or point `DB_PATH` at managed Postgres.

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
