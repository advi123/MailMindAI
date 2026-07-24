"""
MailMind AI - Root API Router.

Architectural Decision Rationale:
---------------------------------
1. API Versioning & Route Aliases: Connects versioned API endpoints under `/api/v1`
   while exposing top-level convenience aliases (`/health`, `/ws/voice`) for direct client access.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, voice
from app.api.v1.router import api_v1_router

root_router = APIRouter()

# Top-level routes (e.g., ws://localhost:8000/ws/voice and http://localhost:8000/health)
root_router.include_router(health.router)
root_router.include_router(voice.router)

# Versioned API routes (e.g., ws://localhost:8000/api/v1/ws/voice)
root_router.include_router(api_v1_router, prefix="/api/v1")
