from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaS6Coordinator

INT_DPS = {
    "arm_delay": (0, 300, 1),
    "alarm_delay": (0, 300, 1),
    "alarm_sound_duration": (1, 9, 1),
    "ring_times": (1, 9, 1),
    "tel_alarm_cycle": (1, 9, 1),
}


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: TuyaS6Coordinator = data["coordinator"]
    device_id = data["device_id"]
    ents = []
    for code, (mn, mx, step) in INT_DPS.items():
        ents.append(TuyaS6Number(coord, device_id, code, mn, mx, step))
    async_add_entities(ents)


class TuyaS6Number(CoordinatorEntity[TuyaS6Coordinator], NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str, code: str, mn: int, mx: int, step: int) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{code}"
        self._attr_name = code.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
        self._attr_native_min_value = mn
        self._attr_native_max_value = mx
        self._attr_native_step = step

    @property
    def native_value(self):
        v = self.coordinator.data.get(self._code)
        return float(v) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.send_commands(self._device_id, [{"code": self._code, "value": int(value)}])
        await self.coordinator.async_request_refresh()
