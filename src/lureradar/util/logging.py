"""Structured (JSON lines) logging for the pipeline; quiet by default for the CLI."""

from __future__ import annotations

import logging
import sys
from typing import Any

import orjson

from lureradar.util.time import isoformat, utcnow

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": isoformat(utcnow()),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return orjson.dumps(payload, default=str).decode()


def configure(level: str = "WARNING", json_lines: bool = False) -> None:
    root = logging.getLogger("lureradar")
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    if json_lines:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"lureradar.{name}")
