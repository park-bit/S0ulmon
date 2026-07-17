"""Solar data aggregator — combines data from all providers.

:class:`SolarAggregator` is the single point of truth for the application.
It owns both provider clients, handles login, fetches data independently
per provider, normalises units, and returns a unified response dict.

Return shape::

    {
        "renac": {
            "today_generation": float,   # kWh
            "month_generation": float,
            "total_generation": float,
            "live_power": float,         # kW
            "weather": { ... },
            "device_status": [ ... ],
        },
        "shinemonitor": { ... },         # same shape
        "combined": {
            "today_generation": float,   # sum of both providers (kWh)
            "live_power": float,         # sum of both providers (kW)
            "timestamp": str,            # ISO-8601 UTC
        },
        "errors": {                      # populated if a provider fails
            "renac": "error message or null",
            "shinemonitor": "error message or null",
        }
    }

Usage::

    from src.services.aggregator import SolarAggregator

    agg = SolarAggregator()
    agg.login_all()
    result = agg.fetch_all()
    summary = agg.get_today_summary()
    live = agg.get_live_summary()
    renac = agg.get_provider("renac")
    combined = agg.get_combined_generation()
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from src.clients.renac import RenacClient, RenacError
from src.clients.shinemonitor import ShineMonitorClient, ShineMonitorError
from src.utils.logger import logger

__all__ = ["SolarAggregator"]


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


def _safe_sum(*values: Optional[float]) -> Optional[float]:
    """Sum non-None values; return ``None`` if ALL inputs are ``None``.

    Args:
        *values: Float values or ``None``.

    Returns:
        Summed float or ``None``.
    """
    non_none = [v for v in values if v is not None]
    return sum(non_none) if non_none else None


def _utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO-8601 string.

    Returns:
        UTC datetime string with timezone suffix, e.g. ``"2024-01-15T10:30:00+00:00"``.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class SolarAggregator:
    """Aggregates solar generation data from RENAC and ShineMonitor.

    Args:
        renac_client: Optional pre-configured :class:`RenacClient`.
            A default instance is created if not supplied.
        shinemonitor_client: Optional pre-configured :class:`ShineMonitorClient`.
            A default instance is created if not supplied.
    """

    def __init__(
        self,
        renac_client: Optional[RenacClient] = None,
        shinemonitor_client: Optional[ShineMonitorClient] = None,
    ) -> None:
        self._renac = renac_client or RenacClient()
        self._shinemonitor = shinemonitor_client or ShineMonitorClient()
        logger.info("SolarAggregator initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login_all(self) -> None:
        """Authenticate with all providers.

        Attempts login for each provider independently; failures are
        logged but do not prevent the other provider from authenticating.

        Raises:
            RuntimeError: If ALL providers fail to authenticate.
        """
        failures: list[str] = []

        logger.info("SolarAggregator: logging in to RENAC …")
        try:
            self._renac.login()
        except RenacError as exc:
            logger.error("RENAC login failed: {exc}", exc=exc)
            failures.append(f"renac: {exc}")

        logger.info("SolarAggregator: logging in to ShineMonitor …")
        try:
            self._shinemonitor.login()
        except ShineMonitorError as exc:
            logger.error("ShineMonitor login failed: {exc}", exc=exc)
            failures.append(f"shinemonitor: {exc}")

        if len(failures) == 2:
            raise RuntimeError(
                f"All providers failed to authenticate: {'; '.join(failures)}"
            )

    def fetch_all(self) -> dict[str, Any]:
        """Fetch, normalise, and combine data from both providers.

        Each provider is fetched independently; errors populate the
        ``errors`` key in the response without aborting the other provider.

        Returns:
            Unified dict with ``renac``, ``shinemonitor``, ``combined``,
            and ``errors`` top-level keys.
        """
        logger.info("SolarAggregator.fetch_all() started.")

        renac_data, renac_error = self._fetch_renac()
        sm_data, sm_error = self._fetch_shinemonitor()

        combined = self._combine(renac_data, sm_data)

        result: dict[str, Any] = {
            "renac": renac_data,
            "shinemonitor": sm_data,
            "combined": combined,
            "errors": {
                "renac": renac_error,
                "shinemonitor": sm_error,
            },
        }

        logger.info(
            "SolarAggregator.fetch_all() complete | "
            "combined_today={today} kWh live={live} kW",
            today=combined.get("today_generation"),
            live=combined.get("live_power"),
        )
        # Cache last result for convenience methods
        self._last_result: dict[str, Any] = result
        return result

    def get_today_summary(self) -> dict[str, Any]:
        """Return a concise today-generation summary across both providers.

        Runs a full fetch if no cached result exists.

        Returns:
            Dict with keys:
            ``renac_today``, ``shinemonitor_today``, ``combined_today`` (all kWh),
            and ``timestamp``.
        """
        result = getattr(self, "_last_result", None) or self.fetch_all()
        return {
            "renac_today_kwh": result.get("renac", {}).get("today_generation"),
            "shinemonitor_today_kwh": result.get("shinemonitor", {}).get("today_generation"),
            "combined_today_kwh": result.get("combined", {}).get("today_generation"),
            "timestamp": _utc_now_iso(),
        }

    def get_live_summary(self) -> dict[str, Any]:
        """Return a concise live-power summary across both providers.

        Runs a full fetch if no cached result exists.

        Returns:
            Dict with keys:
            ``renac_live``, ``shinemonitor_live``, ``combined_live`` (all kW),
            and ``timestamp``.
        """
        result = getattr(self, "_last_result", None) or self.fetch_all()
        return {
            "renac_live_kw": result.get("renac", {}).get("live_power"),
            "shinemonitor_live_kw": result.get("shinemonitor", {}).get("live_power"),
            "combined_live_kw": result.get("combined", {}).get("live_power"),
            "timestamp": _utc_now_iso(),
        }

    def get_provider(self, provider_name: str) -> dict[str, Any]:
        """Return the raw normalised data dict for a single provider.

        Args:
            provider_name: One of ``"renac"`` or ``"shinemonitor"``.

        Returns:
            Provider data dict from the last fetch (may be empty if that
            provider errored). Runs a full fetch if no cached result exists.

        Raises:
            ValueError: If *provider_name* is not a recognised provider.
        """
        if provider_name not in ("renac", "shinemonitor"):
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                "Valid values: 'renac', 'shinemonitor'."
            )
        result = getattr(self, "_last_result", None) or self.fetch_all()
        return result.get(provider_name, {})

    def get_combined_generation(self) -> dict[str, Any]:
        """Return the combined generation totals across all providers.

        Runs a full fetch if no cached result exists.

        Returns:
            Dict with ``today_generation`` (kWh), ``month_generation`` (kWh),
            ``total_generation`` (kWh), ``live_power`` (kW), and ``timestamp``.
        """
        result = getattr(self, "_last_result", None) or self.fetch_all()
        return result.get("combined", {})

    def fetch_renac(self) -> dict[str, Any]:
        """Fetch and normalise RENAC data only.

        Returns:
            RENAC data dict (may be empty on error).
        """
        data, error = self._fetch_renac()
        if error:
            logger.warning("RENAC fetch error: {e}", e=error)
        return data

    def fetch_shinemonitor(self) -> dict[str, Any]:
        """Fetch and normalise ShineMonitor data only.

        Returns:
            ShineMonitor data dict (may be empty on error).
        """
        data, error = self._fetch_shinemonitor()
        if error:
            logger.warning("ShineMonitor fetch error: {e}", e=error)
        return data

    def close(self) -> None:
        """Release resources for all provider clients."""
        try:
            self._renac.logout()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._renac.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._shinemonitor.close()
        except Exception:  # noqa: BLE001
            pass
        logger.info("SolarAggregator closed.")

    def __enter__(self) -> "SolarAggregator":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private fetch helpers
    # ------------------------------------------------------------------

    def _fetch_renac(self) -> tuple[dict[str, Any], Optional[str]]:
        """Fetch all relevant data from RENAC.

        Returns:
            Tuple of ``(data_dict, error_string_or_None)``.
        """
        try:
            overview = self._renac.overview()
            weather = self._renac.get_weather()
            device_status = self._renac.get_device_status()
            storage = {}
            try:
                storage = self._renac.storage_overview()
            except RenacError as exc:
                logger.debug("RENAC storage_overview skipped: {exc}", exc=exc)

            data: dict[str, Any] = {
                "today_generation": overview.get("today_generation"),   # kWh
                "month_generation": overview.get("month_generation"),   # kWh
                "total_generation": overview.get("total_generation"),   # kWh
                "live_power": overview.get("live_power"),               # kW
                "installed_capacity": overview.get("installed_capacity"),
                "performance_ratio": overview.get("performance_ratio"),
                "co2_saved": overview.get("co2_saved"),
                "irradiation": overview.get("irradiation"),
                "weather": weather,
                "device_status": device_status,
                "storage": storage if storage else None,
                "history": self._renac.get_daily_yield_history(_utc_now_iso()[:10]),
                "timestamp": _utc_now_iso(),
            }
            return data, None

        except RenacError as exc:
            logger.error("RENAC fetch error: {exc}", exc=exc)
            return {}, str(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected RENAC error: {exc}", exc=exc)
            return {}, str(exc)

    def _fetch_shinemonitor(self) -> tuple[dict[str, Any], Optional[str]]:
        """Fetch all relevant data from ShineMonitor.

        Returns:
            Tuple of ``(data_dict, error_string_or_None)``.
        """
        try:
            detail = self._shinemonitor.queryPlantInfo()
            device_status = self._shinemonitor.get_device_status()
            
            # Use specialized wrappers for energy since the new API doesn't return them in PlantInfo
            today_gen = self._shinemonitor.get_today_generation()
            live_power_kw = self._shinemonitor.get_live_power()
            
            warnings = []
            try:
                raw_warnings = self._shinemonitor.queryWarnings()
                warnings = [
                    w.model_dump(by_alias=False, exclude_none=True)
                    for w in raw_warnings
                ]
            except ShineMonitorError as exc:
                logger.debug("ShineMonitor queryWarnings skipped: {exc}", exc=exc)

            data: dict[str, Any] = {
                "today_generation": today_gen,
                "month_generation": None,  # Not directly available in new API yet
                "total_generation": None,  # Not directly available in new API yet
                "live_power": live_power_kw,
                "installed_capacity": detail.installed_power if detail else None,
                "co2_saved": detail.co2 if detail else None,
                "today_income": detail.today_income if detail else None,
                "total_income": detail.total_income if detail else None,
                "currency": detail.currency if detail else None,
                "plant_status": detail.status if detail else None,
                "weather": None,
                "device_status": device_status,
                "warnings": warnings,
                "history": self._shinemonitor.get_daily_yield_history(num_days=7),
                "timestamp": _utc_now_iso(),
            }
            return data, None

        except ShineMonitorError as exc:
            logger.error("ShineMonitor fetch error: {exc}", exc=exc)
            return {}, str(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected ShineMonitor error: {exc}", exc=exc)
            return {}, str(exc)

    # ------------------------------------------------------------------
    # Normalisation / combination
    # ------------------------------------------------------------------

    def _combine(
        self,
        renac: dict[str, Any],
        shinemonitor: dict[str, Any],
    ) -> dict[str, Any]:
        """Produce a unified combined summary from both provider data dicts.

        All generation values are assumed to be in kWh and power in kW.
        Summation is ``None``-safe: if one provider is unavailable only the
        available provider's value is used.

        Args:
            renac: Normalised RENAC data dict (may be empty).
            shinemonitor: Normalised ShineMonitor data dict (may be empty).

        Returns:
            Dict with ``today_generation``, ``live_power``, and ``timestamp``.
        """
        combined = {}
        
        # 1. Today generation
        r_today = renac.get("today_generation")
        s_today = shinemonitor.get("today_generation")
        if r_today is not None and s_today is not None:
            combined["today_generation"] = round(r_today + s_today, 2)
        elif r_today is not None:
            combined["today_generation"] = round(r_today, 2)
        elif s_today is not None:
            combined["today_generation"] = round(s_today, 2)

        # 2. Live power
        r_power = renac.get("live_power")
        s_power = shinemonitor.get("live_power")
        if r_power is not None and s_power is not None:
            combined["live_power"] = round(r_power + s_power, 2)
        elif r_power is not None:
            combined["live_power"] = round(r_power, 2)
        elif s_power is not None:
            combined["live_power"] = round(s_power, 2)

        # 3. Month generation
        r_month = renac.get("month_generation")
        s_month = shinemonitor.get("month_generation")
        if r_month is not None and s_month is not None:
            combined["month_generation"] = round(r_month + s_month, 2)
        elif r_month is not None:
            combined["month_generation"] = round(r_month, 2)
        elif s_month is not None:
            combined["month_generation"] = round(s_month, 2)

        # 4. Total generation
        r_total = renac.get("total_generation")
        s_total = shinemonitor.get("total_generation")
        if r_total is not None and s_total is not None:
            combined["total_generation"] = round(r_total + s_total, 2)
        elif r_total is not None:
            combined["total_generation"] = round(r_total, 2)
        elif s_total is not None:
            combined["total_generation"] = round(s_total, 2)
        
        # 5. Combine history by day for the last 7 days
        import datetime
        combined_history = {}
        for i in range(7):
            day_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            r_val = renac.get("history", {}).get(day_str, 0.0)
            s_val = shinemonitor.get("history", {}).get(day_str, 0.0)
            combined_history[day_str] = r_val + s_val
        combined["history"] = combined_history

        now = datetime.datetime.now(datetime.timezone.utc)
        combined["timestamp"] = now.isoformat()

        return combined


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logger.info("=== SolarAggregator self-test ===")

    with SolarAggregator() as agg:
        try:
            agg.login_all()
        except RuntimeError as exc:
            logger.error("login_all failed: {exc}", exc=exc)
            raise

        result = agg.fetch_all()
        print("\n--- fetch_all() ---")
        print(json.dumps(result, indent=2, default=str))

        print("\n--- get_today_summary() ---")
        print(json.dumps(agg.get_today_summary(), indent=2, default=str))

        print("\n--- get_live_summary() ---")
        print(json.dumps(agg.get_live_summary(), indent=2, default=str))

        print("\n--- get_combined_generation() ---")
        print(json.dumps(agg.get_combined_generation(), indent=2, default=str))

        print("\n--- get_provider('renac') ---")
        print(json.dumps(agg.get_provider("renac"), indent=2, default=str))

        print("\n--- get_provider('shinemonitor') ---")
        print(json.dumps(agg.get_provider("shinemonitor"), indent=2, default=str))
