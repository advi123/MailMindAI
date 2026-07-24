"""
MailMind AI - FastAPI Main Application Entrypoint.

Architectural Decision Rationale:
---------------------------------
1. Lifespan Context Manager: Standardized startup and shutdown lifecycle management using
   async context managers (`@asynccontextmanager`). Ensures logging, ConnectionManager, AudioStreamService,
   VADService, STTProviderFactory, STTService, and global services are initialized before accepting incoming traffic.
2. Dependency Injection: Uses `STTProviderFactory` during startup to instantiate the configured `BaseSTTProvider`
   strategy and injects it into `STTService`.
3. Centralized CORS Middleware: Configures `CORSMiddleware` using dynamic environment settings
   to allow secure cross-origin communication with future React frontends or mobile clients.
4. Exception Handler Registration: Attaches custom handlers to convert unhandled exceptions
   or domain errors into clean, structured JSON API responses.
5. Clean Router Inclusion: Mounts versioned and top-level routers via `root_router`.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import root_router
from app.core.config import settings
from app.core.exceptions import (
    BaseAppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.services.audio_stream_service import audio_stream_service
from app.services.connection_manager import connection_manager
from app.services.providers import STTProviderFactory
from app.services.stt_service import stt_service
from app.services.vad_service import vad_service

# Obtain logger for application lifespan lifecycle events
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager handling startup and shutdown initialization tasks.
    """
    # Startup tasks
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in [{settings.ENV}] mode...")

    # Initialize ConnectionManager, AudioStreamService, VADService, & STTService with injected provider strategy
    await connection_manager.initialize()
    await audio_stream_service.initialize()
    await vad_service.initialize()

    # Create provider via STTProviderFactory and inject into stt_service
    provider = STTProviderFactory.create_provider(settings.STT_PROVIDER)
    stt_service.provider = provider
    await stt_service.initialize()

    logger.info(
        f"WebSocket Services initialized (STT Provider: '{provider.provider_name}')."
    )

    yield

    # Shutdown tasks
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await stt_service.shutdown()


def create_application() -> FastAPI:
    """
    Application Factory function initializing and configuring the FastAPI instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Voice-First AI Email Executive Assistant Backend Foundation",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized Exception Handlers Registration
    app.add_exception_handler(BaseAppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Register API Routes
    app.include_router(root_router)

    return app


# Main application instance executed by Uvicorn ASGI server
app = create_application()
