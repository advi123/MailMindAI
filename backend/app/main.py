"""
MailMind AI - FastAPI Main Application Entrypoint.

Architectural Decision Rationale:
---------------------------------
1. Lifespan Context Manager: Standardized startup and shutdown lifecycle management using
   async context managers (`@asynccontextmanager`). Ensures logging, ConnectionManager, AudioStreamService,
   VADService, STTProviderFactory, STTService, ConversationMemoryService, PromptBuilder, ConversationManager,
   and ConversationService are initialized before accepting incoming traffic.
2. Dependency Injection: Uses constructor injection to assemble business services cleanly:
   - Provider strategy -> STTService
   - MemoryService -> ConversationManager
   - Manager + MemoryService + PromptBuilder -> ConversationService
3. Centralized CORS Middleware: Configures `CORSMiddleware` using dynamic environment settings.
4. Exception Handler Registration: Attaches custom handlers to convert unhandled exceptions or domain errors.
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
from app.services.conversation_manager_service import ConversationManager
from app.services.conversation_memory import conversation_memory_service
from app.services.conversation_service import conversation_service
from app.services.prompt_builder import prompt_builder
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

    # Initialize connection, audio streaming, & VAD services
    await connection_manager.initialize()
    await audio_stream_service.initialize()
    await vad_service.initialize()

    # Create STT provider via STTProviderFactory and inject into stt_service
    stt_provider = STTProviderFactory.create_provider(settings.STT_PROVIDER)
    stt_service.provider = stt_provider
    await stt_service.initialize()

    # Assemble and initialize Conversation Intelligence Engine services via Dependency Injection
    conv_mgr = ConversationManager(memory_service=conversation_memory_service)
    conversation_service.conversation_manager = conv_mgr
    conversation_service.memory_service = conversation_memory_service
    conversation_service.prompt_builder = prompt_builder
    await conversation_service.initialize()

    logger.info(
        f"WebSocket & Conversation Intelligence Services initialized (STT Provider: '{stt_provider.provider_name}')."
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
