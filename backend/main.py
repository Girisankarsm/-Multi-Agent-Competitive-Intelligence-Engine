"""Compy Backend — FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import company, competitor, analysis, plan, monitor, compare, sales, chat, voice
from services.scheduler import start_scheduler, stop_scheduler

# Configure logging — show SCOUT/CRAWL logs clearly
logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s\033[0m %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    start_scheduler()
    print("\n\033[1;36m╔══════════════════════════════════════════╗\033[0m")
    print("\033[1;36m║   🚀 Compy Backend — Ready on :8000      ║\033[0m")
    print("\033[1;36m╚══════════════════════════════════════════╝\033[0m\n")
    yield
    stop_scheduler()


app = FastAPI(
    title="Compy — Competitive Intelligence Engine",
    description="Multi-agent competitive intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(company.router)
app.include_router(competitor.router)
app.include_router(analysis.router)
app.include_router(plan.router)
app.include_router(monitor.router)
app.include_router(compare.router)
app.include_router(sales.router)
app.include_router(chat.router)
app.include_router(voice.router)


@app.get("/")
async def root():
    return {
        "name": "Compy",
        "version": "0.1.0",
        "status": "operational",
        "description": "Competitive Intelligence Engine — Multi-Agent Platform",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
