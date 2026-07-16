"""Pydantic v2 models for RENAC Power API responses.

Each class maps directly to one RENAC endpoint response schema.
All fields use ``Optional`` with a ``None`` default so that partial
responses (e.g. missing sensors) do not cause validation failures.

These models are used by :mod:`src.clients.renac` for deserialisation
and by :mod:`src.services.aggregator` for normalisation.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

__all__ = [
    "RenacLoginResponse",
    "RenacOverviewResponse",
    "RenacEquipStatResponse",
    "RenacApiResponse",
]


# ----------------------------------------------------------------------------
# Generic envelope
# ----------------------------------------------------------------------------


class RenacApiResponse(BaseModel):
    """Generic RENAC API response envelope.

    All RENAC endpoints return a common structure::

        {
            "code": 1,
            "msg": "0000",
            "data": { ... }
        }

    Args:
        code: Numeric status code (1 = success).
        msg: Human-readable status message.
        data: Endpoint-specific payload (may be null on error).
    """

    code: int = Field(..., description="API status code (1 = OK).")
    msg: str = Field(..., description="Status message.")
    data: Optional[Any] = Field(None, description="Endpoint-specific payload.")

    @property
    def is_success(self) -> bool:
        """Return ``True`` when the response indicates success."""
        return self.code == 1


# ----------------------------------------------------------------------------
# /api/user/login
# ----------------------------------------------------------------------------


class RenacLoginUser(BaseModel):
    """User object containing the session token."""
    token: str = Field(..., description="Session bearer token.")

class RenacLoginResponse(RenacApiResponse):
    """Typed wrapper for the login endpoint response."""
    user: Optional[RenacLoginUser] = None


# ----------------------------------------------------------------------------
# /api/station/overview  (station overview / today stats)
# ----------------------------------------------------------------------------


class RenacOverviewData(BaseModel):
    """Station-level overview data.

    Args:
        day_energy: Energy generated today in kWh.
        month_energy: Energy generated this month in kWh.
        sum_energy: Cumulative energy generated in kWh.
        output_power: Current output power in kW.
    """

    day_energy: Optional[float] = Field(None)
    month_energy: Optional[float] = Field(None)
    sum_energy: Optional[float] = Field(None)
    output_power: Optional[float] = Field(None)


class RenacOverviewResponse(RenacApiResponse):
    """Typed wrapper for the station overview response."""
    data: Optional[RenacOverviewData] = None


# ----------------------------------------------------------------------------
# /api/station/equipStat  (aggregate device status)
# ----------------------------------------------------------------------------


class RenacEquipStatData(BaseModel):
    """Aggregate device status."""

    total_online_equip: Optional[int] = Field(None)
    total_off_equip: Optional[int] = Field(None)
    total_alarm_equip: Optional[int] = Field(None)
    total_equip: Optional[int] = Field(None)


class RenacEquipStatResponse(RenacApiResponse):
    """Typed wrapper for the equipment statistics response."""
    data: Optional[RenacEquipStatData] = None
