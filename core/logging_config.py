from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, debug: bool = False) -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_interview_review_configured", False):
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    log_level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger._interview_review_configured = True

