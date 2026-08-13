"""FastAPI application: upload a CSV, run the agent, stream progress over WS."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.agent import DataAnalysisAgent
from app.config import settings

settings.ensure_dirs()

app = FastAPI(title="Data Analysis Agent API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store. Fine for a single-process demo; swap for SQLite/Redis in prod.
jobs: dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.ANTHROPIC_MODEL}


@app.post("/api/analyze")
async def start_analysis(
    file: UploadFile = File(...),
    request_text: str = Form("Analyze this data and provide insights."),
):
    """Accept a CSV upload and kick off an analysis job."""
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {settings.MAX_FILE_SIZE // (1024 * 1024)} MB).",
        )
    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty.")

    job_id = str(uuid.uuid4())
    file_path = settings.UPLOAD_DIR / f"{job_id}.csv"
    file_path.write_bytes(content)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "filename": filename,
        "request_text": request_text,
        "steps": [],
        "charts": [],
        "report": None,
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_job(job_id, str(file_path), request_text))
    return {"job_id": job_id, "status": "started"}


async def _run_job(job_id: str, file_path: str, request_text: str) -> None:
    job = jobs[job_id]

    async def on_step(step: dict) -> None:
        job["steps"].append(step)

    try:
        agent = DataAnalysisAgent()
        result = await agent.analyze(file_path, request_text, on_step=on_step)
        job["status"] = result.get("status", "completed")
        job["result"] = result.get("result")
        job["charts"] = result.get("charts", [])
        job["report"] = result.get("report")
        if result.get("status") != "completed":
            job["error"] = result.get("error")
    except Exception as e:  # noqa: BLE001 — surface any failure to the client
        job["status"] = "error"
        job["error"] = str(e)


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return jobs[job_id]


@app.websocket("/ws/job/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in jobs:
        await websocket.send_json({"type": "error", "message": "Job not found."})
        await websocket.close(code=4004)
        return

    sent = 0
    try:
        while True:
            job = jobs.get(job_id, {})
            steps = job.get("steps", [])
            while sent < len(steps):
                await websocket.send_json({"type": "step", "step": steps[sent]})
                sent += 1

            if job.get("status") in ("completed", "error"):
                await websocket.send_json(
                    {
                        "type": "complete",
                        "status": job.get("status"),
                        "result": job.get("result"),
                        "charts": job.get("charts", []),
                        "report": job.get("report"),
                        "error": job.get("error"),
                    }
                )
                break

            await asyncio.sleep(0.4)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
