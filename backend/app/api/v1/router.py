"""
MailMind AI - V1 API Router Aggregator.

Aggregates all version 1 endpoints (health, voice websockets) into a single router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, voice

api_v1_router = APIRouter()

# Include health endpoints
api_v1_router.include_router(health.router)

# Include voice websocket endpoints
api_v1_router.include_router(voice.router)
