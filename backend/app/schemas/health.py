"""
MailMind AI - Health Endpoint Schema.

Defines strict response DTO for system health checks.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Response schema for GET /health endpoint.
    Provides diagnostic metadata regarding application status.
    """

    app_name: str = Field(
        ...,
        description="Name of the application service",
        examples=["MailMind AI Backend"],
    )
    version: str = Field(
        ...,
        description="Semantic version string of the application",
        examples=["0.1.0"],
    )
    status: str = Field(
        ...,
        description="Current operational status (e.g. ok, degraded, unhealthy)",
        examples=["ok"],
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of the health check request",
        examples=["2026-07-23T20:30:00Z"],
    )
