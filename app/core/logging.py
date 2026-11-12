import logging
import re
import sys
from typing import Any, Literal

import loguru._defaults as loguru_defaults
from loguru import logger

IMAGE_B64_REGEX = re.compile(
    r"data:image\/[a-zA-Z0-9\+\-\.]+;base64,[A-Za-z0-9+/=\-_\r\n]+",
    re.IGNORECASE,
)

INTERCEPTED_LOGGERS = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "asyncio",
    "starlette",
)


def sanitize_value(val: Any) -> Any:
    if isinstance(val, str):
        if "data:image/" in val.lower():
            return IMAGE_B64_REGEX.sub("<base64_image_truncated>", val)
        return val
    if isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_value(v) for v in val]
    if isinstance(val, tuple):
        return tuple(sanitize_value(v) for v in val)

    val_repr = repr(val)
    if "data:image/" in val_repr.lower():
        return IMAGE_B64_REGEX.sub("<base64_image_truncated>", val_repr)
    return val


def sanitize_base64(record: dict[str, Any]) -> None:
    msg = record.get("message", "")
    if isinstance(msg, str) and "data:image/" in msg.lower():
        record["message"] = IMAGE_B64_REGEX.sub("<base64_image_truncated>", msg)

    if record.get("extra"):
        record["extra"] = {k: sanitize_value(v) for k, v in record["extra"].items()}


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(handlers=[InterceptHandler()], level=log_level)

    logger.remove()
    _ = logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "format": f"{loguru_defaults.LOGURU_FORMAT} | {{extra}}",
                "level": log_level,
                "colorize": True,
                "backtrace": True,
                "diagnose": True,
                "enqueue": True,
            }
        ],
        patcher=sanitize_base64,
    )

    for logger_name in INTERCEPTED_LOGGERS:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.propagate = True
