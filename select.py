from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaS6Coordinator

LANG_OPTS = [
    "English",
    "French",
    "Italian",
    "German",
    "Spanish",
    "Danish",
    "Dutch",
    "Portuguese",
]

SIREN_OPTS = ["ON", "OFF"]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: TuyaS6Coordinator = data["coordinator"]
    device_id = data["device_id"]

    ents = [
        TuyaS6Select(coord, device_id, "language", LANG_OPTS),
        TuyaS6Select(coord, device_id, "inside_siren_sound", SIREN_OPTS),
    ]
    async_add_entities(ents)


class TuyaS6Select(CoordinatorEntity[TuyaS6Coordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str, code: str, options: list[str]) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{code}"
        self._attr_name = code.replace("_", " ").title()
        self._attr_options = options
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def current_option(self):
        return self.coordinator.data.get(self._code)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.send_commands(self._device_id, [{"code": self._code, "value": option}])
        await self.coordinator.async_request_refresh()
