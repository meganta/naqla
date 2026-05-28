from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from modules.auth.router import router as auth_router
from modules.ingestion.router import router as ingestion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Naqla API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ingestion_router)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment, "service": "naqla-api"}
