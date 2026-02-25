#!/usr/bin/env python3
"""
BlueFalconInk LLC — Security Logger

Provides structured JSON logging for all security-relevant events
across Architect AI Pro services (dashboard, gallery, CI scripts).

CSIAC Domain: Forensics

Usage:
    from security_logger import setup_security_logger, log_security_event

    logger = setup_security_logger("dashboard-server")
    log_security_event(logger, "auth_failure", "Failed login attempt",
                       user_id="testuser", source_ip="192.168.1.100")
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Structured JSON log formatter for Cloud Run / GCP Cloud Logging.

    Output fields:
      - timestamp: ISO 8601 UTC
      - severity: Log level (maps to GCP Cloud Logging severity)
      - message: Human-readable message
      - logger: Logger name
      - module: Source module
      - lineno: Source line number
      - event_type: Security event classification
      - user_id: Authenticated user or 'anonymous'
      - source_ip: Request source IP or 'internal'
      - request_id: Correlation ID for request tracing
      - service: Service name (e.g. 'chad-dashboard')
    """

    # Map Python log levels to GCP Cloud Logging severity
    SEVERITY_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": self.SEVERITY_MAP.get(record.levelname, record.levelname),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "lineno": record.lineno,
            "thread": record.threadName,
            "process": record.processName,
            # Security context fields (set via `extra={}` on log calls)
            "event_type": getattr(record, "event_type", "application_event"),
            "user_id": getattr(record, "user_id", "anonymous"),
            "source_ip": getattr(record, "source_ip", "internal"),
            "request_id": getattr(record, "request_id", ""),
            "service": getattr(record, "service", "architect-ai-pro"),
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra custom fields
        for key in ("details", "duration_ms", "status_code", "method", "path"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Logger Setup
# ---------------------------------------------------------------------------

def setup_security_logger(
    name: str,
    level: int = logging.INFO,
    service: Optional[str] = None,
) -> logging.Logger:
    """
    Create and configure a structured JSON logger.

    Args:
        name: Logger name (e.g. 'dashboard-server', 'gallery').
        level: Minimum log level (default: INFO).
        service: Service name for log entries. Defaults to `name`.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    # Prevent propagation to root logger (avoids double-logging)
    logger.propagate = False

    # Store service name as a default for all log records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "service") or record.service == "architect-ai-pro":
            record.service = service or name
        return record

    logging.setLogRecordFactory(record_factory)

    return logger


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def log_security_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    level: int = logging.INFO,
    **context,
) -> None:
    """
    Log a security-relevant event with structured context.

    Args:
        logger: The logger instance to use.
        event_type: Classification (e.g. 'auth_success', 'auth_failure',
                    'audit_trigger', 'prompt_injection_detected',
                    'plugin_integrity_fail', 'rate_limit_exceeded').
        message: Human-readable description.
        level: Log level (default: INFO).
        **context: Additional fields (user_id, source_ip, request_id, etc.)
    """
    extra = {"event_type": event_type}
    extra.update(context)
    logger.log(level, message, extra=extra)


def generate_request_id() -> str:
    """Generate a unique request ID for correlation."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Request Logging Helpers (Flask)
# ---------------------------------------------------------------------------

def get_client_ip(request) -> str:
    """
    Extract client IP from a Flask/Werkzeug request, respecting
    X-Forwarded-For (set by Cloud Run load balancer).
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def log_request_start(logger: logging.Logger, request, request_id: str) -> None:
    """Log the start of an HTTP request."""
    from flask import g
    g.request_id = request_id

    logger.info(
        f"{request.method} {request.path}",
        extra={
            "event_type": "request_start",
            "method": request.method,
            "path": request.path,
            "source_ip": get_client_ip(request),
            "request_id": request_id,
            "user_id": getattr(request, "authenticated_user", "anonymous"),
        },
    )


def log_request_end(
    logger: logging.Logger,
    request,
    response,
    request_id: str,
    duration_ms: float,
) -> None:
    """Log the completion of an HTTP request."""
    level = logging.INFO if response.status_code < 400 else logging.WARNING
    logger.log(
        level,
        f"{request.method} {request.path} → {response.status_code} ({duration_ms:.0f}ms)",
        extra={
            "event_type": "request_end",
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "source_ip": get_client_ip(request),
            "request_id": request_id,
        },
    )
