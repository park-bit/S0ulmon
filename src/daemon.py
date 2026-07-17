"""Application entry point for solar-aggregator.

Responsibilities:

1. Bootstrap logging and validate settings from the environment.
2. Instantiate :class:`SolarAggregator` and :class:`Notifier`.
3. Run one immediate fetch on startup.
4. Schedule periodic fetches every ``settings.poll_interval_minutes`` minutes
   using the ``schedule`` library.
5. Block in the run-loop until interrupted.

Run::

    python -m src.main              # from project root
    # or
    python src/main.py

Environment:
    Requires a ``.env`` file in the project root with all variables
    defined in ``.env.example``.
"""

from __future__ import annotations

import json
import signal
import sys
import time
from types import FrameType
from typing import Any, Optional

import schedule

from src.config import settings
from src.services.aggregator import SolarAggregator
from src.services.notifier import Notifier, default_notifier
from src.utils.logger import logger, setup_logger

__all__ = ["main"]

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_aggregator: Optional[SolarAggregator] = None
_running: bool = True


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def _handle_shutdown(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGINT / SIGTERM for graceful shutdown.

    Args:
        signum: Signal number received.
        frame: Current stack frame (unused).
    """
    global _running
    logger.info("Shutdown signal {sig} received — stopping.", sig=signum)
    _running = False


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------


def _run_fetch_job(aggregator: SolarAggregator, notifier: Notifier) -> None:
    """Execute one complete fetch cycle.

    * Fetches data from both providers.
    * Logs the combined summary.
    * Evaluates notification rules.
    * Pretty-prints the full result to stdout (dev convenience).

    Args:
        aggregator: The shared :class:`SolarAggregator` instance.
        notifier: The shared :class:`Notifier` instance.
    """
    logger.info("─── Fetch cycle started ───")
    try:
        result: dict[str, Any] = aggregator.fetch_all()

        combined = result.get("combined", {})
        logger.info(
            "Combined | today={today} kWh | live={live} kW",
            today=combined.get("today_generation"),
            live=combined.get("live_power"),
        )

        # Log per-provider summaries
        for provider in ("renac", "shinemonitor"):
            pdata = result.get(provider, {})
            err = result.get("errors", {}).get(provider)
            if err:
                logger.warning("{provider} error: {err}", provider=provider, err=err)
            else:
                logger.info(
                    "{provider} | today={t} kWh | live={l} kW",
                    provider=provider,
                    t=pdata.get("today_generation"),
                    l=pdata.get("live_power"),
                )

        # Evaluate notification rules
        alerts = notifier.evaluate(result)
        if alerts:
            logger.warning("{n} alert(s) fired this cycle.", n=len(alerts))

        # Pretty-print for local development; redirect stdout to /dev/null in prod
        print(json.dumps(result, indent=2, default=str))

    except Exception as exc:  # noqa: BLE001
        logger.exception("Fetch cycle failed unexpectedly: {exc}", exc=exc)

    logger.info("─── Fetch cycle complete ───")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Application bootstrap and run-loop.

    Raises:
        SystemExit: With code 1 if startup validation fails.
    """
    global _aggregator, _running

    # 1. Logging
    setup_logger(settings.log_level)
    logger.info("solar-aggregator starting up.")
    logger.info(
        "Config | RENAC={r} | ShineMonitor={s} | poll={p}min | timeout={t}s",
        r=settings.renac_base_url,
        s=settings.shinemonitor_base_url,
        p=settings.poll_interval_minutes,
        t=settings.http_timeout,
    )

    # 2. Signal handlers
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # 3. Aggregator + Notifier
    _aggregator = SolarAggregator()
    notifier = default_notifier()

    # 4. Login — abort if all providers fail
    try:
        _aggregator.login_all()
    except RuntimeError as exc:
        logger.critical("Cannot start — all providers failed: {exc}", exc=exc)
        sys.exit(1)

    # 5. Immediate first fetch
    _run_fetch_job(_aggregator, notifier)

    # 6. Schedule recurring fetches
    schedule.every(settings.poll_interval_minutes).minutes.do(
        _run_fetch_job, aggregator=_aggregator, notifier=notifier
    )
    logger.info(
        "Scheduler active — polling every {n} minute(s).",
        n=settings.poll_interval_minutes,
    )

    # 7. Run-loop
    try:
        while _running:
            schedule.run_pending()
            time.sleep(1)
    finally:
        logger.info("solar-aggregator shutting down — cleaning up …")
        if _aggregator:
            _aggregator.close()
        logger.info("solar-aggregator stopped.")


if __name__ == "__main__":
    main()
