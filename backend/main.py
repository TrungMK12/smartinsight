import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from backend.app.api import chats, documents, users
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.core.errors import AppError
from backend.app.core.middleware import RequestContextMiddleware
from backend.app.core.rate_limit import limiter
from backend.app.engine.rag import get_rag_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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
app.state.limiter = limiter

# --- Middleware (thêm sau sẽ chạy ngoài cùng) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


# --- Exception handlers ---
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": exc.detail,
            "error_code": exc.error_code,
        },
    )


async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "detail": f"Rate limit exceeded: {exc.detail}",
            "error_code": "rate_limited",
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": "Internal server error",
            "error_code": "internal_error",
        },
    )


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


# --- Routes ---
@app.get("/health")
async def health_check():
    checks = {"api": "ok"}

    try:
        await db.get_database().command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"

    try:
        stats = get_rag_engine().get_stats()
        checks["vector_store"] = "ok"
        checks["vectors"] = stats["vector_db_stats"]["total_vectors"]
    except Exception as e:
        checks["vector_store"] = f"error: {e}"

    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{settings.llm_baseurl}/api/tags")
            checks["llm"] = "ok" if response.status_code == 200 else (
                f"http {response.status_code}"
            )
    except Exception:
        checks["llm"] = "unreachable"

    healthy = checks["mongodb"] == "ok"
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "checks": checks,
        },
    )


@app.get("/")
def root():
    return {"message": "Welcome to SmartInsight API"}


app.include_router(users.router, prefix="/api", tags=["User"])
app.include_router(documents.router, prefix="/api", tags=["Document"])
app.include_router(chats.router, prefix="/api", tags=["Chat"])
