"""Pydantic v2 models for ShineMonitor (Eybond SmartClient) API responses.

ShineMonitor wraps all responses in a common envelope::

    {
        "err": 0,
        "info": "success",
        "dat": { ... }   // or list
    }

``err == 0`` indicates success; any other value is an API-level error.

These models are consumed by :mod:`src.clients.shinemonitor` and
:mod:`src.services.aggregator`.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

__all__ = [
    "ShineMonitorResponse",
    "ShineMonitorAuthData",
    "ShineMonitorAuthResponse",
    "PlantInfo",
    "PlantsInfoResponse",
    "PlantDetail",
    "PlantDetailResponse",
    "EnergyDayPoint",
    "PlantEnergyMonthPerDayResponse",
    "DevicePvChartPoint",
    "TodayDevicePvChartsResponse",
    "PowerDayPoint",
    "PlantActiveOutputPowerOneDayResponse",
    "DeviceStatus",
    "PlantDeviceStatusResponse",
    "ElectricmeterData",
    "PlantElectricmeterResponse",
    "CameraInfo",
    "PlantCameraResponse",
    "WarningItem",
    "WarningsResponse",
]


# ---------------------------------------------------------------------------
# Generic envelope
# ---------------------------------------------------------------------------


class ShineMonitorResponse(BaseModel):
    """Generic ShineMonitor API response envelope.

    Args:
        err: Error code. ``0`` = success, anything else = failure.
        info: Human-readable status message.
        dat: Endpoint-specific payload (may be ``None`` on error).
    """

    err: int = Field(..., description="Error code; 0 = success.")
    info: Optional[str] = Field(None, description="Status message.")
    dat: Optional[Any] = Field(None, description="Endpoint-specific payload.")

    @property
    def is_success(self) -> bool:
        """Return ``True`` when ``err == 0``."""
        return self.err == 0


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class ShineMonitorAuthData(BaseModel):
    """Payload returned by the ``action=auth`` endpoint.

    Args:
        token: Session token to include in all subsequent requests.
        secret: Session secret used to compute per-request signatures.
        expire: Unix timestamp after which the token must be refreshed.
    """

    token: str = Field(..., description="Session bearer token.")
    secret: str = Field(..., description="Session secret for signing.")
    expire: int = Field(..., description="Token expiry as Unix epoch.")


class ShineMonitorAuthResponse(ShineMonitorResponse):
    """Typed wrapper for the auth endpoint response."""

    dat: Optional[ShineMonitorAuthData] = None


# ---------------------------------------------------------------------------
# queryPlantsInfo — list all plants
# ---------------------------------------------------------------------------


class PlantInfo(BaseModel):
    """Summary record for a single plant.

    Args:
        plant_id: Unique plant identifier (used in subsequent queries).
        plant_name: Human-readable plant name.
        installed_power: Rated capacity in kWp.
        today_income: Revenue earned today.
        total_income: Cumulative revenue.
        currency: Currency code (e.g. ``"EUR"``).
        status: Plant operational status (1 = normal).
        country: Country code or name.
        timezone: Timezone offset string (e.g. ``"+05:30"``).
    """

    plant_id: Optional[str] = Field(None, alias="pid")
    plant_name: Optional[str] = Field(None, alias="pname")
    installed_power: Optional[float] = Field(None, alias="pac")
    today_income: Optional[float] = Field(None, alias="todayIncome")
    total_income: Optional[float] = Field(None, alias="totalIncome")
    currency: Optional[str] = Field(None, alias="currency")
    status: Optional[int] = Field(None, alias="status")
    country: Optional[str] = Field(None, alias="country")
    timezone: Optional[str] = Field(None, alias="timezone")

    model_config = {"populate_by_name": True}


class PlantsInfoData(BaseModel):
    info: Optional[list[PlantInfo]] = None


class PlantsInfoResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantsInfo response."""

    dat: Optional[PlantsInfoData] = None


# ---------------------------------------------------------------------------
# queryPlantInfo — single plant detail
# ---------------------------------------------------------------------------


class PlantDetail(BaseModel):
    """Detailed record for a single plant.

    Args:
        plant_id: Unique plant identifier.
        plant_name: Human-readable name.
        installed_power: Rated capacity in kWp.
        today_energy: Energy generated today in kWh.
        month_energy: Energy generated this month in kWh.
        total_energy: Cumulative energy generated in kWh.
        co2: CO2 saved in kg.
        today_income: Revenue today.
        total_income: Cumulative revenue.
        currency: Currency code.
        pac: Current AC output power in W.
        status: Operational status code.
    """

    plant_id: Optional[str] = Field(None, alias="pn")
    plant_name: Optional[str] = Field(None, alias="plantName")
    installed_power: Optional[float] = Field(None, alias="installedPower")
    today_energy: Optional[float] = Field(None, alias="todayEnergy")
    month_energy: Optional[float] = Field(None, alias="monthEnergy")
    total_energy: Optional[float] = Field(None, alias="totalEnergy")
    co2: Optional[float] = Field(None, alias="co2")
    today_income: Optional[float] = Field(None, alias="todayIncome")
    total_income: Optional[float] = Field(None, alias="totalIncome")
    currency: Optional[str] = Field(None, alias="currency")
    pac: Optional[float] = Field(None, alias="pac")
    status: Optional[int] = Field(None, alias="status")

    model_config = {"populate_by_name": True}


class PlantDetailResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantInfo response."""

    dat: Optional[PlantDetail] = None


# ---------------------------------------------------------------------------
# queryPlantEnergyMonthPerDay — daily breakdown for a month
# ---------------------------------------------------------------------------


class EnergyDayPoint(BaseModel):
    """Energy value for a single day within a month."""
    date: Optional[str] = Field(None, alias="date")
    energy: Optional[float] = Field(None, alias="energy")
    ts: Optional[str] = Field(None, alias="ts")
    val: Optional[Any] = Field(None, alias="val")

    model_config = {"populate_by_name": True}


class PlantEnergyMonthPerDayResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantEnergyMonthPerDay response."""
    dat: Optional[Any] = None


# ---------------------------------------------------------------------------
# queryTodayDevicePvCharts — intraday device PV chart
# ---------------------------------------------------------------------------


class DevicePvChartPoint(BaseModel):
    """A single time/power data point for a device PV chart.

    Args:
        time: Time label (``"HH:MM"``).
        power: AC power output at this time in W.
    """

    time: Optional[str] = Field(None, alias="time")
    power: Optional[float] = Field(None, alias="power")

    model_config = {"populate_by_name": True}


class TodayDevicePvChartsResponse(ShineMonitorResponse):
    """Typed wrapper for the queryTodayDevicePvCharts response."""

    dat: Optional[list[DevicePvChartPoint]] = None


# ---------------------------------------------------------------------------
# queryPlantActiveOuputPowerOneDay — plant power curve for one day
# ---------------------------------------------------------------------------


class PowerDayPoint(BaseModel):
    """A single timestamp/power data point in the daily power curve.

    Args:
        time: Time label string.
        power: Active output power in kW.
    """

    time: Optional[str] = Field(None, alias="time")
    power: Optional[float] = Field(None, alias="power")

    model_config = {"populate_by_name": True}


class PlantActiveOutputPowerOneDayResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantActiveOuputPowerOneDay response."""

    dat: Optional[list[PowerDayPoint]] = None


# ---------------------------------------------------------------------------
# queryPlantDeviceStatus — status of all devices in a plant
# ---------------------------------------------------------------------------


class DeviceStatus(BaseModel):
    """Operational status record for a single device.

    Args:
        device_sn: Device serial number.
        device_name: Human-readable device name.
        device_type: Type code (e.g. ``"inverter"``, ``"battery"``).
        status: Status code (1 = normal, 0 = offline, 2 = fault).
        pac: Current active power output in W.
        error_msg: Active fault message, if any.
    """

    device_sn: Optional[str] = Field(None, alias="sn")
    device_name: Optional[str] = Field(None, alias="alias")
    device_type: Optional[str] = Field(None, alias="devType")
    status: Optional[int] = Field(None, alias="status")
    pac: Optional[float] = Field(None, alias="pac")
    error_msg: Optional[str] = Field(None, alias="errorMsg")

    model_config = {"populate_by_name": True}


class CollectorStatus(BaseModel):
    pn: Optional[str] = Field(None, alias="pn")
    alias: Optional[str] = Field(None, alias="alias")
    status: Optional[int] = Field(None, alias="status")
    device: Optional[list[DeviceStatus]] = None


class PlantDeviceStatusData(BaseModel):
    status: Optional[int] = Field(None, alias="status")
    collector: Optional[list[CollectorStatus]] = None


class PlantDeviceStatusResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantDeviceStatus response."""

    dat: Optional[PlantDeviceStatusData] = None


# ---------------------------------------------------------------------------
# queryPlantElectricmeter — meter readings
# ---------------------------------------------------------------------------


class ElectricmeterData(BaseModel):
    """Electricity meter readings for a plant.

    Args:
        meter_id: Meter identifier.
        import_energy: Energy imported from the grid in kWh.
        export_energy: Energy exported to the grid in kWh.
        active_power: Current active power in kW.
    """

    meter_id: Optional[str] = Field(None, alias="meterId")
    import_energy: Optional[float] = Field(None, alias="importEnergy")
    export_energy: Optional[float] = Field(None, alias="exportEnergy")
    active_power: Optional[float] = Field(None, alias="activePower")

    model_config = {"populate_by_name": True}


class PlantElectricmeterResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantElectricmeter response."""

    dat: Optional[list[ElectricmeterData]] = None


# ---------------------------------------------------------------------------
# queryPlantCamera — camera/monitoring images
# ---------------------------------------------------------------------------


class CameraInfo(BaseModel):
    """Information about a plant monitoring camera.

    Args:
        camera_id: Camera identifier.
        camera_name: Human-readable name.
        snapshot_url: URL of the latest camera snapshot image.
        status: Camera operational status.
    """

    camera_id: Optional[str] = Field(None, alias="cameraId")
    camera_name: Optional[str] = Field(None, alias="cameraName")
    snapshot_url: Optional[str] = Field(None, alias="snapshotUrl")
    status: Optional[int] = Field(None, alias="status")

    model_config = {"populate_by_name": True}


class PlantCameraResponse(ShineMonitorResponse):
    """Typed wrapper for the queryPlantCamera response."""

    dat: Optional[list[CameraInfo]] = None


# ---------------------------------------------------------------------------
# queryWarnings — active alerts / warnings
# ---------------------------------------------------------------------------


class WarningItem(BaseModel):
    """A single active warning or alert record.

    Args:
        warning_id: Unique warning identifier.
        device_sn: Serial number of the affected device.
        warning_code: Numeric fault/warning code.
        warning_desc: Human-readable description.
        start_time: ISO-8601 datetime when the warning was raised.
        end_time: ISO-8601 datetime when the warning was cleared (if resolved).
        level: Severity level (1 = info, 2 = warning, 3 = fault).
    """

    warning_id: Optional[str] = Field(None, alias="warningId")
    device_sn: Optional[str] = Field(None, alias="sn")
    warning_code: Optional[str] = Field(None, alias="warningCode")
    warning_desc: Optional[str] = Field(None, alias="warningDesc")
    start_time: Optional[str] = Field(None, alias="startTime")
    end_time: Optional[str] = Field(None, alias="endTime")
    level: Optional[int] = Field(None, alias="level")

    model_config = {"populate_by_name": True}


class WarningsResponse(ShineMonitorResponse):
    """Typed wrapper for the queryWarnings response."""

    dat: Optional[list[WarningItem]] = None
