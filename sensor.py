from __future__ import annotations

import base64

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaS6Coordinator

BASE64_DPS = ["tel_num", "sub_device", "alarm_msg", "history_msg"]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: TuyaS6Coordinator = data["coordinator"]
    device_id = data["device_id"]

    ents = [
        TuyaS6SimpleSensor(coord, device_id, "gsm_status"),
        TuyaS6SimpleSensor(coord, device_id, "dc_status"),
        TuyaS6SimpleSensor(coord, device_id, "device_info"),
        TuyaS6BatterySensor(coord, device_id),
    ]
    for code in BASE64_DPS:
        ents.append(TuyaS6Base64Sensor(coord, device_id, code))

    async_add_entities(ents)


class TuyaS6SimpleSensor(CoordinatorEntity[TuyaS6Coordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str, code: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{code}"
        self._attr_name = code.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def native_value(self):
        return self.coordinator.data.get(self._code)


class TuyaS6BatterySensor(CoordinatorEntity[TuyaS6Coordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}_battery"
        self._attr_name = "Battery"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def native_value(self):
        return self.coordinator.data.get("bat_status")


class TuyaS6Base64Sensor(CoordinatorEntity[TuyaS6Coordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaS6Coordinator, device_id: str, code: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{code}"
        self._attr_name = code.replace("_", " ").title()
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def native_value(self):
        val = self.coordinator.data.get(self._code)
        if not val:
            return None
        try:
            return base64.b64decode(val).decode(errors="ignore")
        except Exception:
            return val
