from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TuyaS6Api, TuyaS6ApiError
from .const import DEFAULT_POLL, S6_ALL_DPS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TuyaS6Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Tuya cloud for S6 status and expose data & commands to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TuyaS6Api,
        device_id: str,
        poll_seconds: int = DEFAULT_POLL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=poll_seconds),
        )
        self.api = api
        self.device_id = device_id
        self.functions: dict[str, dict[str, Any]] = {}
        self._init_lock = asyncio.Lock()
        self._verify_lock = asyncio.Lock()
        self._verify_active = False  # freeze scheduled polls during verify

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest status; keep all known DPs present."""
        # When verify is active, avoid bouncing UI with stale intermediate reads.
        if self._verify_active and isinstance(self.data, dict):
            return dict(self.data)

        try:
            status_list = await self.api.get_status(self.device_id)
            data = {item["code"]: item.get("value") for item in status_list if "code" in item}

            if not self.functions:
                async with self._init_lock:
                    if not self.functions:
                        funcs = await self.api.get_functions(self.device_id)
                        self.functions = {f["code"]: f for f in funcs}
                        _LOGGER.debug("tuya_s6_qt: functions=%s", list(self.functions))

            for dp in S6_ALL_DPS:
                data.setdefault(dp, None)

            return data

        except TuyaS6ApiError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch_status_once(self) -> dict[str, Any]:
        """One-shot fetch without touching verify flags."""
        status_list = await self.api.get_status(self.device_id)
        data = {item["code"]: item.get("value") for item in status_list if "code" in item}
        for dp in S6_ALL_DPS:
            data.setdefault(dp, None)
        return data

    async def async_refresh_now(self) -> dict[str, Any]:
        """One-shot refresh and publish."""
        data = await self._fetch_status_once()
        self.async_set_updated_data(data)
        return data

    async def async_send_commands(
        self,
        commands: list[dict[str, Any]],
        *,
        verify: dict[str, Any] | None = None,
        timeout_seconds: float = 8.0,
        interval_seconds: float = 0.8,
    ) -> Any:
        """
        Send DP commands; optionally verify target DPs reach expected values.
        No optimistic writes; only publish when cloud confirms or timeout hits.
        """
        _LOGGER.debug("tuya_s6_qt: send_commands %s verify=%s", commands, verify)

        try:
            result = await self.api.send_commands(self.device_id, commands)
        except TuyaS6ApiError as err:
            _LOGGER.error("tuya_s6_qt: command error: %s", err.payload or err)
            raise

        # No verification requested -> just refresh once quickly so UI moves faster.
        if not verify:
            try:
                await self.async_refresh_now()
            except Exception:  # best-effort refresh
                _LOGGER.debug("tuya_s6_qt: best-effort post-command refresh failed")
            return result

        # Bounded verify loop: freeze scheduled polls to avoid flip-flop
        async with self._verify_lock:
            self._verify_active = True
            try:
                deadline = self.hass.loop.time() + timeout_seconds
                while self.hass.loop.time() < deadline:
                    try:
                        current = await self._fetch_status_once()
                    except TuyaS6ApiError:
                        current = None

                    if isinstance(current, dict):
                        if all(current.get(k) == v for k, v in verify.items()):
                            self.async_set_updated_data(current)
                            _LOGGER.debug("tuya_s6_qt: verify OK for %s", verify)
                            return result

                    await asyncio.sleep(interval_seconds)

                # Timeout: publish the latest we saw (even if not matching) to keep UI honest
                try:
                    latest = await self._fetch_status_once()
                except TuyaS6ApiError:
                    latest = self.data if isinstance(self.data, dict) else {}
                self.async_set_updated_data(latest)
                _LOGGER.debug("tuya_s6_qt: verify timeout; published latest status")
                return result
            finally:
                self._verify_active = False
