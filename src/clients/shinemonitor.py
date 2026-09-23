"""ShineMonitor (Eybond SmartClient) API client.

Implements the common :class:`src.clients.base.SolarProviderBase` interface
and exposes every ShineMonitor-specific endpoint method.

Verified base URL: ``https://web.shinemonitor.com/public/``

Authentication flow (reverse-engineered from browser HAR capture)
-----------------------------------------------------------------
1. GET ``?action=auth`` with:
   - ``usr`` = username
   - ``company-key`` = company key (``bnrl_frRFjEz8Mkn``)
   - ``passwd`` = SHA1(password)
   - ``salt`` = current Unix millisecond timestamp (string)
   - ``sign`` = SHA1(salt + SHA1(password) + "auth")
2. Response ``dat`` contains ``token``, ``secret``, and ``expire``
   (Unix epoch when token expires).
3. Every subsequent request includes:
   - ``token`` = session token
   - ``salt`` = current Unix millisecond timestamp (string)
   - ``sign`` = SHA1(salt + secret + action)
4. When ``expire`` is reached (minus a 60-second buffer),
   :meth:`_ensure_authenticated` transparently re-authenticates.

ShineMonitor API returns::

    {"err": 0, "info": "success", "dat": { ... }}

``err != 0`` indicates an API-level failure even on HTTP 200.

Usage::

    from src.clients.shinemonitor import ShineMonitorClient

    client = ShineMonitorClient()
    client.login()
    plants = client.queryPlantsInfo()
    print(plants)
"""

from __future__ import annotations

import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from src.clients.base import SolarProviderBase
from src.config import settings
from src.models.shinemonitor import (
    CameraInfo,
    DeviceStatus,
    EnergyDayPoint,
    ElectricmeterData,
    PlantActiveOutputPowerOneDayResponse,
    PlantCameraResponse,
    PlantDetail,
    PlantDetailResponse,
    PlantDeviceStatusResponse,
    PlantElectricmeterResponse,
    PlantEnergyMonthPerDayResponse,
    PlantsInfoResponse,
    PowerDayPoint,
    ShineMonitorAuthResponse,
    TodayDevicePvChartsResponse,
    WarningsResponse,
    WarningItem,
)
from src.utils.crypto import shinemonitor_auth_sign, shinemonitor_passwd_hash, shinemonitor_sign
from src.utils.http import HttpError
from src.utils.logger import logger

__all__ = ["ShineMonitorClient", "ShineMonitorError", "ShineMonitorAuthError"]


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ShineMonitorError(Exception):
    """Base exception for ShineMonitor client errors."""


class ShineMonitorAuthError(ShineMonitorError):
    """Raised when authentication or token refresh fails."""


# ---------------------------------------------------------------------------
# Action name constants (no magic strings)
# ---------------------------------------------------------------------------

_ACTION_AUTH = "auth"
_ACTION_PLANTS_INFO = "queryPlantsInfo"
_ACTION_PLANT_INFO = "queryPlantInfo"
_ACTION_ENERGY_MONTH_PER_DAY = "queryPlantEnergyMonthPerDay"
_ACTION_TODAY_DEVICE_PV_CHARTS = "queryTodayDevicePvCharts"
_ACTION_PLANT_ACTIVE_OUTPUT_POWER = "queryPlantActiveOuputPowerOneDay"
_ACTION_PLANT_DEVICE_STATUS = "queryPlantDeviceStatus"
_ACTION_PLANT_ELECTRICMETER = "queryPlantElectricmeter"
_ACTION_PLANT_CAMERA = "queryPlantCamera"
_ACTION_WARNINGS = "queryWarnings"

# ShineMonitor err code for "success"
_SM_SUCCESS_ERR = 0


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ShineMonitorClient(SolarProviderBase):
    """HTTP client for the ShineMonitor (Eybond SmartClient) API.

    ShineMonitor uses a flat query-string API: all requests go to the
    same base URL and are distinguished by the ``action`` parameter.

    Args:
        base_url: Override the ShineMonitor base URL.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum retry attempts for transient server errors.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        company_key: Optional[str] = None,
        plant_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        # ShineMonitor's base_url IS the full API endpoint — trailing slash required.
        # Do NOT strip it: http://api.shinemonitor.com/public/ → 200
        #                  http://api.shinemonitor.com/public  → 404
        self._base_url: str = base_url or settings.shinemonitor_base_url
        self._timeout: int = timeout or settings.http_timeout
        self._max_retries: int = max_retries or settings.http_max_retries

        self._username: str = username or settings.shinemonitor_username
        self._password: str = password or settings.shinemonitor_password
        self._company_key: str = company_key or settings.shinemonitor_company_key
        self._plant_id: str = plant_id or settings.shinemonitor_plant_id

        # Session state (populated after login — never persisted to disk)
        self._token: Optional[str] = None
        self._secret: Optional[str] = None
        self._expire: Optional[int] = None

        # ShineMonitor uses a flat query-string API; requests.Session gives full control
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        logger.info(
            "ShineMonitorClient initialised | base_url={url}", url=self._base_url
        )

    # ------------------------------------------------------------------
    # SolarProviderBase interface
    # ------------------------------------------------------------------

    def login(self) -> None:
        """Authenticate with ShineMonitor using SHA1-hashed password.

        Verified auth flow (from browser HAR capture of web.shinemonitor.com):

        - Method: GET to ``self._base_url``
        - Params: ``action=auth``, ``usr``, ``company-key``, ``passwd=SHA1(pw)``,
          ``salt=<unix_ms>``, ``sign=SHA1(salt + SHA1(pw) + 'auth')``
        - Response: ``{"err":0, "dat": {"token":"...", "secret":"...", "expire":...}}``

        Note: ``source``, ``app-client`` etc. are NOT required for auth.

        Raises:
            ShineMonitorAuthError: If the API returns ``err != 0`` or
                a network error occurs.
        """
        passwd_hash = shinemonitor_passwd_hash(self._password)  # SHA1(password)
        salt = str(int(time.time() * 1000))                    # Unix ms timestamp
        
        from urllib.parse import quote
        def enc(s):
            return quote(str(s), safe='').replace('+', '%2B').replace("'", '%27')
            
        action_fragment = f"&action=auth&usr={enc(self._username)}&company-key={enc(self._company_key)}"
        
        from src.utils.crypto import sha1_hex
        auth_sign = sha1_hex(salt + passwd_hash + action_fragment)
        
        # Build the exact URL string expected by the server
        url = f"{self._base_url.rstrip('/')}/?sign={auth_sign}&salt={salt}{action_fragment}"

        logger.info(
            "ShineMonitorClient.login() | username={u} salt={s}",
            u=self._username, s=salt,
        )
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
            )
            response.raise_for_status()
            raw = response.json()
        except requests.Timeout as exc:
            raise ShineMonitorAuthError(
                f"ShineMonitor auth timed out after {self._timeout}s"
            ) from exc
        except requests.RequestException as exc:
            raise ShineMonitorAuthError(
                f"ShineMonitor auth network error: {exc}"
            ) from exc

        resp = ShineMonitorAuthResponse.model_validate(raw)
        if not resp.is_success or resp.dat is None:
            raise ShineMonitorAuthError(
                f"ShineMonitor auth failed: err={resp.err} info={resp.info}"
            )

        self._token = resp.dat.token
        self._secret = resp.dat.secret
        # The API returns a duration (e.g. 432000 seconds), not an epoch timestamp
        self._expire = int(time.time()) + resp.dat.expire
        logger.success(
            "ShineMonitorClient authenticated | token={tok}... expire_in={exp}s",
            tok=self._token[:8] if self._token else "?",
            exp=resp.dat.expire,
        )

    def get_today_generation(self) -> Optional[float]:
        self._ensure_authenticated()
        try:
            status = self._api_get(_ACTION_PLANT_DEVICE_STATUS, extra_params={"plantid": self._plant_id})
            if status.get("err") != 0:
                return None
                
            pns, devcodes, sns, devaddrs = [], [], [], []
            for c in status.get("dat", {}).get("collector", []):
                pn = c.get("pn")
                for d in c.get("device", []):
                    if pn and d.get("sn"):
                        pns.append(pn)
                        devcodes.append(str(d.get("devcode", "")))
                        sns.append(d.get("sn"))
                        devaddrs.append(str(d.get("devaddr", "")))
                        
            if not sns:
                return None
                
            charts = self._api_get(_ACTION_TODAY_DEVICE_PV_CHARTS, extra_params={
                "plantid": self._plant_id,
                "pns": ",".join(pns),
                "devcodes": ",".join(devcodes),
                "sns": ",".join(sns),
                "devaddrs": ",".join(devaddrs),
            })
            
            if charts.get("err") != 0:
                return None
                
            total = 0.0
            for item in charts.get("dat", []):
                try:
                    total += float(item.get("val", 0))
                except (ValueError, TypeError):
                    pass
            return total
        except Exception as e:
            logger.error(f"ShineMonitor get_today_generation error: {e}")
            return None

    def get_month_generation(self) -> Optional[float]:
        """Return this month's generation in kWh via queryPlantInfo.

        Returns:
            Energy in kWh or ``None``.
        """
        detail = self.queryPlantInfo()
        if detail and detail.month_energy is not None:
            return detail.month_energy
        return None

    def get_total_generation(self) -> Optional[float]:
        """Return cumulative total generation in kWh via queryPlantInfo.

        Returns:
            Energy in kWh or ``None``.
        """
        detail = self.queryPlantInfo()
        if detail and detail.total_energy is not None:
            return detail.total_energy
        return None

    def get_live_power(self) -> Optional[float]:
        self._ensure_authenticated()
        try:
            now = time.localtime()
            date_str = f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d}"
            curve = self._api_get(_ACTION_PLANT_ACTIVE_OUTPUT_POWER, extra_params={
                "plantid": self._plant_id,
                "date": date_str
            })
            if curve.get("err") != 0:
                return None
                
            pts = curve.get("dat", {}).get("outputPower", [])
            if not pts:
                return None
                
            import datetime
            now_dt = datetime.datetime.now()
            latest_val = 0.0
            for pt in pts:
                ts_str = pt.get("ts")
                if not ts_str: continue
                try:
                    ts_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if ts_dt <= now_dt:
                        latest_val = float(pt.get("val", 0))
                except:
                    pass
            return latest_val
        except Exception as e:
            logger.error(f"ShineMonitor get_live_power error: {e}")
            return None

    def get_weather(self) -> Optional[dict[str, Any]]:
        """ShineMonitor does not provide a dedicated weather endpoint.

        Returns:
            ``None`` — weather data not available from this provider.
        """
        logger.debug("ShineMonitorClient: no weather endpoint available.")
        return None

    def get_device_status(self) -> Optional[list[dict[str, Any]]]:
        """Return device status list via queryPlantDeviceStatus.

        Returns:
            List of device status dicts or ``None``.
        """
        devices = self.queryPlantDeviceStatus()
        if devices is None:
            return None
        return [d.model_dump(by_alias=False, exclude_none=True) for d in devices]

    # ------------------------------------------------------------------
    # ShineMonitor-specific endpoint methods
    # ------------------------------------------------------------------

    def storage_overview(self) -> dict[str, Any]:
        return {}

    def get_daily_yield_history(self, num_days: int = 7) -> dict[str, float]:
        """Fetch daily generation for the past N days.
        Returns a dict of { 'YYYY-MM-DD': float_kwh }
        """
        import datetime
        history = {}
        try:
            points = self.queryPlantEnergyMonthPerDay()
            if points:
                pts_by_day = {p.ts: float(p.val) for p in points if p.ts}
                today = datetime.datetime.now()
                for i in range(num_days):
                    day_str = (today - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
                    history[day_str] = pts_by_day.get(day_str, 0.0)
        except Exception as exc:
            logger.warning("ShineMonitor history failed: {exc}", exc=exc)
        return history

    def queryPlantsInfo(self) -> list[dict[str, Any]]:
        """Retrieve summary information for all plants in the account.

        Returns:
            List of plant summary dicts.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        raw = self._api_get(_ACTION_PLANTS_INFO)
        resp = PlantsInfoResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANTS_INFO)
        if resp.dat is None or resp.dat.info is None:
            return []
        return [p.model_dump(by_alias=False, exclude_none=True) for p in resp.dat.info]

    def queryPlantInfo(self, plant_id: Optional[str] = None) -> Optional[PlantDetail]:
        """Retrieve detailed information for a single plant.

        Args:
            plant_id: Plant identifier; defaults to ``settings.shinemonitor_plant_id``.

        Returns:
            :class:`PlantDetail` instance or ``None``.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        if hasattr(self, '_plant_info_cache'):
            return self._plant_info_cache
        self._ensure_authenticated()
        pn = plant_id or self._plant_id
        # JS uses &plantid=... for queryPlantInfo
        raw = self._api_get(_ACTION_PLANT_INFO, extra_params={"plantid": pn})
        resp = PlantDetailResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANT_INFO)
        self._plant_info_cache = resp.dat
        return self._plant_info_cache

    def queryPlantEnergyMonthPerDay(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        plant_id: Optional[str] = None,
    ) -> list[EnergyDayPoint]:
        """Retrieve daily energy breakdown for a calendar month.

        Args:
            year: 4-digit year; defaults to current year.
            month: 1–12 month number; defaults to current month.
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of :class:`EnergyDayPoint` instances.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        now = time.localtime()
        params: dict[str, Any] = {
            "plantid": plant_id or self._plant_id,
            "year": year or now.tm_year,
            "month": month or now.tm_mon,
        }
        raw = self._api_get(_ACTION_ENERGY_MONTH_PER_DAY, extra_params=params)
        resp = PlantEnergyMonthPerDayResponse.model_validate(raw)
        self._check_response(resp, _ACTION_ENERGY_MONTH_PER_DAY)
        return resp.dat or []

    def queryTodayDevicePvCharts(
        self,
        device_sn: str,
        plant_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve today's intraday PV chart for a specific device.

        Args:
            device_sn: Serial number of the device (inverter).
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of time/power data point dicts.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        params: dict[str, Any] = {
            "plantid": plant_id or self._plant_id,
            "sn": device_sn,
        }
        raw = self._api_get(_ACTION_TODAY_DEVICE_PV_CHARTS, extra_params=params)
        resp = TodayDevicePvChartsResponse.model_validate(raw)
        self._check_response(resp, _ACTION_TODAY_DEVICE_PV_CHARTS)
        if resp.dat is None:
            return []
        return [p.model_dump(by_alias=False, exclude_none=True) for p in resp.dat]

    def queryPlantActiveOuputPowerOneDay(
        self,
        date: Optional[str] = None,
        plant_id: Optional[str] = None,
    ) -> list[PowerDayPoint]:
        """Retrieve the plant's active output power curve for one day.

        Args:
            date: Date string ``"YYYY-MM-DD"``; defaults to today.
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of :class:`PowerDayPoint` instances.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        now = time.localtime()
        date_str = date or f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d}"
        params: dict[str, Any] = {
            "plantid": plant_id or self._plant_id,
            "date": date_str,
        }
        raw = self._api_get(_ACTION_PLANT_ACTIVE_OUTPUT_POWER, extra_params=params)
        resp = PlantActiveOutputPowerOneDayResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANT_ACTIVE_OUTPUT_POWER)
        return resp.dat or []

    def queryPlantDeviceStatus(
        self, plant_id: Optional[str] = None
    ) -> Optional[list[DeviceStatus]]:
        """Retrieve operational status for all devices in a plant.

        Args:
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of :class:`DeviceStatus` instances or ``None``.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        params: dict[str, Any] = {"plantid": plant_id or self._plant_id}
        raw = self._api_get(_ACTION_PLANT_DEVICE_STATUS, extra_params=params)
        resp = PlantDeviceStatusResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANT_DEVICE_STATUS)
        
        if not resp.dat or not resp.dat.collector:
            return []
            
        devices = []
        for c in resp.dat.collector:
            if c.device:
                devices.extend(c.device)
        return devices

    def queryPlantElectricmeter(
        self, plant_id: Optional[str] = None
    ) -> list[ElectricmeterData]:
        """Retrieve electricity meter readings for a plant.

        Args:
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of :class:`ElectricmeterData` instances.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        params: dict[str, Any] = {"plantid": plant_id or self._plant_id}
        raw = self._api_get(_ACTION_PLANT_ELECTRICMETER, extra_params=params)
        resp = PlantElectricmeterResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANT_ELECTRICMETER)
        return resp.dat or []

    def queryPlantCamera(
        self, plant_id: Optional[str] = None
    ) -> list[CameraInfo]:
        """Retrieve camera information for a plant.

        Args:
            plant_id: Plant identifier; defaults to settings value.

        Returns:
            List of :class:`CameraInfo` instances.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        params: dict[str, Any] = {"plantid": plant_id or self._plant_id}
        raw = self._api_get(_ACTION_PLANT_CAMERA, extra_params=params)
        resp = PlantCameraResponse.model_validate(raw)
        self._check_response(resp, _ACTION_PLANT_CAMERA)
        return resp.dat or []

    def queryWarnings(
        self,
        plant_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[WarningItem]:
        """Retrieve active warnings / alerts for a plant.

        Args:
            plant_id: Plant identifier; defaults to settings value.
            page: Page number for paginated results.
            page_size: Number of items per page.

        Returns:
            List of :class:`WarningItem` instances.

        Raises:
            ShineMonitorError: On API-level or network errors.
        """
        self._ensure_authenticated()
        params: dict[str, Any] = {
            "plantid": plant_id or self._plant_id,
            "page": page,
            "pagesize": page_size,
        }
        raw = self._api_get(_ACTION_WARNINGS, extra_params=params)
        resp = WarningsResponse.model_validate(raw)
        self._check_response(resp, _ACTION_WARNINGS)
        return resp.dat or []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_get(
        self,
        action: str,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Execute a signed GET request to the ShineMonitor public API.

        Computes a fresh ``timestamp`` and ``sign`` per request.

        Args:
            action: ShineMonitor action name.
            extra_params: Additional query parameters beyond auth fields.

        Returns:
            Parsed JSON dict.

        Raises:
            ShineMonitorError: On network or HTTP errors.
        """
        assert self._token is not None, "Call login() before making API requests."
        assert self._secret is not None

        # Build the action fragment: "&action=<name>&param=val..."
        from urllib.parse import quote
        def enc(s):
            return quote(str(s), safe='').replace('+', '%2B').replace("'", '%27')

        action_fragment = f"&action={action}"
        if extra_params:
            for k, v in extra_params.items():
                action_fragment += f"&{k}={enc(v)}"

        sign, salt_str = shinemonitor_sign(self._secret, self._token, action_fragment)
        
        url = f"{self._base_url.rstrip('/')}/?sign={sign}&salt={salt_str}&token={self._token}{action_fragment}"
        
        logger.debug("ShineMonitor GET action={action}", action=action)

        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise ShineMonitorError(
                f"ShineMonitor request '{action}' timed out after {self._timeout}s"
            ) from exc
        except requests.RequestException as exc:
            raise ShineMonitorError(
                f"ShineMonitor request '{action}' network error: {exc}"
            ) from exc

    def _ensure_authenticated(self) -> None:
        """Log in if no valid session exists or the token has expired.

        Raises:
            ShineMonitorAuthError: If re-authentication fails.
        """
        if self._token is None or self._secret is None:
            logger.debug("ShineMonitorClient: no session, authenticating…")
            self.login()
            return

        if self._expire is not None:
            if int(time.time()) >= self._expire - 60:
                logger.info("ShineMonitorClient: token near expiry, refreshing…")
                self.login()

    def _check_response(self, resp: Any, action: str = "") -> None:
        """Raise :class:`ShineMonitorError` if ``err != 0``.

        Args:
            resp: A :class:`ShineMonitorResponse` instance.
            action: Action name for error context.

        Raises:
            ShineMonitorAuthError: When ``err`` indicates auth failure.
            ShineMonitorError: For other non-zero error codes.
        """
        if not resp.is_success:
            msg = f"ShineMonitor API error for action='{action}': err={resp.err} info={resp.info}"
            # Common auth error codes: 101, 102, 103
            if resp.err in (101, 102, 103):
                logger.warning(
                    "ShineMonitorClient: auth error {err}, re-authenticating…",
                    err=resp.err,
                )
                self.login()
                raise ShineMonitorAuthError(msg)
            raise ShineMonitorError(msg)

    def close(self) -> None:
        """Close the underlying requests session."""
        self._session.close()
        logger.debug("ShineMonitorClient session closed.")

    def __enter__(self) -> "ShineMonitorClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logger.info("=== ShineMonitorClient self-test ===")

    try:
        with ShineMonitorClient() as client:
            logger.info("login() …")
            client.login()
            logger.info("login OK")

            logger.info("queryPlantsInfo() …")
            plants = client.queryPlantsInfo()
            print("plants:", json.dumps(plants, indent=2))

            logger.info("queryPlantInfo() …")
            detail = client.queryPlantInfo()
            if detail:
                print("plant detail:", json.dumps(
                    detail.model_dump(by_alias=False, exclude_none=True), indent=2
                ))

            logger.info("queryWarnings() …")
            warnings = client.queryWarnings()
            print(f"warnings: {len(warnings)} active")
            for w in warnings:
                print(" •", w.model_dump(by_alias=False, exclude_none=True))

            logger.info("queryPlantEnergyMonthPerDay() …")
            energy_days = client.queryPlantEnergyMonthPerDay()
            print(f"energy days: {len(energy_days)} data points")

    except Exception as exc:
        logger.error("ShineMonitorClient test failed: {exc}", exc=exc)
        raise
