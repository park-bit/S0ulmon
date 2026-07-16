"""Abstract base class that all solar provider clients must implement.

Defines the common interface consumed by :class:`src.services.aggregator.SolarAggregator`
so the aggregator can treat RENAC and ShineMonitor clients interchangeably.

Usage::

    from src.clients.base import SolarProviderBase

    class MyProvider(SolarProviderBase):
        def login(self) -> None: ...
        def get_today_generation(self) -> Optional[float]: ...
        # … etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

__all__ = ["SolarProviderBase"]


class SolarProviderBase(ABC):
    """Abstract interface for solar monitoring provider clients.

    Every concrete provider must implement all abstract methods.
    The aggregator calls only these methods — provider-specific extras
    are accessed directly when needed.
    """

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @abstractmethod
    def login(self) -> None:
        """Authenticate with the provider and store credentials / tokens.

        Raises:
            Exception: Provider-specific auth exception on failure.
        """

    # ------------------------------------------------------------------
    # Generation statistics
    # ------------------------------------------------------------------

    @abstractmethod
    def get_today_generation(self) -> Optional[float]:
        """Return energy generated today in kWh.

        Returns:
            Float kWh value, or ``None`` if data is unavailable.
        """

    @abstractmethod
    def get_month_generation(self) -> Optional[float]:
        """Return energy generated this calendar month in kWh.

        Returns:
            Float kWh value, or ``None`` if data is unavailable.
        """

    @abstractmethod
    def get_total_generation(self) -> Optional[float]:
        """Return total cumulative energy generated in kWh.

        Returns:
            Float kWh value, or ``None`` if data is unavailable.
        """

    # ------------------------------------------------------------------
    # Live data
    # ------------------------------------------------------------------

    @abstractmethod
    def get_live_power(self) -> Optional[float]:
        """Return current live output power in kW.

        Returns:
            Float kW value, or ``None`` if data is unavailable.
        """

    # ------------------------------------------------------------------
    # Environmental / ancillary data
    # ------------------------------------------------------------------

    @abstractmethod
    def get_weather(self) -> Optional[dict[str, Any]]:
        """Return current weather conditions at the plant site.

        Returns:
            Dict with at least ``temperature`` (°C) and any other
            provider-supplied fields, or ``None`` if unavailable.
        """

    @abstractmethod
    def get_device_status(self) -> Optional[list[dict[str, Any]]]:
        """Return operational status for all devices in the plant.

        Returns:
            List of dicts — one per device — with at least ``status``
            and ``device_name`` keys; or ``None`` if unavailable.
        """
