"""
main.py — FastAPI application entry point.

Starts the API server, registers routers, and configures CORS so the
React/Vite frontend can communicate with the backend during development.

Phase 0: health check only. NLP routes are added in later phases.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import upload, analysis

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


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    """Returns 200 OK — used to verify the server is running."""
    return {"status": "ok"}
