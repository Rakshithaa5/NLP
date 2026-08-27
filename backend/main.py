"""
main.py — FastAPI application entry point.

Starts the API server, registers routers, and configures CORS so the
React/Vite frontend can communicate with the backend during development.

Phase 0: /health (server) + /health/db (Supabase ping). NLP routes added in later phases.
"""

import os
import logging

logger = logging.getLogger("meeting_analyzer")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.routes import upload, analysis

load_dotenv()

app = FastAPI(
    title="Meeting Analyzer API",
    description="AI-based NLP system for automated meeting analysis.",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])


# ── Health checks ────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    """Returns 200 OK — used to verify the server is running."""
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
async def health_db():
    """
    Phase 0 DB connectivity check.
    Attempts a trivial Supabase query; returns status and any error message.
    Fill in SUPABASE_URL + SUPABASE_ANON_KEY in .env before calling this.
    """
    try:
        from backend.db import get_client
        client = get_client()
        # Trivial read — list tables metadata; fails gracefully if not configured
        client.table("meetings").select("id").limit(1).execute()
        return {"status": "ok", "db": "supabase connected"}
    except RuntimeError as exc:
        return {"status": "unconfigured", "detail": str(exc)}
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
