from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .api import TuyaS6Api
from .coordinator import TuyaS6Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp.ClientSession()
    api = TuyaS6Api(
        session=session,
        region=entry.data["region"],
        access_id=entry.data["access_id"],
        access_secret=entry.data["access_secret"],
    )
    coordinator = TuyaS6Coordinator(
        hass,
        api,
        entry.data["device_id"],
        poll_seconds=entry.data.get("poll_seconds", 30),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "api": api,
        "coordinator": coordinator,
        "device_id": entry.data["device_id"],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("tuya_s6_qt: setup entry finished, platforms loaded")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        await data["session"].close()
    return unload_ok
