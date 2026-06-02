from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from core.config import settings


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

    payload = await request.json()
    job_id = payload.get("job_id")
    source_id = payload.get("source_id")
    tenant_id = payload.get("tenant_id")

    if not all([job_id, source_id, tenant_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as db:
        try:
            from handlers.ingestion import process_ingestion_job

            count = await process_ingestion_job(
                db=db,
                job_id=job_id,
                source_id=source_id,
                tenant_id=tenant_id,
                bucket_name=settings.gcs_bucket_name,
            )
            await db.commit()
            return {"status": "done", "chunks_created": count}
        except Exception as e:
            await db.rollback()
            import traceback
            import logging
            from handlers.ingestion import classify_error, format_user_error
            error_type = classify_error(e)
            logging.getLogger("worker").error(
                "Ingestion task failed [%s] job=%s source=%s: %s\n%s",
                error_type, job_id, source_id, str(e), traceback.format_exc()
            )
            if error_type == "dead":
                try:
                    from sqlalchemy.ext.asyncio import async_sessionmaker
                    from sqlalchemy import update
                    from ingestion_models import IngestionJob, KnowledgeSource
                    from datetime import datetime
                    session_factory2 = async_sessionmaker(bind=engine, expire_on_commit=False)
                    user_msg = format_user_error(e, error_type)
                    async with session_factory2() as db2:
                        await db2.execute(
                            update(IngestionJob)
                            .where(IngestionJob.id == job_id)
                            .values(status="failed", error_message=user_msg)
                        )
                        await db2.execute(
                            update(KnowledgeSource)
                            .where(KnowledgeSource.id == source_id)
                            .values(status="failed", updated_at=datetime.utcnow())
                        )
                        await db2.commit()
                    logging.getLogger("worker").info(
                        "Dead error handled for job=%s: %s", job_id, user_msg
                    )
                except Exception as db_err:
                    logging.getLogger("worker").error("Failed to mark dead error: %s", db_err)
                return {"status": "dead_error", "detail": format_user_error(e, error_type)}
            raise HTTPException(status_code=500, detail=str(e)) from e
