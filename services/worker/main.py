from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException

from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Naqla Worker",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment, "service": "naqla-worker"}


@app.post("/tasks/ingestion")
async def handle_ingestion_task(request: Request):
    payload = await request.json()
    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job_id in payload")
    # Ingestion handler will be implemented in Milestone 2
    return {"status": "accepted", "job_id": job_id}
