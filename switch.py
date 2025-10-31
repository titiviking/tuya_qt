from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaS6Coordinator

BOOL_DPS = [
    "gsm_en",
    "tel_ctrl_en",
    "arm_sms_en",
    "disarm_sms_en",
    "keyboard_tone_en",
    "arm_delay_tone_en",
    "alarm_delay_tone_en",
    "arm_disarm_tone_en",
    "inside_siren_en",
    "wireless_siren_en",
]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: TuyaS6Coordinator = data["coordinator"]
    device_id = data["device_id"]
    ents = [TuyaS6Switch(coord, device_id, code) for code in BOOL_DPS]
    async_add_entities(ents)


class TuyaS6Switch(CoordinatorEntity[TuyaS6Coordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str, code: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{code}"
        self._attr_name = code.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def is_on(self):
        v = self.coordinator.data.get(self._code)
        if v is None:
            return None
        return bool(v)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.send_commands(self._device_id, [{"code": self._code, "value": True}])
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.send_commands(self._device_id, [{"code": self._code, "value": False}])
        await self.coordinator.async_request_refresh()
