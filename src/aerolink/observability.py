import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Write operational logs as compact JSON without request bodies or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "topic",
            "raw_message_id",
            "workspace_id",
            "reason_code",
            "session_present",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Configure one JSON handler for AeroLink's process logs."""
    logger = logging.getLogger("aerolink")
    if any(getattr(handler, "_aerolink_handler", False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._aerolink_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
