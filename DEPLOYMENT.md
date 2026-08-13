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
   - `backend/railway.json` already provides the start command
     `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, so Railway uses `$PORT`
     automatically — no manual start command needed.
3. **Settings → Variables**, add:

   | Variable | Value |
   |----------|-------|
   | `ANTHROPIC_API_KEY` | your real key (`sk-ant-...`) |
   | `ANTHROPIC_MODEL` | `claude-sonnet-5` |
   | `CORS_ORIGINS` | *(fill in after Vercel — your prod URL, e.g. `https://data-analysis-agent.vercel.app`)* |
   | `CORS_ORIGIN_REGEX` | `https://.*\.vercel\.app` *(optional — allows Vercel preview URLs)* |

4. **Settings → Networking → Generate Domain** to get a public URL, e.g.
   `https://data-analysis-agent-production.up.railway.app`.
5. Verify: open `https://<your-railway-url>/health` → should return
   `{"status":"ok","model":"claude-sonnet-5"}`.

> Note: Railway's filesystem is ephemeral — uploaded CSVs and generated chart
> files are temporary, which is fine here (results are returned via the API).

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
| Build fails on Railway | Confirm Root Directory is `backend`; check `runtime.txt` Python version. |
| 502 on `/health` | Railway start command must bind `--host 0.0.0.0 --port $PORT` (already in `railway.json`). |

---

*Both platforms redeploy automatically on every push to the default branch.*
