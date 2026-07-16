"""Centralised loguru configuration for solar-aggregator.

All modules should import ``logger`` from here instead of creating their own
loguru instances so that the sink configuration (format, level, rotation) is
applied exactly once at import time.

Usage::

    from src.utils.logger import logger
    logger.info("Hello {name}", name="world")
"""

import sys
from pathlib import Path

from loguru import logger  # re-exported for consumers

__all__ = ["logger", "setup_logger"]

_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


def setup_logger(level: str = "INFO") -> None:
    """Configure loguru sinks.

    Removes the default stderr sink and adds:

    * A coloured stderr sink at the requested level.
    * A rotating file sink that keeps 7 days of logs.

    Args:
        level: Minimum log level string (``"DEBUG"``, ``"INFO"``, etc.).
               Sourced from ``Settings.log_level`` at startup.
    """
    logger.remove()  # remove default handler

    # --- stderr (human-readable, coloured) ---
    logger.add(
        sys.stderr,
        level=level,
        format=_LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # --- rotating file sink ---
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        _LOG_DIR / "solar-aggregator_{time:YYYY-MM-DD}.log",
        level=level,
        format=_LOG_FORMAT,
        rotation="00:00",       # new file every midnight
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=False,         # suppress local variable dump in file sink
        encoding="utf-8",
    )

    logger.debug("Logger initialised at level={level}", level=level)


# Initialise with INFO defaults so any early-import logging works before
# setup_logger() is called with the value from Settings.
setup_logger("INFO")


if __name__ == "__main__":
    setup_logger("DEBUG")
    logger.trace("trace msg")
    logger.debug("debug msg")
    logger.info("info msg")
    logger.warning("warning msg")
    logger.error("error msg")
    logger.success("success msg")
    logger.critical("critical msg")
    print("Logger test complete — check logs/ directory for the file sink.")
