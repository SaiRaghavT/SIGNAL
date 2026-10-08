"""Persistent, privacy-conscious logging for AI document detection."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOGGER_NAME = "signal.ai_detection"
_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3


def get_ai_detection_logger() -> logging.Logger:
    """Return the shared AI logger, writing to a rotating backend log file."""

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = Path(__file__).resolve().parents[1] / "logs" / "ai_detection.log"
    if not any(getattr(handler, "_signal_ai_detection_file", False) for handler in logger.handlers):
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                log_path,
                maxBytes=_MAX_LOG_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-7s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            handler._signal_ai_detection_file = True  # type: ignore[attr-defined]
            logger.addHandler(handler)
        except OSError:
            print(
                f"Could not create AI detection log file at {log_path}",
                file=sys.stderr,
            )

    if not any(getattr(handler, "_signal_ai_detection_console", False) for handler in logger.handlers):
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        console._signal_ai_detection_console = True  # type: ignore[attr-defined]
        logger.addHandler(console)

    if not getattr(logger, "_signal_ai_detection_ready_logged", False):
        logger.info("AI detection logging ready file=%s console=stdout", log_path)
        logger._signal_ai_detection_ready_logged = True  # type: ignore[attr-defined]

    return logger
