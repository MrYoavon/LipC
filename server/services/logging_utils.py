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
    Configure root + library loggers.
    Call exactly once, as early as possible.
    """
    level = level or os.getenv("LOG_LEVEL", "INFO").upper()

    Path(logs_dir).mkdir(exist_ok=True)

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,          # keep 3rd-party logs
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                "datefmt": "%d-%m-%Y %H:%M:%S",
            },
            # nice if I later want JSON logs
            # "json": { "()": "pythonjsonlogger.jsonlogger.JsonFormatter", "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s" },
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

    logging.config.dictConfig(LOGGING_CONFIG)
