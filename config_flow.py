from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, TUYA_ENDPOINTS
from .api import TuyaS6Api, TuyaS6ApiError

_LOGGER = logging.getLogger(__name__)
ALLOWED_REGIONS = ["auto"] + sorted(TUYA_ENDPOINTS.keys())


class TuyaS6ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Tuya S6 (qt) Cloud."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            region = user_input["region"]
            device_id = user_input["device_id"].strip()
            session = aiohttp.ClientSession()
            api = TuyaS6Api(session, region, user_input["access_id"].strip(), user_input["access_secret"].strip())

            try:
                # verify now so user gets instant feedback
                await api.get_functions(device_id)
                await session.close()
            except TuyaS6ApiError:
                await session.close()
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{device_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Tuya S6 (qt) {device_id}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required("region", default="auto"): vol.In(ALLOWED_REGIONS),
                vol.Required("access_id"): str,
                vol.Required("access_secret"): str,
                vol.Required("device_id"): str,
                vol.Optional("poll_seconds", default=30): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TuyaS6OptionsFlow(config_entry)


class TuyaS6OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("poll_seconds", default=self._entry.data.get("poll_seconds", 30)): int,
                }
            ),
        )
