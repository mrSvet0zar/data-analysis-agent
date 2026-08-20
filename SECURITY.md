# Security & threat model

This app feeds **user-uploaded CSV content into an LLM's context**, then lets the
model drive tools. That makes prompt injection and cost abuse first-class
concerns, not afterthoughts. This document states what we defend against and how.

## Assets

- The Anthropic API key and the spend it authorizes.
- The backend host and its filesystem.
- Other users' jobs and results.

## Threats & mitigations

### 1. Prompt injection via CSV content
A column name or cell value could contain text like *"ignore your instructions
and …"*. Because that data enters the model's context, it could try to steer the
agent.

**Mitigations**
- The system prompt explicitly instructs the model to treat all CSV
  content — column names, cell values, tool results — as **data, never
  instructions** (`app/agent.py`, `SYSTEM_PROMPT`).
- The tool surface is small and read-only-analytical: the agent can compute
  stats, correlations, outliers, charts, and a report. There is **no tool that
  reads arbitrary files, runs code, makes network calls, or writes outside the
  outputs directory**, so a successful injection has a very limited blast radius.
- The model never receives or chooses a file path — the server injects it
  (see below), so injection cannot redirect file access.

### 2. Server-side path traversal / arbitrary file read
If the model chose the file path, injected text could point tools at
`/etc/passwd` or another job's upload.

**Mitigation**: `file_path` is **injected by the agent server-side** and is never
part of any tool's input schema. Tools operate only on the job's own uploaded
CSV.

### 3. Cost abuse / denial of wallet
An open `/api/analyze` endpoint backed by an LLM is a way to burn someone else's
tokens.

**Mitigations**
- Optional bearer-token auth (`API_AUTH_TOKEN`) on the REST and WS endpoints.
- Per-IP rate limiting (`RATE_LIMIT`, via slowapi).
- A global concurrency semaphore (`MAX_CONCURRENT_JOBS`) caps simultaneous
  Anthropic calls.
- A hard iteration cap (`MAX_ITERATIONS`) and per-job wall-clock timeout
  (`JOB_TIMEOUT_SECONDS`) bound the work (and cost) of any single job.
- Every run's token usage and estimated USD cost are tracked and surfaced, so
  spend is observable.

### 4. Resource exhaustion via large/malformed files
A huge or malformed CSV could exhaust memory or CPU.

**Mitigations**: upload size limit (`MAX_FILE_SIZE`), a hard row cap
(`MAX_ROWS`), and automatic random sampling above `SAMPLE_OVER_ROWS`. Parsing is
defensive (encoding/delimiter sniffing) and failures return a clean error rather
than crashing the loop.

### 5. Data retention
Uploaded CSVs are **deleted as soon as their analysis finishes**, and any job
older than `JOB_TTL_SECONDS` (with its file) is swept on a schedule.

## Explicitly out of scope (for this demo)

- Multi-tenant authn/z (per-user accounts, per-user job isolation beyond ids).
- Secrets management beyond environment variables.
- Encryption at rest for the SQLite job store.

## Reporting

This is a portfolio project. For a real deployment, route vulnerability reports
to a monitored inbox and add a coordinated-disclosure policy here.
