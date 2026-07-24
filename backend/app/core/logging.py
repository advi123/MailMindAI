"""
MailMind AI - Structured Logging System.

Architectural Decision Rationale:
---------------------------------
1. Structured JSON Output: Modern cloud deployments require logs to be machine-parseable
   by log aggregators (e.g., Datadog, AWS CloudWatch, ELK stack). Standardized JSON logs
   with metadata (timestamp, log level, logger name) simplify querying and automated alerting.
2. Standardized Python logging module: Using standard python logging hooks into Uvicorn,
   FastAPI, and standard library exceptions cleanly without proprietary vendor lock-in.
3. Centralized Initialization: Called once during application lifecycle setup (lifespan hook),
   ensuring uniform formatting across all modules and sub-services.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Custom logging formatter that transforms log records into structured JSON objects.
    Ensures all logs emitted across services follow a standard schema.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_object: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields passed to logger if present
        if hasattr(record, "extra_data"):
            log_object["extra"] = record.extra_data

        return json.dumps(log_object)


class TextFormatter(logging.Formatter):
    """
    Human-readable log formatter for local development environments.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configures root logger and attaches standard output stream handler with chosen formatter.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicate log outputs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(numeric_level)

    if log_format.lower() == "json":
        stream_handler.setFormatter(JSONFormatter())
    else:
        stream_handler.setFormatter(TextFormatter())

    root_logger.addHandler(stream_handler)

    # Quiet overly chatty third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Factory function to obtain a named logger instance for any service or module.
    """
    return logging.getLogger(name)
