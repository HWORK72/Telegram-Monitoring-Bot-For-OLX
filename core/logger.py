import logging
import sys
from typing import Optional
from core.config import get_settings


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    settings = get_settings()
    log_level: str = (level or settings.LOG_LEVEL).upper()
    numeric_level: int = getattr(logging, log_level, logging.INFO)

    log_format: str = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    date_format: str = "%Y-%m-%d %H:%M:%S"

    formatter: logging.Formatter = logging.Formatter(
        fmt=log_format,
        datefmt=date_format,
    )

    handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(formatter)

    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(handler)

    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)

    logger: logging.Logger = logging.getLogger("app")
    logger.info("Logging initialized with level: %s", log_level)
    return logger