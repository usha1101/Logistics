import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_ctx_var.get()


def set_request_id(request_id: str) -> None:
    request_id_ctx_var.set(request_id)


class StructuredSingleLineFormatter(logging.Formatter):
    """
    Formats log records into single-line structured JSON records.
    Guarantees no multi-line outputs even if exceptions are logged.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_request_id()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        log_payload = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "request_id": req_id,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info).replace("\n", " | ")

        return json.dumps(log_payload)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures root and app loggers to emit single-line structured logs."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Replace existing handlers with our single-line formatter
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredSingleLineFormatter())
    root_logger.addHandler(handler)

