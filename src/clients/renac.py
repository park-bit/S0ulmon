from __future__ import annotations

import time
import hashlib
from typing import Any, Optional

from src.clients.base import SolarProviderBase
from src.config import settings
from src.models.renac import (
    RenacLoginResponse,
    RenacOverviewResponse,
    RenacEquipStatResponse,
)
from src.utils.http import HttpAuthError, HttpClient, HttpError
from src.utils.logger import logger

__all__ = ["RenacClient", "RenacError", "RenacAuthError"]


class RenacError(Exception):
    """Base exception for RENAC client errors."""


class RenacAuthError(RenacError):
    """Raised when authentication with RENAC fails."""


_PATH_LOGIN = "/api/user/login"
_PATH_OVERVIEW = "/api/station/overview"
_PATH_EQUIP_STAT = "/api/station/equipStat"


class RenacClient(SolarProviderBase):
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._base_url: str = base_url or settings.renac_base_url
        self._timeout: int = timeout or settings.http_timeout
        self._max_retries: int = max_retries or settings.http_max_retries

        self._username: str = settings.renac_email
        self._password: str = settings.renac_password
        self._station_id: str = settings.renac_station_id

        self._token: Optional[str] = None

        self._http = HttpClient(
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        logger.info("RenacClient initialised | base_url={url}", url=self._base_url)

    def _request_headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        timestamp = str(int(time.time()))
        secret = "9P@3kF7sD2&zX5cV8bNm1qR4tY6uI0o"
        sign = hashlib.md5((self._token + timestamp + secret).encode('utf-8')).hexdigest()
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
            "Origin": "https://sec.renacpower.com",
            "Referer": "https://sec.renacpower.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Token": self._token,
            "timestamp": timestamp,
            "sign": sign,
        }

    def login(self) -> None:
        payload = {
            "login_name": self._username,
            "pwd": self._password,
        }
        logger.info("RenacClient.login() | username={user}", user=self._username)
        try:
            raw = self._http.post(_PATH_LOGIN, json=payload)
        except HttpAuthError as exc:
            raise RenacAuthError(f'RENAC login HTTP 401/403: {exc}') from exc
        except HttpError as exc:
            raise RenacAuthError(f'RENAC login network error: {exc}') from exc

        resp = RenacLoginResponse.model_validate(raw)
        if not resp.is_success or resp.user is None:
            raise RenacAuthError(f"RENAC login failed: code={resp.code} msg={resp.msg}")

        self._token = resp.user.token
        logger.success("RenacClient authenticated | token={tok}...", tok=self._token[:8])

    def overview(self) -> dict[str, Any]:
        try:
            raw = self._http.post(_PATH_OVERVIEW, data={"station_id": self._station_id}, headers=self._request_headers())
            resp = RenacOverviewResponse.model_validate(raw)
            if resp.is_success and resp.data:
                return {
                    "today_generation": resp.data.day_energy,
                    "month_generation": resp.data.month_energy,
                    "total_generation": resp.data.sum_energy,
                    "live_power": resp.data.output_power,
                    "installed_capacity": raw.get("data", {}).get("station_capacity"),
                    "co2_saved": raw.get("data", {}).get("co2"),
                    "performance_ratio": raw.get("data", {}).get("profit_ratio"),
                }
        except Exception as exc:
            logger.warning("RENAC overview failed: {exc}", exc=exc)
        return {}

    def get_device_status(self) -> Optional[set[dict[str, Any]]]:
        try:
            raw = self._http.post(_PATH_EQUIP_STAT, json={"station_id": self._station_id}, headers=self._request_headers())
            resp = RenacEquipStatResponse.model_validate(raw)
            if resp.is_success and resp.data:
                return resp.data.model_dump()
        except Exception as exc:
            logger.warning("RENAC device status failed: {exc}", exc=exc)
        return None

    def get_weather(self) -> Optional[dict[str, Any]]: 
        return None
    
    def storage_overview(self) -> dict[str, Any]:
        return {}

    def get_today_generation(self) -> Optional[float]:
        data = self.overview()
        return data.get("today_generation") if data else None

    def get_month_generation(self) -> Optional[float]:
        data = self.overview()
        return data.get("month_generation") if data else None

    def get_total_generation(self) -> Optional[float]:
        data = self.overview()
        return data.get("total_generation") if data else None

    def get_live_power(self) -> Optional[float]:
        data = self.overview()
        return data.get("live_power") if data else None
