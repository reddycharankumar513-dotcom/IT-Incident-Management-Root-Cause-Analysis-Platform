import logging
import re
from typing import List
from app.config import settings

# Sensitive patterns to redact in log messages
SENSITIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"(password['\"]?\s*[:=]\s*['\"]?)([^'\"\s&,]+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?)([^'\"\s&,]+)", re.IGNORECASE),
    re.compile(r"(token['\"]?\s*[:=]\s*['\"]?)([^'\"\s&,]+)", re.IGNORECASE),
    re.compile(r"(secret['\"]?\s*[:=]\s*['\"]?)([^'\"\s&,]+)", re.IGNORECASE),
    # Credit Card pattern (13-16 digits)
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    # Generic credential query parameter pattern
    re.compile(r"(auth=)[^&\s]+", re.IGNORECASE),
]

class SensitiveDataFilter(logging.Filter):
    """
    Log filter that masks sensitive data such as passwords, API keys, and bearer tokens.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if not settings.LOG_SENSITIVE_DATA_MASKING:
            return True

        if isinstance(record.msg, str):
            record.msg = self.mask_sensitive(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.mask_sensitive(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.mask_sensitive(v) if isinstance(v, str) else v for v in record.args)
        return True

    @staticmethod
    def mask_sensitive(text: str) -> str:
        masked = text
        for pattern in SENSITIVE_PATTERNS:
            if "password" in pattern.pattern or "key" in pattern.pattern or "token" in pattern.pattern or "secret" in pattern.pattern or "bearer" in pattern.pattern:
                masked = pattern.sub(r"\1***REDACTED***", masked)
            else:
                masked = pattern.sub("***REDACTED_SENSITIVE***", masked)
        return masked

def setup_logging():
    level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Check if handler already attached
    if not any(isinstance(f, SensitiveDataFilter) for h in root_logger.handlers for f in h.filters):
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        root_logger.handlers = [handler]

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("incident_platform")
