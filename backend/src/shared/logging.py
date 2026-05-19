import logging
import sys

import structlog

from shared.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    # Intentionally omit `file=sys.stdout`: PrintLogger's `msg()` checks
    # `self._file is sys.stdout` and, when true, passes `file=None` to
    # print() so the current sys.stdout is resolved at write time. Passing
    # `file=sys.stdout` explicitly captures whatever sys.stdout pointed at
    # during configure(), which breaks under pytest capsys teardown. See 5vt.
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, handlers=[logging.StreamHandler(sys.stdout)], force=True)
