"""structlog configuration.

JSON output to stdout — Kubernetes collects it via container runtime, so
no log file management is needed. `bind_contextvars` from middleware lets
us tag every log line in a request with `request_id`, `user_id`, ...
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Wire structlog as the global logger.

    Safe to call multiple times; later calls reset configuration.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Route stdlib logging through structlog too (uvicorn, sqlalchemy, ...).
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
