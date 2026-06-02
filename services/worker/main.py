from contextlib import asynccontextmanager
import logging
import traceback
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from core.config import settings

logger = logging.getLogger("worker")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Naqla Worker", version="0.1.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment, "service": "naqla-worker"}

@app.post("/tasks/ingestion")
async def handle_ingestion_task(request: Request):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy import update
    from ingestion_models import IngestionJob, KnowledgeSource

    payload = await request.json()
    job_id = payload.get("job_id")
    source_id = payload.get("source_id")
    tenant_id = payload.get("tenant_id")

    if not all([job_id, source_id, tenant_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def mark_failed(msg: str) -> None:
        """Mark job and source as failed in a fresh DB session."""
        try:
            async with session_factory() as db_fail:
                await db_fail.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == job_id)
                    .values(status="failed", error_message=msg)
                )
                await db_fail.execute(
                    update(KnowledgeSource)
                    .where(KnowledgeSource.id == source_id)
                    .values(status="failed", updated_at=datetime.utcnow())
                )
                await db_fail.commit()
                logger.info("Marked job=%s source=%s as failed: %s", job_id, source_id, msg)
        except Exception as db_err:
            logger.error("Failed to mark_failed for job=%s: %s", job_id, db_err)

    try:
        from handlers.ingestion import process_ingestion_job, classify_error, format_user_error
    except Exception as import_err:
        logger.error(
            "Worker import error for job=%s: %s\n%s",
            job_id, str(import_err), traceback.format_exc()
        )
        await mark_failed(f"خطأ داخلي في النظام: {str(import_err)[:200]}")
        return {"status": "import_error", "detail": str(import_err)}

    async with session_factory() as db:
        try:
            count = await process_ingestion_job(
                db=db,
                job_id=job_id,
                source_id=source_id,
                tenant_id=tenant_id,
                bucket_name=settings.gcs_bucket_name,
            )
            await db.commit()
            logger.info("Job=%s completed: %d chunks created", job_id, count)
            return {"status": "done", "chunks_created": count}
        except Exception as e:
            await db.rollback()
            error_type = classify_error(e)
            logger.error(
                "Ingestion task failed [%s] job=%s source=%s: %s\n%s",
                error_type, job_id, source_id, str(e), traceback.format_exc()
            )
            user_msg = format_user_error(e, error_type)
            if error_type == "dead":
                await mark_failed(user_msg)
                return {"status": "dead_error", "detail": user_msg}
            # Retryable: mark failed with message but return 500 so Cloud Tasks retries
            await mark_failed(user_msg)
            raise HTTPException(status_code=500, detail=str(e)) from e
