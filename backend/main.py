from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import chats, documents, users
from backend.app.core.database import db
from contextlib import asynccontextmanager
from backend.app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins = settings.allow_origins,
    allow_credentials = True,
    allow_methods = ['*'],
    allow_headers = ['*']
)

@app.get("/health")
def heath_check():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Welcome to SmartInsight API"}

app.include_router(
    users.router,
    prefix="/api",
    tags=["User"]
)

app.include_router(
    documents.router,
    prefix="/api",
    tags=["Document"]
)

app.include_router(
    chats.router,
    prefix="/api",
    tags=["Chat"]
)