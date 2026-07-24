import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

SENSITIVE_FIELD = re.compile(
    r"(?:api[_-]?key|authorization|cookie|password|prompt|question|answer|"
    r"document[_-]?text|content|token)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(?i)\b(?:bearer\s+)?(?:gsk_|sk-|AIza)[A-Za-z0-9._-]{8,}\b"
)
MAX_LOG_STRING = 500


def redact_sensitive(value: Any, *, field: str = "") -> Any:
    if SENSITIVE_FIELD.search(field):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(key): redact_sensitive(item, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        cleaned = SECRET_VALUE.sub("[REDACTED]", value)
        return cleaned[:MAX_LOG_STRING]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_LOG_STRING]


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "heritage_fields", {})
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            **redact_sensitive(fields),
        }
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(log_path: Path, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("heritage")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if getattr(logger, "_heritage_configured", False):
        return logger

    formatter = JsonLogFormatter()
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger._heritage_configured = True  # type: ignore[attr-defined]
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    logger.log(
        level,
        event,
        extra={"heritage_fields": redact_sensitive(fields)},
    )
