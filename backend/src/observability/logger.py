"""
Structured logging configuration with context.
Provides consistent logging across the application.
"""
import logging
import sys
from typing import Any
from src.config import settings


def setup_logging():
    """Configure application logging."""
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)


class ContextLogger:
    """Logger with additional context (session_id, customer_id, etc.)."""
    
    def __init__(self, name: str, context: dict[str, Any] | None = None):
        self.logger = logging.getLogger(name)
        self.context = context or {}
    
    def _format_message(self, msg: str) -> str:
        """Add context to log message."""
        if self.context:
            context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{context_str} | {msg}"
        return msg
    
    def debug(self, msg: str, **kwargs):
        self.logger.debug(self._format_message(msg), **kwargs)
    
    def info(self, msg: str, **kwargs):
        self.logger.info(self._format_message(msg), **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self.logger.warning(self._format_message(msg), **kwargs)
    
    def error(self, msg: str, **kwargs):
        self.logger.error(self._format_message(msg), **kwargs)
    
    def critical(self, msg: str, **kwargs):
        self.logger.critical(self._format_message(msg), **kwargs)
