"""FastAPI application: upload a CSV, run the agent, stream progress over WS."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent import DataAnalysisAgent
from app.config import settings
from app.logging_config import correlation_id, get_logger, log_event, setup_logging
from app.security import require_auth
from app.store import store

setup_logging(settings.log_level)
logger = get_logger("api")

limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    await store.init()
    sweeper = asyncio.create_task(store.sweep_loop())
    log_event(
        logger,
        logging.INFO,
        "startup",
        model=settings.anthropic_model,
        auth=settings.auth_enabled,
        max_concurrent=settings.max_concurrent_jobs,
    )
    try:
        yield
    finally:
        sweeper.cancel()
        await store.close()


app = FastAPI(title="Data Analysis Agent API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Slow down."})


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    cid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = cid
    return response


@app.get("/health")
async def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness: dependencies (DB, API key) are configured."""
    ok = store.connected and bool(settings.anthropic_api_key)
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "ready": ok,
            "model": settings.anthropic_model,
            "db": store.connected,
            "db_backend": store.backend,
            "api_key": bool(settings.anthropic_api_key),
        },
    )


@app.post("/api/analyze", dependencies=[Depends(require_auth)])
@limiter.limit(settings.rate_limit)
async def start_analysis(
    request: Request,
    file: UploadFile = File(...),
    request_text: str = Form("Analyze this data and provide insights."),
):
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {settings.max_file_size // (1024 * 1024)} MB).",
        )
    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty.")

    job_id = str(uuid.uuid4())
    file_path = settings.upload_dir / f"{job_id}.csv"
    file_path.write_bytes(content)

    await store.create(job_id, filename, request_text, str(file_path))
    asyncio.create_task(_run_job(job_id, str(file_path), request_text))
    log_event(
        logger, logging.INFO, "job_created", job_id=job_id, filename=filename, size=len(content)
    )
    return {"job_id": job_id, "status": "started"}


async def _run_job(job_id: str, file_path: str, request_text: str) -> None:
    correlation_id.set(job_id[:12])
    live = store.live(job_id)

    async def on_step(step: dict) -> None:
        if live:
            live.add_step(step)

    async with store.semaphore:  # cap concurrent Anthropic runs
        try:
            agent = DataAnalysisAgent()
            result = await asyncio.wait_for(
                agent.analyze(file_path, request_text, on_step=on_step),
                timeout=settings.job_timeout_seconds,
            )
        except TimeoutError:
            log_event(logger, logging.WARNING, "job_timeout", job_id=job_id)
            result = _error_result(f"Job timed out after {settings.job_timeout_seconds}s.")
        except Exception as e:  # noqa: BLE001 — surface any failure to the client
            log_event(logger, logging.ERROR, "job_failed", job_id=job_id, error=str(e))
            result = _error_result(str(e))
        await store.finalize(job_id, result, file_path)


def _error_result(msg: str) -> dict:
    return {
        "status": "error",
        "result": "",
        "error": msg,
        "charts": [],
        "report": None,
        "usage": {},
    }


@app.get("/api/job/{job_id}", dependencies=[Depends(require_auth)])
async def get_job(job_id: str):
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.websocket("/ws/job/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    # WS can't use header deps; accept an optional ?token= when auth is enabled.
    if settings.auth_enabled:
        token = websocket.query_params.get("token")
        if token != settings.api_auth_token:
            await websocket.close(code=4401)
            return

    await websocket.accept()
    live = store.live(job_id)

    if live is None:
        # Not in memory: either finished (replay from DB) or unknown.
        job = await store.get(job_id)
        if job is None:
            await websocket.send_json({"type": "error", "message": "Job not found."})
            await websocket.close(code=4004)
            return
        for step in job.get("steps", []):
            await websocket.send_json({"type": "step", "step": step})
        await websocket.send_json(
            {
                "type": "complete",
                "status": job.get("status"),
                "result": job.get("result"),
                "charts": job.get("charts", []),
                "report": job.get("report"),
                "usage": job.get("usage", {}),
                "error": job.get("error"),
            }
        )
        await websocket.close()
        return

    queue = live.subscribe()
    try:
        while True:
            kind, payload = await queue.get()
            if kind == "step":
                await websocket.send_json({"type": "step", "step": payload})
            elif kind == "complete":
                await websocket.send_json({"type": "complete", **payload})
                break
    except WebSocketDisconnect:
        pass
    finally:
        live.unsubscribe(queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
