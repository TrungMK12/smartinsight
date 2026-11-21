import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import chats, documents, users
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.engine.rag import get_rag_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        get_rag_engine()
        logger.info("RAG engine ready")
    except Exception:
        logger.exception(
            "RAG engine warm-up failed; it will be retried on first request"
        )
    yield
    await db.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Welcome to SmartInsight API"}


app.include_router(users.router, prefix="/api", tags=["User"])
app.include_router(documents.router, prefix="/api", tags=["Document"])
app.include_router(chats.router, prefix="/api", tags=["Chat"])
