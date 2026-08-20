# 🤖 Data Analysis Agent

An **autonomous AI agent** that analyzes any CSV on its own. You upload a dataset
and a request; the agent — powered by Claude's native tool-use — decides which
tools to call, executes them, iterates, and produces an interactive report with
visualizations. Every step streams live to the browser over WebSockets.

![CI](https://github.com/mrSvet0zar/data-analysis-agent/actions/workflows/ci.yml/badge.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Claude](https://img.shields.io/badge/Claude_tool--use-8A2BE2)
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)

**Live:** [frontend](https://data-analysis-agent-ecru.vercel.app/) ·
[backend health](https://data-analysis-agent-production-ed08.up.railway.app/health)

---

## What makes it an "agent"?

Not a fixed pipeline — a **tool-use loop**. Claude receives the request plus a
toolbox and *chooses* what to do next based on what it has learned.

```
user request + CSV
      │
      ▼
┌───────────────────────────────────────────┐
│  Agent loop (backend/app/agent.py)         │
│   Claude ──► "call read_csv" ──► execute   │
│     ▲                              │       │
│     └──── tool result ◄────────────┘       │
│        (repeats until Claude says done)    │
└───────────────────────────────────────────┘
      │  every step streamed via WebSocket
      ▼   + token/cost accounting per run
   report + charts
```

### The 6 tools

| Tool | What it does |
|------|--------------|
| `read_csv` | Structure: shape, dtypes, missing values, preview |
| `describe_statistics` | mean/std/quartiles + skewness & kurtosis |
| `detect_outliers` | IQR or Z-score outlier detection |
| `correlation_analysis` | Pearson matrix + strongest pairs |
| `create_visualization` | Interactive Plotly chart (5 types) |
| `generate_report` | Compile findings into a markdown report |

---

## Production-readiness highlights

This started as a demo and was hardened toward production:

- **Observability & cost** — per-run token accounting + USD cost estimate
  (surfaced in the UI), structured JSON logs with correlation ids.
- **Reliability** — SQLite-backed job store (survives restarts), per-job timeout,
  SDK retry/backoff, TTL sweep + upload cleanup.
- **Real-time** — WebSocket **push** (per-subscriber queues), fully async
  (`AsyncAnthropic` + `asyncio.to_thread`).
- **Robust ingestion** — encoding/delimiter sniffing, row caps, sampling of huge
  files, cached DataFrame (loaded once per job, not per tool call).
- **Security** — optional bearer-token auth, rate limiting, concurrency cap,
  prompt-injection guard, server-side file-path injection. See [SECURITY.md](SECURITY.md).
- **Quality gates** — `evals/` harness (tool-coverage + factual grounding +
  LLM-as-judge), pytest + ruff + mypy, GitHub Actions CI, Docker.

---

## Project structure

```
agent/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI: /api/analyze, /ws/job, /health, /ready
│   │   ├── agent.py         # the tool-use loop (token/cost tracking, retries)
│   │   ├── store.py         # SQLite job store + WS pub/sub + TTL sweep
│   │   ├── data_loader.py   # robust, cached CSV loading
│   │   ├── config.py        # Pydantic Settings (fail-fast)
│   │   ├── security.py      # optional bearer-token auth
│   │   ├── logging_config.py
│   │   └── tools/           # tool schemas + pandas/plotly handlers
│   ├── evals/               # agent evals (tool coverage, grounding, LLM-judge)
│   ├── tests/               # pytest: data loader, store, API, agent loop
│   ├── Dockerfile · pyproject.toml · requirements*.txt
│   └── sample_data/         # sales, employees, weather (deterministic)
├── frontend/                # React + Vite + Tailwind + Plotly (lazy-loaded)
├── .github/workflows/ci.yml
├── docker-compose.yml
├── DEPLOYMENT.md · SECURITY.md
```

---

## Quickstart

### Backend
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | macOS/Linux: source venv/bin/activate
venv/Scripts/pip install -r requirements-dev.txt
cp .env.example .env          # paste your ANTHROPIC_API_KEY
venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

Open `http://localhost:5173`, drop in `backend/sample_data/sales.csv`, and watch
the agent work — with a live cost readout.

### Docker (both, prod-parity)
```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```

---

## Testing & quality

```bash
# Backend — fast, no API cost (LLM stubbed)
cd backend
venv/Scripts/python -m pytest
venv/Scripts/python -m ruff check . && venv/Scripts/python -m mypy app/

# Agent evals — live, spends tokens (run before releasing / prompt changes)
venv/Scripts/python -m evals.run

# Frontend
cd frontend && npm test && npm run build
```

CI (GitHub Actions) runs ruff + mypy + pytest and the frontend build on every
push. Evals are intentionally excluded from CI because they call the real model.

See [DEPLOYMENT.md](DEPLOYMENT.md) for Railway + Vercel, and [SECURITY.md](SECURITY.md)
for the threat model.

---

## Configuration (`backend/.env`)

Key settings (full list in `.env.example`):

| Variable | Default | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | — | **required** |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | any current Claude model |
| `API_AUTH_TOKEN` | *(empty)* | if set, required as bearer token |
| `RATE_LIMIT` | `20/minute` | per-IP |
| `MAX_CONCURRENT_JOBS` | `4` | caps simultaneous LLM runs |
| `JOB_TIMEOUT_SECONDS` | `180` | per-job wall clock |
| `MAX_ROWS` / `SAMPLE_OVER_ROWS` | `1e6` / `2e5` | ingestion bounds |

---

*Project 4 of the AI portfolio — autonomous agent / agentic workflow.*
