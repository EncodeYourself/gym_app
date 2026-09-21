# utils/logging.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_bytes: int = 5_000_000,  # 5 MB
    backup_count: int = 5,
    ) -> None:
    """
    Configure application-wide logging.

    Logs are written to:
        - logs/app.log         (rotating file)
        - logs/errors.log      (errors only, rotating file)
        - stdout               (console)

    Args:
        log_dir: Directory where log files are stored.
        log_level: Minimum log level to record. One of:
            DEBUG, INFO, WARNING, ERROR, CRITICAL.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of backup files to keep.

    Example:
        from utils.logging import setup_logging

        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Application started")
    """

    # --- Create log directory ---
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # --- Convert string level to logging constant ---
    level = getattr(logging, log_level.upper(), logging.INFO)

    # --- Root logger configuration ---
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on rerun
    root_logger.handlers.clear()

    # --- Formatters ---
    standard_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    error_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(standard_formatter)
    root_logger.addHandler(console_handler)

    # --- Rotating file handler for all logs ---
    app_log_file = log_path / "app.log"
    app_file_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(standard_formatter)
    root_logger.addHandler(app_file_handler)

    # --- Rotating file handler for errors only ---
    error_log_file = log_path / "errors.log"
    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_file_handler)

    # --- Reduce noise from noisy libraries ---
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    # --- Log startup ---
    root_logger.info("Logging initialized. Level=%s, directory=%s", log_level, log_path)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        Configured logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Hello")
    """
    return logging.getLogger(name)