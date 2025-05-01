# services/logging_utils.py
import os
import logging
import logging.config
from pathlib import Path


def setup_logging(
        level: str = None,
        logs_dir: str = "logs",
        log_file: str = "server.log") -> None:
    """
    Configure application-wide logging with console and rotating file handlers.

    Args:
        level (str, optional): Logging level (e.g., "INFO", "DEBUG").
            Defaults to the LOG_LEVEL environment variable or "INFO".
        logs_dir (str, optional): Directory path to store log files.
            Will be created if it does not exist. Defaults to "logs".
        log_file (str, optional): Filename for the main log file within logs_dir.
            Defaults to "server.log".

    Returns:
        None

    Raises:
        OSError: If the logs_dir directory cannot be created.
    """
    # Determine logging level
    level = level or os.getenv("LOG_LEVEL", "INFO").upper()

    # Ensure log directory exists
    Path(logs_dir).mkdir(exist_ok=True)

    # Logging configuration dictionary
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,          # keep 3rd-party logs
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                "datefmt": "%d-%m-%Y %H:%M:%S",
            },
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler",
                        "formatter": "default",
                        "level": level},
            "file":    {"class": "logging.handlers.TimedRotatingFileHandler",
                        "formatter": "default",
                        "filename": f"{logs_dir}/{log_file}",
                        "when": "midnight",
                        "backupCount": 14,
                        "encoding": "utf-8",
                        "level": level},
            "errors":  {"class": "logging.handlers.RotatingFileHandler",
                        "formatter": "default",
                        "filename": f"{logs_dir}/server-error.log",
                        "maxBytes": 10 * 1024 * 1024,    # 10 MiB
                        "backupCount": 5,
                        "encoding": "utf-8",
                        "level": "ERROR"},
        },
        "root": {"level": level,
                 "handlers": ["console", "file", "errors"]},
    }

    # Apply configuration
    logging.config.dictConfig(LOGGING_CONFIG)
